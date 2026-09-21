#!/usr/bin/env python3
"""Continue a frozen Mario baseline in four auditable, bounded learning stages.

The plan is written before this runner starts. Learning time is separate from
evaluation/publication time. Existing experiments are never restarted or
overwritten; --finish-only retries presentation and publication of completed
results without launching either training or evaluation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import statistics
import subprocess
import sys
import time


class StopRequested(Exception):
    """The experiment's STOP file requested a graceful halt."""


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: Path) -> dict:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def within(root: Path, value: str | Path) -> Path:
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Path escapes the repository: {value}")
    return path


def same_number(actual, expected) -> bool:
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return math.isfinite(actual) and math.isfinite(expected) and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12)
    return actual == expected


def verify_parameters(actual: dict, expected: dict, label: str) -> None:
    for key, value in expected.items():
        if key not in actual or not same_number(actual[key], value):
            raise RuntimeError(f"{label} differs from the plan: {key} = {actual.get(key)!r}, expected {value!r}")


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGINT)
    except ProcessLookupError:
        process.wait()
        return
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


def run_process(command: list[str], root: Path, log: Path, timeout: float, stop_file: Path | None = None) -> tuple[int, str | None]:
    if stop_file and stop_file.exists():
        return 130, "stop_requested"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as output:
        output.write(json.dumps({"started_at": utc(), "command": command}) + "\n")
        output.flush()
        process = subprocess.Popen(command, cwd=root, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                reason = "stop_requested" if stop_file and stop_file.exists() else "command_timeout" if time.monotonic() >= deadline else None
                if reason:
                    stop_process(process)
                    return process.returncode, reason
                time.sleep(0.5)
        except BaseException:
            stop_process(process)
            raise
        return process.returncode, None


class Experiment:
    def __init__(self, root: Path, plan_path: Path, publish: bool):
        self.root = root
        self.plan_path = plan_path
        self.plan = load(plan_path)
        self.plan_hash = digest(plan_path)
        self.run = plan_path.parent
        self.manifest_path = self.run / "manifest.json"
        self.stop_file = self.run / "STOP"
        self.publish_enabled = publish
        self.py = sys.executable
        self.manifest: dict = {}
        self.started = time.monotonic()
        self.keep_awake: subprocess.Popen | None = None

    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def persist(self) -> None:
        self.manifest["updated_at"] = utc()
        save(self.manifest_path, self.manifest)

    def checkpoint_metadata(self, path: Path) -> dict:
        # Loading for verification performs no rollout and no optimizer update.
        import torch
        from stable_baselines3 import PPO
        from train import optimizer_steps, policy_digest
        torch.set_num_threads(1)
        model = PPO.load(path, device="cpu")
        state = model.policy.state_dict()
        parameters = {key: getattr(model, key) for key in (
            "n_steps", "batch_size", "n_epochs", "gamma", "gae_lambda", "ent_coef",
            "target_kl", "vf_coef", "max_grad_norm", "normalize_advantage",
        )}
        parameters.update({
            "learning_rate": float(model.lr_schedule(model._current_progress_remaining)),
            "learning_rate_schedule": repr(model.lr_schedule),
            "clip_range": float(model.clip_range(model._current_progress_remaining)),
            "clip_range_vf": float(model.clip_range_vf(model._current_progress_remaining)) if model.clip_range_vf else None,
        })
        result = {
            "num_timesteps": int(model.num_timesteps),
            "optimizer_steps": optimizer_steps(model),
            "policy_sha256": policy_digest(state),
            "all_parameters_finite": all(bool(torch.isfinite(tensor).all().item()) for tensor in state.values()),
            "effective_seed": model.seed,
            "hyperparameters": parameters,
        }
        del model, state
        return result

    def validate_plan(self) -> None:
        required = (
            "initial_checkpoint", "initial_checkpoint_sha256", "source_hashes",
            "validation_seeds", "validation_video_seeds", "holdout_seeds", "holdout_video_seeds",
            "chunk_seconds", "max_chunks", "reward_scale", "expected_hyperparameters", "created_at",
        )
        missing = [name for name in required if name not in self.plan]
        if missing:
            raise ValueError("Plan fields missing: " + ", ".join(missing))
        if self.plan["max_chunks"] != 4 or not same_number(self.plan["chunk_seconds"], 900):
            raise ValueError("This experiment requires four 900-second learning stages")
        if not same_number(self.plan["reward_scale"], 0.01):
            raise ValueError("The existing 0.01 training reward scale must be preserved")
        if not isinstance(self.plan["expected_hyperparameters"], dict) or not self.plan["expected_hyperparameters"]:
            raise ValueError("Expected checkpoint hyperparameters must be recorded before the run")
        if not isinstance(self.plan["source_hashes"], dict) or not {"train.py", "mario_env.py", "lesson_eval.py"}.issubset(self.plan["source_hashes"]):
            raise ValueError("The plan must freeze the trainer, environment, and evaluator sources")
        for name, video_name, size in (("validation_seeds", "validation_video_seeds", 20), ("holdout_seeds", "holdout_video_seeds", 100)):
            seeds, videos = self.plan[name], self.plan[video_name]
            if not isinstance(seeds, list) or len(seeds) != size or len(set(seeds)) != size:
                raise ValueError(f"{name} must contain {size} distinct seeds")
            if any(type(seed) is not int or not 0 <= seed < 2**32 for seed in seeds):
                raise ValueError(f"Invalid {name}")
            if not isinstance(videos, list) or len(videos) != len(set(videos)) or not set(videos).issubset(seeds):
                raise ValueError(f"Invalid {video_name}")
        if set(self.plan["validation_seeds"]) & set(self.plan["holdout_seeds"]):
            raise ValueError("Validation and final test seeds must be disjoint")
        self.baseline = within(self.root, self.plan["initial_checkpoint"])
        if not self.baseline.is_file():
            raise ValueError("The planned baseline checkpoint does not exist")

    def verify_sources(self) -> None:
        if digest(self.plan_path) != self.plan_hash:
            raise RuntimeError("The experiment plan changed after the run started")
        for name, expected in self.plan["source_hashes"].items():
            path = within(self.root, name)
            if digest(path) != expected:
                raise RuntimeError(f"Source changed during the experiment: {name}")
        if digest(self.baseline) != self.plan["initial_checkpoint_sha256"]:
            raise RuntimeError("The original baseline checkpoint changed")

    def verify_fresh_seeds(self) -> None:
        planned = set(self.plan["validation_seeds"]) | set(self.plan["holdout_seeds"])
        for path in (self.root / "results").rglob("evaluation.json"):
            data = load(path)
            overlap = planned & set(data.get("protocol", {}).get("seeds", []))
            if overlap:
                raise RuntimeError(f"Planned seeds were already evaluated in {self.rel(path)}: {sorted(overlap)}")

    def check_stop(self) -> None:
        if self.stop_file.exists():
            raise StopRequested("The experiment STOP file was created")

    def execute(self, command: list[str], log_name: str, timeout: float, stoppable: bool = False) -> None:
        code, reason = run_process(command, self.root, self.run / "logs" / log_name, timeout, self.stop_file if stoppable else None)
        if reason == "stop_requested":
            raise StopRequested("The experiment STOP file was created")
        if reason or code:
            raise RuntimeError(f"{Path(command[1]).name}: return code {code}; {reason or 'see log'} ({log_name})")

    def render(self) -> None:
        for script in ("continuation_report.py", "lesson_report.py"):
            self.execute([self.py, script, "--manifest", self.rel(self.manifest_path)], script.replace(".py", ".log"), 180)

    def publish(self) -> bool:
        if not self.publish_enabled:
            return True
        run_relative = self.rel(self.run)
        publication = self.run / "logs" / "publication.json"

        def git(*args, timeout=60) -> subprocess.CompletedProcess:
            return subprocess.run(["git", *args], cwd=self.root, check=True, text=True, capture_output=True, timeout=timeout)

        def allowed(name: str) -> bool:
            return name.startswith(run_relative + "/") or name.startswith("docs/aula/")

        try:
            if git("branch", "--show-current").stdout.strip() != "main":
                raise RuntimeError("Automatic publication requires main; the branch is not changed")
            staged = git("diff", "--cached", "--name-only", "-z").stdout.split("\0")
            if any(name and not allowed(name) for name in staged):
                raise RuntimeError("Unrelated changes are already staged; automatic publication leaves them untouched")
            git("add", "--", run_relative, "docs/aula")
            staged = git("diff", "--cached", "--name-only", "-z").stdout.split("\0")
            if any(name and not allowed(name) for name in staged):
                raise RuntimeError("Unrelated staged changes prevent automatic publication")
            if any(staged):
                git("diff", "--cached", "--check")
                git("commit", "-m", f"Update Mario continuation {self.manifest['session_id']}: {len(self.manifest['stages'])} stages ({self.manifest['status']})", timeout=90)
            git("push", "origin", "main", timeout=120)
            commit = git("rev-parse", "HEAD").stdout.strip()
            remote = git("ls-remote", "origin", "refs/heads/main").stdout.split()
            if not remote or remote[0] != commit:
                raise RuntimeError("Remote main does not match the local published commit")
            save(publication, {"status": "published", "at": utc(), "commit": commit})
            return True
        except (subprocess.SubprocessError, RuntimeError) as error:
            save(publication, {"status": "pending", "at": utc(), "error": str(error)})
            print("Publication pending: " + str(error), flush=True)
            return False

    def evaluate(self, model: Path, output: Path, seeds: list[int], videos: list[int], label: str) -> dict:
        self.check_stop()
        self.verify_sources()
        expected_hash = digest(model)
        if output.exists():
            raise RuntimeError(f"Evaluation output already exists: {self.rel(output)}")
        command = [
            self.py, "lesson_eval.py", "--model", self.rel(model), "--output-dir", self.rel(output),
            "--seeds", *map(str, seeds), "--video-seeds", *map(str, videos),
            "--max-decisions", "3000", "--max-seconds", "600", "--device", "cpu",
            "--beginning-decisions", "3000", "--ending-decisions", "75", "--stall-decisions", "120",
        ]
        self.manifest["active_evaluation"] = label
        self.persist()
        self.execute(command, label + ".log", 660, stoppable=True)
        data = load(output / "evaluation.json")
        episodes = data.get("episodes", [])
        protocol = data.get("protocol", {})
        expected_protocol = {
            "environment": "SuperMarioBros-1-1-v0", "seeds": seeds, "max_decisions": 3000,
            "deterministic": False, "seed_method": "SB3 set_random_seed plus environment reset(seed)",
            "action_space": "RIGHT_ONLY", "action_repeat": 4, "observation_shape": [4, 84, 84],
            "reward": "native reward summed over repeated frames", "device": "cpu",
            "stall_threshold_decisions": 120,
            "stall_definition": "consecutive decisions without a new maximum x position",
        }
        if data.get("status") != "complete" or [ep.get("seed") for ep in episodes] != seeds or data.get("partial_episode") is not None:
            raise RuntimeError(f"Incomplete or mismatched evaluation: {label}")
        if data.get("learning_updates") != 0 or data.get("model_sha256") != expected_hash or digest(model) != expected_hash:
            raise RuntimeError(f"Frozen-model verification failed: {label}")
        for key, value in expected_protocol.items():
            if protocol.get(key) != value:
                raise RuntimeError(f"Evaluation protocol mismatch in {label}: {key}")
        for episode in episodes:
            if not 1 <= episode.get("decisions", 0) <= 3000 or not episode.get("terminated", False) and not episode.get("truncated", False):
                raise RuntimeError(f"Incomplete episode boundary in {label}: seed {episode.get('seed')}")
            if not math.isfinite(float(episode["native_reward"])) or not math.isfinite(float(episode["max_x"])):
                raise RuntimeError(f"Non-finite metrics in {label}")
            trace = (output / episode["trace_csv"]).resolve()
            if not trace.is_relative_to(output.resolve()) or not trace.is_file():
                raise RuntimeError(f"Missing trace in {label}")
            if episode["seed"] in videos:
                clip = episode.get("media", {}).get("beginning", {})
                if not clip.get("is_full_episode") or clip.get("first_decision") != 1 or clip.get("last_decision") != episode["decisions"]:
                    raise RuntimeError(f"Full trial clip missing in {label}: seed {episode['seed']}")
                asset = (output / clip["path"]).resolve()
                if not asset.is_relative_to(output.resolve()) or not asset.is_file():
                    raise RuntimeError(f"Full trial media file missing in {label}")
        clears = sum(bool(ep["completed"]) for ep in episodes)
        if data.get("level_completions") != clears or not same_number(data.get("completion_rate"), clears / len(episodes)):
            raise RuntimeError(f"Completion aggregate mismatch in {label}")
        for key, field in (("mean_max_x", "max_x"), ("mean_native_reward", "native_reward")):
            if not same_number(data.get(key), statistics.mean(ep[field] for ep in episodes)):
                raise RuntimeError(f"Evaluation aggregate mismatch in {label}: {key}")
        self.verify_sources()
        self.manifest["active_evaluation"] = None
        self.persist()
        return data

    def verify_training(self, training: Path, previous: dict, previous_model: Path, stopped: bool) -> tuple[dict, dict]:
        summary = load(training / "training_summary.json")
        config = load(training / "config.json")
        checkpoint = training / "checkpoints" / "final.zip"
        if summary.get("status") not in ({"completed", "interrupted"} if stopped else {"completed"}):
            raise RuntimeError("The training segment did not finish successfully")
        if not summary.get("all_parameters_finite"):
            raise RuntimeError("The training segment contains non-finite parameters")
        for field, earlier in (("base_num_timesteps", "num_timesteps"), ("base_optimizer_steps", "optimizer_steps")):
            if summary.get(field) != previous[earlier] or config.get(field) != previous[earlier]:
                raise RuntimeError(f"Training continuation counter mismatch: {field}")
        if summary.get("policy_sha256_before") != previous["policy_sha256"]:
            raise RuntimeError("The next segment did not start from its recorded predecessor policy")
        if not stopped and (summary.get("optimizer_steps_this_run", 0) <= 0 or summary.get("changed_parameter_tensors", 0) <= 0 or summary.get("policy_sha256_before") == summary.get("policy_sha256_after")):
            raise RuntimeError("The training segment did not produce verifiable learning updates")
        if not same_number(config.get("reward_scale"), self.plan["reward_scale"]) or config.get("hyperparameter_overrides") != {}:
            raise RuntimeError("Training reward scale or parameter overrides changed")
        verify_parameters(config.get("hyperparameters", {}), self.plan["expected_hyperparameters"], "Recorded training hyperparameters")
        if within(self.root, config["args"]["resume"]) != previous_model:
            raise RuntimeError("The trainer resumed a different checkpoint")
        if config.get("effective_seed") != previous["effective_seed"]:
            raise RuntimeError("The trainer changed the saved seed")
        if config.get("args", {}).get("max_seconds") != self.plan["chunk_seconds"]:
            raise RuntimeError("The trainer changed the planned segment time")
        metadata = self.checkpoint_metadata(checkpoint)
        if not metadata["all_parameters_finite"] or metadata["policy_sha256"] != summary["policy_sha256_after"]:
            raise RuntimeError("Saved checkpoint weights do not match the training summary")
        if metadata["num_timesteps"] != summary["timesteps"] or metadata["optimizer_steps"] != summary["optimizer_steps"]:
            raise RuntimeError("Saved checkpoint counters do not match the training summary")
        if summary["optimizer_steps_this_run"] != metadata["optimizer_steps"] - previous["optimizer_steps"]:
            raise RuntimeError("Optimizer-update accounting is inconsistent")
        if summary["decisions_this_run"] != metadata["num_timesteps"] - previous["num_timesteps"]:
            raise RuntimeError("Training-decision accounting is inconsistent")
        verify_parameters(metadata["hyperparameters"], self.plan["expected_hyperparameters"], "Saved checkpoint hyperparameters")
        elapsed = float(summary["elapsed_seconds"])
        if not math.isfinite(elapsed) or elapsed < 0 or elapsed > self.plan["chunk_seconds"] + 30:
            raise RuntimeError("Training segment exceeded its callback timer allowance")
        self.verify_sources()
        return summary, metadata

    def stage(self, index: int, model: Path, previous: dict) -> tuple[Path, dict]:
        self.check_stop()
        self.verify_sources()
        if self.rel(model) != self.manifest["latest_checkpoint"] or digest(model) != self.manifest["latest_checkpoint_sha256"]:
            raise RuntimeError("The preceding checkpoint changed before the next training segment")
        stage_id = f"{index:02d}_stage"
        training = self.run / "training" / stage_id
        if training.exists():
            raise RuntimeError("Training directories must be new")
        self.manifest.update(active_stage=stage_id, active_training_dir=self.rel(training))
        self.persist()
        command = [
            self.py, "train.py", "--run-dir", self.rel(training), "--resume", self.rel(model),
            "--reward-scale", str(self.plan["reward_scale"]), "--device", "cpu", "--threads", "1",
            "--n-envs", "4", "--max-decisions", "3000", "--max-seconds", str(self.plan["chunk_seconds"]),
            "--checkpoint-seconds", "60", "--archive-seconds", "0",
        ]
        code, reason = run_process(command, self.root, self.run / "logs" / (stage_id + "_training.log"), self.plan["chunk_seconds"] + 90, self.stop_file)
        stopped = reason == "stop_requested" or self.stop_file.exists()
        if stopped and not (training / "training_summary.json").is_file():
            raise StopRequested("Stopped before a training summary was saved; inspect the segment's checkpoint and log")
        if reason not in (None, "stop_requested") or code and not stopped:
            raise RuntimeError(f"Training {stage_id} failed: code {code}; {reason or 'see log'}")
        summary, metadata = self.verify_training(training, previous, model, stopped)
        checkpoint = training / "checkpoints" / "final.zip"
        self.manifest["elapsed_training_seconds"] += summary["elapsed_seconds"]
        self.manifest.update(latest_checkpoint=self.rel(checkpoint), latest_checkpoint_sha256=digest(checkpoint))
        self.manifest["pending_stage"] = {
            "id": stage_id, "training_summary_path": self.rel(training / "training_summary.json"),
            "checkpoint_path": self.rel(checkpoint), "checkpoint_sha256": digest(checkpoint),
            "status": "evaluation_pending",
        }
        metrics = training / "logs" / "progress.csv"
        if metrics.is_file():
            shutil.copy2(metrics, training / "learning_metrics.csv")
        self.persist()
        if stopped:
            raise StopRequested("Training stopped gracefully; its saved checkpoint remains available")
        evaluation_dir = self.run / "stages" / stage_id
        self.evaluate(checkpoint, evaluation_dir, self.plan["validation_seeds"], self.plan["validation_video_seeds"], stage_id + "_validation")
        self.manifest["stages"].append({
            "id": stage_id,
            "label": f"Stage {index}: {self.manifest['elapsed_training_seconds'] / 60:.0f} additional min",
            "elapsed_training_seconds": self.manifest["elapsed_training_seconds"],
            "training_timesteps": summary["timesteps"],
            "evaluation_path": self.rel(evaluation_dir / "evaluation.json"),
            "checkpoint_path": self.rel(checkpoint), "checkpoint_sha256": digest(checkpoint),
            "training_summary_path": self.rel(training / "training_summary.json"),
        })
        self.manifest.pop("pending_stage", None)
        self.manifest.update(active_stage=None, active_training_dir=None)
        self.persist()
        self.render()
        self.publish()
        print(json.dumps({"stage": stage_id, "training_minutes": self.manifest["elapsed_training_seconds"] / 60, "timesteps": summary["timesteps"]}), flush=True)
        return checkpoint, metadata

    def select_candidate(self) -> Path:
        self.check_stop()
        self.verify_sources()
        ranking = []
        for stage in self.manifest["stages"][1:]:
            data = load(within(self.root, stage["evaluation_path"]))
            if data.get("status") != "complete" or data["protocol"]["seeds"] != self.plan["validation_seeds"]:
                raise RuntimeError("Candidate selection requires complete planned validation trials")
            ranking.append({
                "stage_id": stage["id"], "checkpoint_path": stage["checkpoint_path"],
                "checkpoint_sha256": stage["checkpoint_sha256"],
                "validation_completions": data["level_completions"], "validation_trials": len(data["episodes"]),
                "mean_max_x": data["mean_max_x"], "mean_native_reward": data["mean_native_reward"],
            })
        if len(ranking) != self.plan["max_chunks"]:
            raise RuntimeError("All four planned training stages must be evaluated before selection")
        ranking.sort(key=lambda item: (-item["validation_completions"], -item["mean_max_x"], -item["mean_native_reward"], item["stage_id"]))
        chosen = ranking[0]
        model = within(self.root, chosen["checkpoint_path"])
        if digest(model) != chosen["checkpoint_sha256"]:
            raise RuntimeError("The selected checkpoint changed after validation")
        for name in ("baseline_audit", "candidate_audit"):
            if (self.run / name).exists():
                raise RuntimeError("Final test artifacts already exist before candidate selection")
        selection_path = self.run / "selection.json"
        if selection_path.exists():
            raise RuntimeError("A candidate selection already exists")
        selection = {
            "selected_at": utc(), "rule": self.manifest["selection_rule"],
            "validation_seeds": self.plan["validation_seeds"], "holdout_seeds": self.plan["holdout_seeds"],
            "holdouts_evaluated_at_selection": False,
            "selected_stage_id": chosen["stage_id"], "selected_checkpoint": chosen["checkpoint_path"],
            "selected_checkpoint_sha256": chosen["checkpoint_sha256"], "ranking": ranking,
        }
        save(selection_path, selection)
        self.manifest.update(
            selected_stage_id=chosen["stage_id"], selected_checkpoint=chosen["checkpoint_path"],
            selected_checkpoint_sha256=chosen["checkpoint_sha256"],
            selection_path=self.rel(selection_path), selection_sha256=digest(selection_path),
            selection_completed_at=selection["selected_at"],
        )
        for stage in self.manifest["stages"]:
            if stage["id"] == chosen["stage_id"]:
                stage["selected_for_demo"] = True
        self.persist()
        self.render()
        self.publish()
        return model

    def verify_selection(self) -> None:
        if digest(within(self.root, self.manifest["selection_path"])) != self.manifest["selection_sha256"]:
            raise RuntimeError("Candidate selection changed after the final test began")
        if digest(within(self.root, self.manifest["selected_checkpoint"])) != self.manifest["selected_checkpoint_sha256"]:
            raise RuntimeError("The selected checkpoint changed after selection")

    def finalize_publication(self) -> None:
        self.render()
        results_published = self.publish()
        if not self.publish_enabled:
            return
        try:
            if not results_published:
                raise RuntimeError("Publish source and results before creating the model release; retry with --finish-only --publish")
            self.execute([self.py, "publish_lesson_models.py", "--manifest", self.rel(self.manifest_path), "--max-seconds", "480"], "models_publication.log", 510)
            self.manifest = load(self.manifest_path)
        except Exception as error:
            self.manifest["model_release_status"] = "pending"
            self.manifest["model_release_error"] = str(error)
            self.persist()
            print("Model publication pending: " + str(error), flush=True)
        self.render()
        self.publish()

    def finish_only(self) -> int:
        self.manifest = load(self.manifest_path)
        if self.manifest.get("status") != "completed":
            raise RuntimeError("--finish-only requires an already completed experiment; it never resumes training or evaluation")
        if self.manifest.get("experiment_plan_sha256") != self.plan_hash:
            raise RuntimeError("The completed experiment plan has changed")
        self.finalize_publication()
        print(json.dumps({"status": "completed", "mode": "finish-only", "manifest": self.rel(self.manifest_path), "training_started": False, "evaluations_started": False}), flush=True)
        return 0

    def run_experiment(self) -> int:
        if self.manifest_path.exists() or any((self.run / name).exists() for name in ("stages", "training", "selection.json", "baseline_audit", "candidate_audit")):
            raise RuntimeError("Existing experiments are not restarted or overwritten; completed runs may use --finish-only")
        self.check_stop()
        self.verify_sources()
        self.verify_fresh_seeds()
        initial = self.checkpoint_metadata(self.baseline)
        if not initial["all_parameters_finite"]:
            raise RuntimeError("The baseline contains non-finite parameters")
        verify_parameters(initial["hyperparameters"], self.plan["expected_hyperparameters"], "Baseline hyperparameters")
        rule = "Choose one of stages 01–04 by most validation completions, then greatest mean maximum x, then greatest mean native reward; exact ties prefer the earlier stage. The baseline is preserved separately and is not a candidate. Final test results are never used for selection."
        self.manifest = {
            "session_id": self.run.name, "session_dir": self.rel(self.run), "status": "preparing",
            "created_at": utc(), "started_at": utc(), "pid": os.getpid(),
            "experiment_plan_path": self.rel(self.plan_path), "experiment_plan_sha256": self.plan_hash,
            "initial_checkpoint": self.rel(self.baseline), "initial_checkpoint_sha256": self.plan["initial_checkpoint_sha256"],
            "initial_checkpoint_metadata": initial,
            "configuration": {
                "reward_scale": self.plan["reward_scale"], **self.plan["expected_hyperparameters"],
                "training_seed": initial["effective_seed"], "eval_seeds": self.plan["validation_seeds"],
                "chunk_seconds": self.plan["chunk_seconds"], "max_chunks": self.plan["max_chunks"],
                "device": "cpu", "threads": 1, "n_envs": 4,
            },
            "source_hashes": self.plan["source_hashes"], "stages": [], "elapsed_training_seconds": 0.0,
            "planned_training_seconds": self.plan["max_chunks"] * self.plan["chunk_seconds"],
            "budget_note": "The four learning callback timers each allow 900 seconds. Evaluation, loading, checkpoint saving, reporting, and publication add wall time. Timer checks and final saving may cause a small measured overrun.",
            "interpretation": "Continue the existing policy and optimizer with the same reward and hyperparameters. Twenty repeated validation action seeds describe each stage and select one candidate. The baseline and selected candidate then receive the same 100 fresh stochastic action seeds on World 1-1. These seeds change sampled moves, not level layouts.",
            "continuation_note": "The checkpoint retains PPO weights, optimizer, counters, and saved seed. Emulator state, exact RNG state, and partial rollouts are not restored; each segment reseeds from the saved seed.",
            "selection_rule": rule,
            "validation_seeds": self.plan["validation_seeds"], "holdout_seeds": self.plan["holdout_seeds"],
            "diagnostic_report_path": self.rel(self.run / "diagnostics" / "README.md"),
            "comparison_report_path": self.rel(self.run / "README.md"),
            "latest_checkpoint": self.rel(self.baseline), "latest_checkpoint_sha256": self.plan["initial_checkpoint_sha256"],
            "completion_reason": None, "active_stage": None, "active_training_dir": None, "active_evaluation": None,
        }
        self.persist()
        if sys.platform == "darwin" and shutil.which("caffeinate"):
            self.keep_awake = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
        try:
            baseline_dir = self.run / "stages" / "00_baseline"
            self.evaluate(self.baseline, baseline_dir, self.plan["validation_seeds"], self.plan["validation_video_seeds"], "00_baseline_validation")
            self.manifest["stages"].append({
                "id": "00_baseline", "label": f"Preserved baseline: {initial['num_timesteps']:,} prior decisions",
                "elapsed_training_seconds": 0, "training_timesteps": initial["num_timesteps"],
                "evaluation_path": self.rel(baseline_dir / "evaluation.json"),
                "checkpoint_path": self.rel(self.baseline), "checkpoint_sha256": self.plan["initial_checkpoint_sha256"],
                "training_summary_path": None,
            })
            self.manifest["status"] = "running"
            self.persist()
            self.render()
            self.publish()
            model, metadata = self.baseline, initial
            for index in range(1, self.plan["max_chunks"] + 1):
                model, metadata = self.stage(index, model, metadata)
            selected = self.select_candidate()
            self.verify_selection()
            baseline_audit = self.run / "baseline_audit"
            self.evaluate(self.baseline, baseline_audit, self.plan["holdout_seeds"], self.plan["holdout_video_seeds"], "baseline_final_test")
            self.verify_selection()
            self.manifest["baseline_audit_path"] = self.rel(baseline_audit / "evaluation.json")
            self.persist()
            candidate_audit = self.run / "candidate_audit"
            self.evaluate(selected, candidate_audit, self.plan["holdout_seeds"], self.plan["holdout_video_seeds"], "candidate_final_test")
            self.verify_selection()
            self.manifest["candidate_audit_path"] = self.rel(candidate_audit / "evaluation.json")
            baseline_protocol = load(baseline_audit / "evaluation.json")["protocol"]
            if load(candidate_audit / "evaluation.json")["protocol"] != baseline_protocol:
                raise RuntimeError("Baseline and candidate final-test protocols differ")
            self.verify_sources()
            self.manifest.update(status="completed", completion_reason="four_training_stages_and_paired_final_test_completed", finished_at=utc(), active_stage=None, active_training_dir=None, active_evaluation=None)
        except StopRequested as error:
            self.manifest.update(status="interrupted", completion_reason="stop_requested", error=str(error), finished_at=utc())
        except KeyboardInterrupt:
            self.manifest.update(status="interrupted", completion_reason="keyboard_interrupt", finished_at=utc())
        except Exception as error:
            self.manifest.update(status="failed", completion_reason=str(error), finished_at=utc())
            import traceback
            traceback.print_exc()
        finally:
            if self.keep_awake:
                self.keep_awake.terminate()
                try:
                    self.keep_awake.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.keep_awake.kill()
                    self.keep_awake.wait(timeout=5)
            self.manifest["wall_seconds_before_final_publication"] = round(time.monotonic() - self.started, 3)
            self.persist()
            try:
                if self.manifest["status"] == "completed":
                    self.finalize_publication()
                else:
                    self.render()
                    self.publish()
            except Exception as error:
                save(self.run / "logs" / "final_report_error.json", {"at": utc(), "error": str(error)})
                print("Final presentation pending: " + str(error), flush=True)
        print(json.dumps({"status": self.manifest["status"], "reason": self.manifest["completion_reason"], "manifest": self.rel(self.manifest_path), "training_minutes": self.manifest["elapsed_training_seconds"] / 60}), flush=True)
        return 0 if self.manifest["status"] == "completed" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--finish-only", action="store_true", help="retry reports and publication only; no training or evaluation")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    plan_path = within(root, args.plan)
    if not plan_path.is_relative_to(root / "results") or not plan_path.is_file():
        parser.error("--plan must be an existing file under this repository's results directory")
    cache = root / ".cache"
    cache.mkdir(exist_ok=True)
    with (cache / "lesson_session.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("another classroom session is running")
        lock.seek(0)
        lock.truncate()
        lock.write(str(os.getpid()) + "\n")
        lock.flush()
        experiment = Experiment(root, plan_path, args.publish)
        experiment.validate_plan()
        return experiment.finish_only() if args.finish_only else experiment.run_experiment()


if __name__ == "__main__":
    raise SystemExit(main())
