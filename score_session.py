#!/usr/bin/env python3
"""Run a bounded score experiment; frozen comparisons and publication add wall time."""
from __future__ import annotations

import argparse
import fcntl
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from continue_lesson import (Experiment, StopRequested, digest, load, save, utc,
                             run_process, verify_parameters, within)
from score_report import checked_evaluation, metrics, rank_candidates, SELECTION_RULE
from score_objective import SCORE_REWARD_CONFIG as REWARD


SOURCES = ["score_session.py", "score_report.py", "continue_lesson.py", "train.py",
           "mario_env.py", "score_objective.py", "lesson_eval.py", "lesson_report.py", "live_view.py",
           "watch_training.py", "publish_lesson_models.py", "requirements-lock.txt"]


class ScoreExperiment(Experiment):
    """Reuse audited process, checkpoint, publication, and finalization helpers."""

    def validate_plan(self):
        if self.plan.get("max_chunks") not in range(1, 5) or self.plan.get("chunk_seconds") != 900:
            raise ValueError("Score training requires one to four 900-second stages")
        if self.plan.get("reward_scale") != 1.0 or self.plan.get("score_reward_config") != REWARD:
            raise ValueError("The frozen score objective changed")
        for key, size in (("validation_seeds", 20), ("holdout_seeds", 100)):
            seeds = self.plan[key]
            if len(seeds) != size or len(set(seeds)) != size or any(type(s) is not int or not 0 <= s < 2**32 for s in seeds):
                raise ValueError("Invalid planned seeds: " + key)
        if set(self.plan["validation_seeds"]) & set(self.plan["holdout_seeds"]):
            raise ValueError("Validation and holdout seeds overlap")
        for key, expected in (("validation_video_seeds", 3), ("holdout_video_seeds", 4)):
            seeds = self.plan[key]
            if len(seeds) != expected or len(set(seeds)) != expected or not set(seeds).issubset(self.plan[key.replace("_video", "")]):
                raise ValueError("Invalid preselected videos")
        self.baseline = within(self.root, self.plan["initial_checkpoint"])
        if not self.baseline.is_file() or set(self.plan["source_hashes"]) != set(SOURCES):
            raise ValueError("Missing baseline or frozen source files")
        verify_parameters(self.plan["expected_hyperparameters"], {"learning_rate": 1e-4, "target_kl": .02, "ent_coef": .01}, "Planned hyperparameters")

    def render(self):
        for script in ("score_report.py", "lesson_report.py"):
            self.execute([self.py, script, "--manifest", self.rel(self.manifest_path)], script + ".log", 180)

    def evaluate(self, model, output, seeds, videos, label):
        self.check_stop()
        self.verify_sources()
        expected_hash = digest(model)
        if output.exists():
            raise RuntimeError("Evaluation directories must be new")
        self.manifest["active_evaluation"] = label
        self.persist()
        self.execute([self.py, "lesson_eval.py", "--model", self.rel(model), "--output-dir", self.rel(output),
                      "--seeds", *map(str, seeds), "--video-seeds", *map(str, videos),
                      "--max-decisions", "3000", "--max-seconds", "1800", "--device", "cpu",
                      "--beginning-decisions", "3000", "--ending-decisions", "75", "--stall-decisions", "120"],
                     label + ".log", 1860, stoppable=True)
        data = checked_evaluation(output / "evaluation.json", seeds, expected_hash, videos, verify_traces=True)
        if digest(model) != expected_hash:
            raise RuntimeError("Frozen evaluation modified its checkpoint")
        self.verify_sources()
        self.manifest["active_evaluation"] = None
        self.persist()
        return data

    def stage(self, index, model, previous):
        self.check_stop()
        self.verify_sources()
        if self.rel(model) != self.manifest["latest_checkpoint"] or digest(model) != self.manifest["latest_checkpoint_sha256"]:
            raise RuntimeError("Preceding checkpoint changed before the next stage")
        stage_id = f"{index:02d}_stage"
        training = self.run / "training" / stage_id
        if training.exists():
            raise RuntimeError("Training directories must be new")
        self.manifest.update(active_stage=stage_id, active_training_dir=self.rel(training))
        self.persist()
        command = [self.py, "train.py", "--run-dir", self.rel(training), "--resume", self.rel(model),
                   "--objective", "score", "--reward-scale", "1.0", "--live-preview", "--device", "cpu", "--threads", "1",
                   "--n-envs", "4", "--max-decisions", "3000", "--max-seconds", "900", "--checkpoint-seconds", "60", "--archive-seconds", "0"]
        code, reason = run_process(command, self.root, self.run / "logs" / (stage_id + "_training.log"), 990, self.stop_file)
        stopped = reason == "stop_requested" or self.stop_file.exists()
        if stopped and not (training / "training_summary.json").is_file():
            raise StopRequested("Stopped before the training summary was saved; inspect checkpoints and log")
        if reason not in (None, "stop_requested") or code and not stopped:
            raise RuntimeError(f"Training {stage_id} failed: {code}; {reason or 'see log'}")
        summary, metadata = self.verify_training(training, previous, model, stopped)
        checkpoint = training / "checkpoints" / "final.zip"
        self.manifest["elapsed_training_seconds"] += summary["elapsed_seconds"]
        self.manifest.update(latest_checkpoint=self.rel(checkpoint), latest_checkpoint_sha256=digest(checkpoint))
        self.manifest["pending_stage"] = {"id": stage_id, "training_summary_path": self.rel(training / "training_summary.json"),
                                          "checkpoint_path": self.rel(checkpoint), "checkpoint_sha256": digest(checkpoint), "status": "evaluation_pending"}
        progress = training / "logs" / "progress.csv"
        if progress.is_file():
            shutil.copy2(progress, training / "learning_metrics.csv")
        self.persist()
        if stopped:
            raise StopRequested("Training stopped gracefully; its checkpoint remains available")
        evaluation_dir = self.run / "stages" / stage_id
        self.evaluate(checkpoint, evaluation_dir, self.plan["validation_seeds"], self.plan["validation_video_seeds"], stage_id + "_validation")
        self.manifest["stages"].append({"id": stage_id, "label": f"Stage {index}: {self.manifest['elapsed_training_seconds'] / 60:.0f} additional min",
                                        "elapsed_training_seconds": self.manifest["elapsed_training_seconds"], "training_timesteps": summary["timesteps"],
                                        "evaluation_path": self.rel(evaluation_dir / "evaluation.json"), "checkpoint_path": self.rel(checkpoint),
                                        "checkpoint_sha256": digest(checkpoint), "training_summary_path": self.rel(training / "training_summary.json")})
        self.manifest.pop("pending_stage", None)
        self.manifest.update(active_stage=None, active_training_dir=None)
        self.persist()
        self.render()
        self.publish()
        return checkpoint, metadata

    def verify_training(self, training, previous, previous_model, stopped):
        summary, metadata = super().verify_training(training, previous, previous_model, stopped)
        config = load(training / "config.json")
        if config.get("args", {}).get("objective") != "score":
            raise RuntimeError("Training did not use the declared score objective")
        if config.get("score_reward_config") != self.plan["score_reward_config"]:
            raise RuntimeError("Training score reward configuration differs from the plan")
        return summary, metadata

    def select_candidate(self):
        self.check_stop()
        self.verify_sources()
        entries = []
        for stage in self.manifest["stages"][1:]:
            data = checked_evaluation(within(self.root, stage["evaluation_path"]), self.plan["validation_seeds"], stage["checkpoint_sha256"])
            entries.append({"stage_id": stage["id"], "checkpoint_path": stage["checkpoint_path"],
                            "checkpoint_sha256": stage["checkpoint_sha256"], **metrics(data)})
        if len(entries) != self.plan["max_chunks"]:
            raise RuntimeError("All planned stages must finish before candidate selection")
        ranking, qualified = rank_candidates(entries)
        chosen = ranking[0]
        if any((self.run / p).exists() for p in ("selection.json", "baseline_audit", "candidate_audit")):
            raise RuntimeError("Selection and final-test directories must be new")
        checkpoint = within(self.root, chosen["checkpoint_path"])
        if digest(checkpoint) != chosen["checkpoint_sha256"]:
            raise RuntimeError("Selected checkpoint changed after validation")
        selection = {"selected_at": utc(), "rule": SELECTION_RULE, "validation_seeds": self.plan["validation_seeds"],
                     "holdout_seeds": self.plan["holdout_seeds"], "holdouts_evaluated_at_selection": False,
                     "selected_stage_id": chosen["stage_id"], "selected_checkpoint": chosen["checkpoint_path"],
                     "selected_checkpoint_sha256": chosen["checkpoint_sha256"], "qualified": qualified, "ranking": ranking}
        path = self.run / "selection.json"
        save(path, selection)
        self.manifest.update(selected_stage_id=chosen["stage_id"], selected_checkpoint=chosen["checkpoint_path"],
                             selected_checkpoint_sha256=chosen["checkpoint_sha256"], selected_qualified=qualified,
                             selection_path=self.rel(path), selection_sha256=digest(path), selection_completed_at=selection["selected_at"])
        self.persist()
        self.render()
        self.publish()
        return checkpoint

    def run_experiment(self, show_window=False):
        if self.manifest_path.exists():
            raise RuntimeError("Existing score experiments are never restarted")
        self.verify_sources()
        self.verify_fresh_seeds()
        initial = self.checkpoint_metadata(self.baseline)
        verify_parameters(initial["hyperparameters"], self.plan["expected_hyperparameters"], "Baseline hyperparameters")
        if not initial["all_parameters_finite"]:
            raise RuntimeError("Baseline has non-finite parameters")
        self.manifest = {
            "session_id": self.run.name, "session_dir": self.rel(self.run), "status": "preparing", "objective": "score",
            "created_at": utc(), "started_at": utc(), "pid": os.getpid(), "experiment_plan_path": self.rel(self.plan_path),
            "experiment_plan_sha256": self.plan_hash, "initial_checkpoint": self.rel(self.baseline),
            "initial_checkpoint_sha256": self.plan["initial_checkpoint_sha256"], "initial_checkpoint_metadata": initial,
            "configuration": {**self.plan["expected_hyperparameters"], "objective": "score", "reward_scale": 1.0,
                              "training_seed": initial["effective_seed"], "eval_seeds": self.plan["validation_seeds"],
                              "chunk_seconds": 900, "max_chunks": self.plan["max_chunks"], "device": "cpu", "threads": 1, "n_envs": 4},
            "score_reward_config": REWARD, "source_hashes": self.plan["source_hashes"], "stages": [],
            "elapsed_training_seconds": 0.0, "planned_training_seconds": 900 * self.plan["max_chunks"],
            "budget_note": "Learning is timed in 15-minute stages; loading, evaluation, recordings and publication add wall time. Callback timing may overrun slightly.",
            "interpretation": "A score-focused objective continues the preserved policy and optimizer with the same hyperparameters. Stage validation is reused; final action seeds are reserved until selection. One run does not establish a general causal effect.",
            "continuation_note": "Weights, optimizer and counters resume. Emulator state, RNG state and partial rollouts do not resume exactly.",
            "selection_rule": SELECTION_RULE, "validation_seeds": self.plan["validation_seeds"], "holdout_seeds": self.plan["holdout_seeds"],
            "comparison_report_path": self.rel(self.run / "README.md"), "latest_checkpoint": self.rel(self.baseline),
            "latest_checkpoint_sha256": self.plan["initial_checkpoint_sha256"], "preferred_checkpoint": self.rel(self.baseline),
            "active_stage": None, "active_training_dir": None, "active_evaluation": None, "completion_reason": None,
            "live_view": {"requested": show_window, "training_frames": "active_training_dir/live_frame.json", "closing_stops_training": False}}
        self.persist()
        if sys.platform == "darwin" and shutil.which("caffeinate"):
            self.keep_awake = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
        try:
            self.render()
            if show_window:
                log = self.run / "logs" / "live_window.log"
                log.parent.mkdir(exist_ok=True)
                try:
                    with log.open("a") as stream:
                        window = subprocess.Popen([self.py, "watch_training.py", self.rel(self.run)], cwd=self.root,
                                                  stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                    self.manifest["live_view"]["pid"] = window.pid
                except OSError as error:
                    self.manifest["live_view"]["launch_error"] = str(error)
                self.persist()
            baseline_dir = self.run / "stages" / "00_baseline"
            self.evaluate(self.baseline, baseline_dir, self.plan["validation_seeds"], self.plan["validation_video_seeds"], "00_baseline_validation")
            self.manifest["stages"].append({"id": "00_baseline", "label": "Preserved completion baseline", "elapsed_training_seconds": 0,
                                            "training_timesteps": initial["num_timesteps"], "evaluation_path": self.rel(baseline_dir / "evaluation.json"),
                                            "checkpoint_path": self.rel(self.baseline), "checkpoint_sha256": self.plan["initial_checkpoint_sha256"], "training_summary_path": None})
            self.manifest["status"] = "running"
            self.persist()
            self.render()
            self.publish()
            model, metadata = self.baseline, initial
            for index in range(1, self.plan["max_chunks"] + 1):
                model, metadata = self.stage(index, model, metadata)
            candidate = self.select_candidate()
            for label, checkpoint in (("baseline", self.baseline), ("candidate", candidate)):
                self.verify_selection()
                output = self.run / (label + "_audit")
                self.evaluate(checkpoint, output, self.plan["holdout_seeds"], self.plan["holdout_video_seeds"], label + "_final_test")
                self.manifest[label + "_audit_path"] = self.rel(output / "evaluation.json")
                self.persist()
            self.verify_selection()
            baseline_data = load(self.run / "baseline_audit" / "evaluation.json")
            candidate_data = load(self.run / "candidate_audit" / "evaluation.json")
            if baseline_data["protocol"] != candidate_data["protocol"]:
                raise RuntimeError("Final evaluation protocols differ")
            if self.manifest["selected_qualified"] and candidate_data["level_completions"] >= 95 and metrics(candidate_data)["mean_completed_score"] > metrics(baseline_data)["mean_completed_score"]:
                self.manifest["preferred_checkpoint"] = self.rel(candidate)
            self.verify_sources()
            self.manifest.update(status="completed", completion_reason="all_score_stages_and_paired_final_test_completed", finished_at=utc())
        except (StopRequested, KeyboardInterrupt) as error:
            self.manifest.update(status="interrupted", completion_reason=str(error) or "keyboard_interrupt", finished_at=utc())
        except Exception as error:
            self.manifest.update(status="failed", completion_reason=str(error), finished_at=utc())
            import traceback
            traceback.print_exc()
        finally:
            if self.keep_awake:
                self.keep_awake.terminate()
                self.keep_awake.wait(timeout=5)
            self.manifest.update(active_stage=None, active_training_dir=None, active_evaluation=None,
                                 wall_seconds_before_final_publication=round(time.monotonic() - self.started, 3))
            self.persist()
            try:
                if self.manifest["status"] == "completed":
                    self.finalize_publication()
                else:
                    self.render()
                    self.publish()
            except Exception as error:
                save(self.run / "logs" / "final_report_error.json", {"at": utc(), "error": str(error)})
        print(self.manifest["status"] + ": " + self.rel(self.manifest_path), flush=True)
        return 0 if self.manifest["status"] == "completed" else 1


def create_plan(root, run, args):
    # Source must be reviewable in Git before a run publishes experiment artifacts.
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--", *SOURCES], cwd=root, text=True)
    if dirty:
        raise RuntimeError("Commit the score experiment source files before starting")
    baseline = within(root, args.initial_model)
    previous = load(root / "results/teaching_20260920/manifest.json")
    expected = previous["initial_checkpoint_metadata"]["hyperparameters"]
    plan = {"created_at": utc(), "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
            "source_hashes": {name: digest(root / name) for name in SOURCES},
            "initial_checkpoint": str(baseline.relative_to(root)), "initial_checkpoint_sha256": digest(baseline),
            "score_reward_config": REWARD, "reward_scale": 1.0, "chunk_seconds": 900, "max_chunks": args.minutes // 15,
            "expected_hyperparameters": expected, "validation_seeds": list(range(args.seed_base + 101, args.seed_base + 121)),
            "validation_video_seeds": [args.seed_base + i for i in (101, 110, 120)],
            "holdout_seeds": list(range(args.seed_base + 201, args.seed_base + 301)),
            "holdout_video_seeds": [args.seed_base + i for i in (201, 234, 267, 300)],
            "selection_rule": SELECTION_RULE, "max_decisions": 3000, "evaluation_max_seconds": 1800,
            "evaluation_policy": "frozen stochastic actions; same World 1-1 start; no learning",
            "promotion_rule": "Validation-qualified candidate, at least 95/100 holdout clears and greater mean completed score (failed attempts count zero); otherwise preserve baseline preference",
            "primary_metric": "mean_completed_score", "score_measurement": "HUD points at flag/episode end, before later time-bonus conversion",
            "limits": "RIGHT_ONLY actions cannot backtrack; no claim of global maximum score or generalization to other levels"}
    save(run / "experiment_plan.json", plan)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=Path("results/teaching_score_20260921"))
    parser.add_argument("--initial-model", type=Path, default=Path("results/teaching_20260920/training/03_stage/checkpoints/final.zip"))
    parser.add_argument("--minutes", type=int, choices=(15, 30, 45, 60), default=15)
    parser.add_argument("--seed-base", type=int, default=7000)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--show-window", action="store_true")
    parser.add_argument("--finish-only", action="store_true", help="retry reports/release only; never training or evaluation")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    run = within(root, args.run_dir)
    if not run.is_relative_to(root / "results") or run == root / "results" or not 0 <= args.seed_base <= 2**32 - 301:
        parser.error("Choose a new results subdirectory and a valid seed base")
    (root / ".cache").mkdir(exist_ok=True)
    with (root / ".cache" / "lesson_session.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Another classroom session is running")
        if not args.finish_only:
            run.mkdir(parents=True, exist_ok=False)
            create_plan(root, run, args)
        experiment = ScoreExperiment(root, run / "experiment_plan.json", args.publish)
        experiment.validate_plan()
        return experiment.finish_only() if args.finish_only else experiment.run_experiment(args.show_window)


if __name__ == "__main__":
    raise SystemExit(main())
