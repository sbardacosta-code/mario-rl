#!/usr/bin/env python3
"""Train a time-bounded Mario PPO experiment and retain auditable results."""
from __future__ import annotations

import argparse
import csv
from collections import deque
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import platform
import time
import traceback

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".cache/matplotlib"))

from gymnasium import RewardWrapper
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.logger import configure
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from mario_env import make_env


class ScaleReward(RewardWrapper):
    """Scale learning rewards while preserving native episode metrics in info."""

    def __init__(self, env, scale=1.0):
        super().__init__(env)
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError("reward scale must be finite and positive")
        self.scale = float(scale)

    def reward(self, reward):
        return float(reward) * self.scale


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def save_model(model, path):
    path = Path(path)
    temporary = path.with_name("." + path.stem + ".tmp.zip")
    model.save(temporary)
    temporary.replace(path)


def policy_digest(state):
    digest = sha256()
    for name, tensor in sorted(state.items()):
        digest.update(name.encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def optimizer_steps(model):
    steps = [value.get("step", 0) for value in model.policy.optimizer.state.values()]
    return max((int(value.item() if hasattr(value, "item") else value) for value in steps), default=0)


class SessionCallback(BaseCallback):
    def __init__(self, run_dir, max_seconds, deadline_utc, checkpoint_seconds):
        super().__init__()
        self.run_dir = run_dir
        self.max_seconds = max_seconds
        self.deadline = datetime.fromisoformat(deadline_utc.replace("Z", "+00:00")).timestamp() if deadline_utc else None
        self.checkpoint_seconds = checkpoint_seconds
        self.recent = deque(maxlen=100)
        self.episode_count = 0
        self.completions = 0
        self.best_x = 0
        self.stop_reason = "timesteps_reached"

    def _on_training_start(self):
        self.started = time.monotonic()
        self.first_timestep = self.model.num_timesteps
        self.next_checkpoint = self.checkpoint_seconds
        self.next_archive = 300.0
        self.next_progress = 0.0
        self.next_print = 0.0
        self.csv_file = (self.run_dir / "episodes.csv").open("w", newline="")
        self.writer = csv.DictWriter(self.csv_file, fieldnames=["elapsed_seconds", "timesteps", "return", "length", "max_x", "completed"])
        self.writer.writeheader()
        self.csv_file.flush()

    def progress(self):
        elapsed = time.monotonic() - self.started
        recent = list(self.recent)
        return {
            "elapsed_seconds": round(elapsed, 3),
            "timesteps": self.model.num_timesteps,
            "decisions_this_run": self.model.num_timesteps - self.first_timestep,
            "decisions_per_second": round((self.model.num_timesteps - self.first_timestep) / max(elapsed, 0.001), 2),
            "episodes": self.episode_count,
            "training_completions": self.completions,
            "best_training_x": self.best_x,
            "recent_mean_x": float(np.mean([row["max_x"] for row in recent])) if recent else None,
            "recent_mean_return": float(np.mean([row["return"] for row in recent])) if recent else None,
            "ppo_epochs": self.model._n_updates,
            "optimizer_steps": optimizer_steps(self.model),
        }

    def _on_step(self):
        elapsed = time.monotonic() - self.started
        for done, info in zip(self.locals["dones"], self.locals["infos"]):
            if done:
                metrics = info["episode_metrics"]
                row = {
                    "elapsed_seconds": round(elapsed, 3),
                    "timesteps": self.model.num_timesteps,
                    "return": float(metrics["native_reward_sum"]),
                    "length": int(metrics["decisions"]),
                    "max_x": int(metrics["max_x"]),
                    "completed": int(metrics["completed"]),
                }
                self.writer.writerow(row)
                self.csv_file.flush()
                self.recent.append(row)
                self.episode_count += 1
                self.completions += row["completed"]
                self.best_x = max(self.best_x, row["max_x"])
        if elapsed >= self.next_progress:
            write_json(self.run_dir / "progress.json", self.progress())
            self.next_progress = elapsed + 10
        if elapsed >= self.next_print:
            print(json.dumps(self.progress()), flush=True)
            self.next_print = elapsed + 30
        if elapsed >= self.next_checkpoint:
            save_model(self.model, self.run_dir / "checkpoints/latest.zip")
            self.next_checkpoint = elapsed + self.checkpoint_seconds
        if elapsed >= self.next_archive:
            save_model(self.model, self.run_dir / f"checkpoints/step_{self.model.num_timesteps:09d}.zip")
            self.next_archive = elapsed + 300
        if elapsed >= self.max_seconds:
            self.stop_reason = "training_time_budget_reached"
            return False
        if self.deadline is not None and time.time() >= self.deadline:
            self.stop_reason = "session_training_deadline_reached"
            return False
        return True

    def _on_training_end(self):
        self.csv_file.close()
        write_json(self.run_dir / "progress.json", self.progress())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=Path("results/first_training"))
    parser.add_argument("--max-seconds", type=float, default=1500)
    parser.add_argument("--max-timesteps", type=int, default=100_000_000)
    parser.add_argument("--deadline-utc")
    parser.add_argument("--device", choices=["cpu", "mps"], default="cpu")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--n-envs", type=int, default=4)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--max-decisions", type=int, default=3000)
    parser.add_argument("--checkpoint-seconds", type=float, default=60)
    parser.add_argument("--reward-scale", type=float, default=1.0, help="multiply training rewards only; native episode metrics remain unchanged")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--initialize-only", action="store_true")
    args = parser.parse_args()
    if min(args.max_seconds, args.max_timesteps, args.threads, args.n_envs, args.max_decisions, args.checkpoint_seconds) <= 0:
        parser.error("budgets, worker counts, and checkpoint interval must be positive")
    if not math.isfinite(args.reward_scale) or args.reward_scale <= 0:
        parser.error("reward scale must be finite and positive")
    args.run_dir.mkdir(parents=True, exist_ok=True)
    (args.run_dir / "checkpoints").mkdir(exist_ok=True)
    if (args.run_dir / "training_summary.json").exists():
        parser.error("choose a new --run-dir; completed experiments are not overwritten")
    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(1)
    if args.device == "mps" and not torch.backends.mps.is_available():
        parser.error("MPS is unavailable; choose --device cpu")
    env = DummyVecEnv([lambda i=i: Monitor(ScaleReward(make_env(seed=args.seed+i, max_decisions=args.max_decisions), args.reward_scale)) for i in range(args.n_envs)])
    hyperparameters = dict(n_steps=256, batch_size=256, n_epochs=4, learning_rate=2.5e-4, gamma=0.99, gae_lambda=0.95, ent_coef=0.01, clip_range=0.2)
    try:
        if args.resume:
            model = PPO.load(args.resume, env=env, device=args.device)
        else:
            model = PPO("CnnPolicy", env, seed=args.seed, device=args.device, verbose=0, **hyperparameters)
        config = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "environment": "SuperMarioBros-1-1-v0", "algorithm": "PPO", "policy": "CnnPolicy",
            "hyperparameters": hyperparameters, "action_set": "RIGHT_ONLY", "action_repeat": 4,
            "observation_shape": [4,84,84], "reward": "native summed across repeated frames, multiplied by reward_scale for learning",
            "reward_scale": args.reward_scale,
            "metric_units": {"episodes.csv:return": "native reward", "logs:rollout/ep_rew_mean": "scaled training reward", "evaluation": "native reward"},
            "args": {key: str(value) if isinstance(value, Path) else value for key,value in vars(args).items()},
            "python": platform.python_version(), "platform": platform.platform(),
            "packages": {name:version(name) for name in ["gym-super-mario-bros","nes-py","gymnasium","stable-baselines3","torch","numpy"]},
            "continuation_note": "PPO parameters and optimizer resume; simulator state, partial rollout, and RNG state are not restored exactly.",
        }
        write_json(args.run_dir / "config.json", config)
        if not args.resume:
            save_model(model, args.run_dir / "checkpoints/initial.zip")
        if args.initialize_only:
            print(json.dumps({"status":"initialized", "initial_model":str(args.run_dir / "checkpoints/initial.zip"), "learning_updates":0}), flush=True)
            return 0
        before = {key:value.detach().cpu().clone() for key,value in model.policy.state_dict().items()}
        first_optimizer_steps = optimizer_steps(model)
        first_epochs = model._n_updates
        callback = SessionCallback(args.run_dir, args.max_seconds, args.deadline_utc, args.checkpoint_seconds)
        model.set_logger(configure(str(args.run_dir / "logs"), ["csv", "tensorboard"]))
        status = "completed"
        error = None
        try:
            model.learn(total_timesteps=args.max_timesteps, callback=callback, reset_num_timesteps=False, log_interval=1)
        except KeyboardInterrupt:
            status = "interrupted"
            callback.stop_reason = "keyboard_interrupt"
        except Exception as caught:
            status = "failed"
            callback.stop_reason = "exception"
            error = f"{type(caught).__name__}: {caught}"
            traceback.print_exc()
        finally:
            if hasattr(callback, "csv_file") and not callback.csv_file.closed:
                callback.csv_file.close()
            save_model(model, args.run_dir / "checkpoints/final.zip")
            save_model(model, args.run_dir / "checkpoints/latest.zip")
        after = model.policy.state_dict()
        changed = sum(not torch.equal(before[key], tensor.detach().cpu()) for key,tensor in after.items())
        finite = all(bool(torch.isfinite(tensor).all().item()) for tensor in after.values())
        summary = {
            "status": status, "error":error, "completed_at":datetime.now(timezone.utc).isoformat(),
            "stop_reason": callback.stop_reason, **callback.progress(),
            "optimizer_steps_this_run":optimizer_steps(model)-first_optimizer_steps,
            "ppo_epochs_this_run":model._n_updates-first_epochs,
            "changed_parameter_tensors":changed, "all_parameters_finite":finite,
            "policy_sha256_before":policy_digest(before), "policy_sha256_after":policy_digest(after),
            "final_model":"checkpoints/final.zip", "latest_model":"checkpoints/latest.zip",
            "partial_final_rollout": "An incomplete rollout at the time limit is discarded; completed optimizer updates are saved.",
        }
        write_json(args.run_dir / "training_summary.json", summary)
        print(json.dumps(summary, indent=2), flush=True)
        return 0 if status == "completed" and finite and changed > 0 and summary["optimizer_steps_this_run"] > 0 else 1
    finally:
        env.close()


if __name__ == "__main__":
    raise SystemExit(main())
