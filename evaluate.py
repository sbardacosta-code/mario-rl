#!/usr/bin/env python3
"""Run seeded Mario checkpoint evaluations; never update model weights."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def positive_float(value: str) -> float:
    number = float(value)
    if not 0 < number < float("inf"):
        raise argparse.ArgumentTypeError("must be finite and positive")
    return number


def write_json(path: Path, data: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    parser.add_argument("--max-decisions", type=positive_int, default=3000)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--video-steps", type=positive_int, default=300)
    parser.add_argument("--max-seconds", type=positive_float, default=180.0)
    args = parser.parse_args()
    if len(set(args.seeds)) != len(args.seeds):
        parser.error("seeds must be distinct")
    if any(seed < 0 or seed >= 2**32 for seed in args.seeds):
        parser.error("seeds must be between 0 and 2**32 - 1")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "evaluation.json"
    started = time.monotonic()
    deadline = started + args.max_seconds
    report = {
        "status": "running",
        "model": str(args.model.resolve()),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "learning_updates": 0,
        "protocol": {
            "version": 1,
            "environment": "SuperMarioBros-1-1-v0",
            "seeds": args.seeds,
            "max_decisions": args.max_decisions,
            "deterministic": False,
            "seed_method": "SB3 set_random_seed plus environment reset(seed)",
            "action_space": "RIGHT_ONLY",
            "action_repeat": 4,
            "observation_shape": [4, 84, 84],
            "reward": "native reward summed over repeated frames",
            "device": args.device,
        },
        "max_seconds": args.max_seconds,
        "episodes": [],
        "partial_episode": None,
        "mean_max_x": None,
        "mean_native_reward": None,
        "level_completions": 0,
        "completion_rate": None,
        "limitations": f"{len(args.seeds)} seeded trials are a small sample; a short GIF shows only one trial.",
    }

    def save_report() -> None:
        episodes = report["episodes"]
        count = len(episodes)
        report["finished_episodes"] = count
        report["planned_episodes"] = len(args.seeds)
        report["mean_max_x"] = sum(e["max_x"] for e in episodes) / count if count else None
        report["mean_native_reward"] = (
            sum(e["native_reward"] for e in episodes) / count if count else None
        )
        report["level_completions"] = sum(e["completed"] for e in episodes)
        report["completion_rate"] = report["level_completions"] / count if count else None
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        write_json(report_path, report)

    save_report()
    frames = []
    exit_code = 0
    try:
        import numpy as np
        from PIL import Image
        from stable_baselines3 import PPO
        from stable_baselines3.common.utils import set_random_seed
        import torch
        from mario_env import make_env

        torch.set_num_threads(1)
        model = PPO.load(args.model, device=args.device)
        model.policy.set_training_mode(False)
        for trial_index, seed in enumerate(args.seeds):
            if time.monotonic() >= deadline:
                report["status"] = "incomplete"
                report["reason"] = "overall wall-time limit reached"
                break
            set_random_seed(seed, using_cuda=str(args.device).startswith("cuda"))
            env = make_env(seed=seed, render_mode="rgb_array", max_decisions=args.max_decisions)
            decisions = 0
            native_reward = 0.0
            max_x = 0
            info = {}
            episode_started = time.monotonic()
            try:
                observation, info = env.reset(seed=seed)
                max_x = int(info.get("x_pos", 0))
                for decisions in range(1, args.max_decisions + 1):
                    if time.monotonic() >= deadline:
                        report["status"] = "incomplete"
                        report["reason"] = "overall wall-time limit reached"
                        report["partial_episode"] = {
                            "seed": seed,
                            "decisions": decisions - 1,
                            "max_x": max_x,
                            "native_reward": native_reward,
                            "excluded_from_episode_means": True,
                        }
                        break
                    action, _ = model.predict(observation, deterministic=False)
                    observation, reward, terminated, truncated, info = env.step(int(np.asarray(action).item()))
                    native_reward += float(reward)
                    max_x = max(max_x, int(info.get("action_repeat_max_x", info.get("x_pos", 0))))
                    if trial_index == 0 and len(frames) < args.video_steps:
                        raw = env.render()
                        if raw is not None:
                            raw = np.asarray(raw)
                            if raw.ndim != 3 or raw.shape[-1] != 3:
                                raise ValueError(f"Expected native RGB render; got {raw.shape}")
                            frames.append(Image.fromarray(raw.copy()))
                    if terminated or truncated or decisions == args.max_decisions:
                        metrics = info.get("episode_metrics", {})
                        completed = bool(metrics.get("completed", metrics.get("flag_get", info.get("flag_get", False))))
                        report["episodes"].append({
                            "seed": seed,
                            "max_x": int(metrics.get("max_x", max_x)),
                            "completed": completed,
                            "flag_get": bool(metrics.get("flag_get", info.get("flag_get", completed))),
                            "native_reward": float(metrics.get("native_reward_sum", native_reward)),
                            "decisions": int(metrics.get("decisions", decisions)),
                            "raw_frames": int(metrics["raw_frames"]) if "raw_frames" in metrics else None,
                            "terminated": bool(terminated),
                            "truncated": bool(truncated),
                            "end_reason": "terminated" if terminated else "truncated" if truncated else "decision_limit",
                            "elapsed_seconds": round(time.monotonic() - episode_started, 3),
                        })
                        save_report()
                        break
            finally:
                env.close()
            if report["status"] == "incomplete":
                break
        else:
            report["status"] = "complete"
    except Exception as error:
        exit_code = 1
        report["status"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}"
        import traceback
        traceback.print_exc()
    finally:
        if frames:
            gif_path = args.output_dir / "first-seed.gif"
            try:
                frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=67, loop=0)
                report["gif"] = str(gif_path.resolve())
                report["gif_frames"] = len(frames)
                report["gif_seed"] = args.seeds[0]
                report["gif_duration_ms_per_frame"] = 67
            except Exception as error:
                report["gif_error"] = f"{type(error).__name__}: {error}"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        save_report()
    print(json.dumps(report, indent=2, allow_nan=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
