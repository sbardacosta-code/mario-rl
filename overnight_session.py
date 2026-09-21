#!/usr/bin/env python3
"""One bounded overnight experiment, with a separate process-tree deadline watchdog."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone, timedelta
import fcntl
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import psutil
from continue_lesson import Experiment, StopRequested, digest, load, save, utc, verify_parameters, within
from overnight_report import best_stage, checked_evaluation, metrics, qualified, ranking_key


SOURCES = ["overnight_session.py", "overnight_report.py", "overnight_env.py", "overnight_train.py", "overnight_eval.py", "mario_events.py",
           "overnight_gallery.py", "overnight_live.py", "overnight_watch.py",
           "continue_lesson.py", "train.py", "mario_env.py", "score_objective.py", "lesson_report.py", "live_view.py",
           "watch_training.py", "publish_lesson_models.py", "requirements-lock.txt"]
PURE = {"objective": "score_events", "score_weight": 1.0, "learning_rate": 2.5e-5, "target_kl": .01, "ent_coef": .003}
BRIDGE = {**PURE, "objective": "score_bridge", "score_weight": .25}


class DeadlineReached(Exception):
    pass


class CommandTimeout(RuntimeError):
    pass


class EvaluationIncomplete(RuntimeError):
    pass


def parse_time(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Deadline must include its timezone")
    return result.timestamp()


def watchdog(parent_pid, parent_created, deadline, registry):
    """Retain process identities, including detached children; never kill reused PIDs."""
    tracked = {}
    interrupted = False
    self_pid = os.getpid()
    result_path = registry.with_name("deadline_watchdog_result.json")
    while True:
        parent = None
        try:
            candidate = psutil.Process(parent_pid)
            if candidate.create_time() == parent_created:
                parent = candidate
        except psutil.Error:
            pass
        state = load(registry) if registry.exists() else {}
        if state.get("finished"):
            save(result_path, {"status": "normal_exit", "at": utc()})
            return 0
        roots = ([parent] if parent else [])
        for item in state.get("children", []):
            try:
                process = psutil.Process(item["pid"])
                if process.create_time() == item["created"]:
                    roots.append(process)
            except psutil.Error:
                pass
        for process in roots:
            try:
                if process.pid != self_pid: tracked[(process.pid, process.create_time())] = process
            except psutil.Error:
                pass
            try:
                for child in [process, *process.children(recursive=True)]:
                    if child.pid != self_pid:
                        tracked[(child.pid, child.create_time())] = child
            except (psutil.Error, OSError):
                pass
        # If the runner disappears unexpectedly, stop orphaned work immediately.
        remaining = deadline - time.time()
        if parent is None:
            remaining = min(remaining, 0)
        if remaining <= 10 and not interrupted:
            for process in reversed(list(tracked.values())):
                try:
                    if process.is_running(): process.send_signal(signal.SIGINT)
                except psutil.Error:
                    pass
            interrupted = True
        if remaining <= 0:
            killed = []
            for process in reversed(list(tracked.values())):
                try:
                    if process.is_running(): process.kill(); killed.append(process.pid)
                except psutil.Error:
                    pass
            save(result_path, {"status": "hard_deadline" if parent else "orphan_cleanup", "at": utc(), "killed_pids": killed})
            return 0
        time.sleep(min(.5, max(.01, remaining)))


class OvernightExperiment(Experiment):
    def __init__(self, root, plan_path, publish):
        super().__init__(root, plan_path, publish)
        self.deadline = parse_time(self.plan["deadline_utc"])
        self.cutoff = self.deadline - self.plan["final_reserve_seconds"]
        self.registry = self.run / "logs" / "deadline_registry.json"
        self.children = []
        self.guard = None
        self.monotonic_deadline = time.monotonic() + self.deadline - time.time()
        self.baseline = within(root, self.plan["initial_checkpoint"])

    def remaining(self, phase="final"):
        seconds = min(self.deadline - time.time(), self.monotonic_deadline - time.monotonic())
        return seconds - (self.plan["final_reserve_seconds"] if phase == "learning" else 10)

    def validate_plan(self):
        if not 0 < self.plan["wall_budget_seconds"] <= 21600 or self.plan["final_reserve_seconds"] != 2700:
            raise ValueError("Wall budget must be no more than six hours with 45 minutes reserved")
        if self.plan["chunk_seconds"] != 900 or not 1 <= self.plan["max_chunks"] <= 20:
            raise ValueError("Learning stages must be bounded to 15 minutes")
        from overnight_env import EVENT_REWARD_CONFIG
        if self.plan["event_reward_config"] != EVENT_REWARD_CONFIG:
            raise ValueError("Frozen event reward configuration differs")
        seeds = self.plan["validation_seeds"] + self.plan["holdout_seeds"]
        for group in self.plan["confirmation_seed_bank"]:
            if len(group) != 20: raise ValueError("Confirmation checks require 20 paired seeds")
            seeds += group
        if len(self.plan["validation_seeds"]) != 20 or len(self.plan["holdout_seeds"]) != 100 or len(set(seeds)) != len(seeds):
            raise ValueError("Evaluation seeds must have the planned sizes and no overlaps")
        if any(type(seed) is not int or not 0 <= seed < 2**32 for seed in seeds):
            raise ValueError("Invalid seed")
        if not self.baseline.is_file(): raise ValueError("Preserved baseline missing")

    def verify_fresh_seeds(self):
        planned = set(self.plan["validation_seeds"] + self.plan["holdout_seeds"])
        planned.update(seed for group in self.plan["confirmation_seed_bank"] for seed in group)
        for path in (self.root / "results").rglob("evaluation.json"):
            overlap = planned & set(load(path).get("protocol", {}).get("seeds", []))
            if overlap: raise RuntimeError("Evaluation seeds were already used: " + str(path))

    def update_registry(self, finished=False):
        save(self.registry, {"parent": os.getpid(), "children": self.children, "finished": finished, "deadline_utc": self.plan["deadline_utc"]})

    def launch_guard(self):
        # Descendant discovery is required, not an optional best-effort protection.
        psutil.Process().children(recursive=True)
        self.update_registry()
        self.guard = subprocess.Popen([self.py, str(self.root / "overnight_session.py"), "--watchdog-parent", str(os.getpid()),
                                       "--watchdog-created", str(psutil.Process().create_time()), "--watchdog-deadline", str(self.deadline),
                                       "--watchdog-registry", str(self.registry)], cwd=self.root, start_new_session=True,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def child(self, command, log_name, timeout, phase="final", stoppable=False, check=True):
        if stoppable: self.check_stop()
        allowance = min(timeout, self.remaining(phase))
        if allowance <= 1: raise DeadlineReached("Reserved phase deadline reached")
        log = self.run / "logs" / log_name; log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a+") as stream:
            stream.seek(0, 2); offset = stream.tell()
            process = subprocess.Popen(command, cwd=self.root, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            identity = {"pid": process.pid, "created": psutil.Process(process.pid).create_time()}
            self.children.append(identity); self.update_registry()
            end = time.monotonic() + allowance
            reason = None
            try:
                while process.poll() is None:
                    if stoppable and self.stop_file.exists(): reason = "stop_requested"
                    elif time.monotonic() >= end or self.remaining(phase) <= 0: reason = "deadline_or_timeout"
                    if reason:
                        os.killpg(process.pid, signal.SIGINT)
                        try: process.wait(timeout=min(8, max(.1, self.remaining("final"))))
                        except subprocess.TimeoutExpired: os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=2)
                        break
                    time.sleep(.25)
            except BaseException:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGINT)
                    try: process.wait(timeout=3)
                    except subprocess.TimeoutExpired: os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=2)
                raise
            finally:
                self.children.remove(identity); self.update_registry()
            stream.seek(offset); output = stream.read()
        if reason == "stop_requested": raise StopRequested("STOP file requested")
        if reason:
            if self.remaining(phase) <= 1: raise DeadlineReached("Reserved phase deadline reached: " + log_name)
            raise CommandTimeout("Subprocess time limit reached: " + log_name)
        if check and process.returncode: raise RuntimeError(f"{log_name}: exit {process.returncode}; inspect retained log")
        return subprocess.CompletedProcess(command, process.returncode, output, "")

    def execute(self, command, log_name, timeout, stoppable=False):
        return self.child(command, log_name, timeout, stoppable=stoppable)

    def render(self):
        for script in ("overnight_report.py", "overnight_gallery.py"):
            self.child([self.py, script, "--manifest", self.rel(self.manifest_path)], script + ".log", 90)

    def publish(self):
        if not self.publish_enabled: return True
        relative = self.rel(self.run)
        def git(*args, timeout=45): return self.child(["git", *args], "git_publication.log", timeout).stdout
        try:
            if git("branch", "--show-current").strip() != "main": raise RuntimeError("Publication requires main")
            allowed = lambda path: path.startswith(relative + "/") or path.startswith("docs/aula/")
            if any(path and not allowed(path) for path in git("diff", "--cached", "--name-only", "-z").split("\0")):
                raise RuntimeError("Unrelated staged changes preserved; publication deferred")
            git("add", "--", relative, "docs/aula")
            if git("diff", "--cached", "--name-only").strip():
                git("diff", "--cached", "--check")
                git("commit", "-m", f"Record overnight Mario session {self.run.name}: {self.manifest['status']} ({len(self.manifest['stages'])} stages)")
            git("push", "origin", "main", timeout=75)
            commit = git("rev-parse", "HEAD").strip()
            remote = git("ls-remote", "origin", "refs/heads/main").split()
            if not remote or remote[0] != commit: raise RuntimeError("Published remote SHA differs")
            save(self.run / "logs/publication.json", {"status": "published", "commit": commit, "at": utc()})
            return True
        except (RuntimeError, DeadlineReached) as error:
            save(self.run / "logs/publication.json", {"status": "pending", "error": str(error), "at": utc()})
            return False

    def evaluate(self, checkpoint, output, seeds, videos, label, final=False):
        self.verify_sources(); self.check_stop()
        if output.exists(): raise RuntimeError("Evaluation directory already exists")
        digest_before = digest(checkpoint)
        phase = "final" if final else "learning"
        # Divide the reserved allowance before the first test; keep publication time.
        final_allowance = (self.remaining("final") - 300) / (2 if "baseline" in label else 1)
        budget = min(1800 if final else 600, final_allowance if final else self.remaining(phase) - 15)
        if budget <= 10: raise DeadlineReached("Insufficient time for evaluation")
        self.manifest["active_evaluation"] = label; self.persist()
        try:
            self.child([self.py, "overnight_eval.py", "--model", self.rel(checkpoint), "--output-dir", self.rel(output),
                        "--seeds", *map(str, seeds), "--video-seeds", *map(str, videos), "--max-decisions", "3000",
                        "--max-seconds", str(budget), "--device", "cpu", "--beginning-decisions", "3000",
                        "--ending-decisions", "75", "--stall-decisions", "120"], label + ".log", budget + 10, phase, True)
        except (RuntimeError, CommandTimeout) as error:
            self.verify_sources()
            if digest(checkpoint) != digest_before: raise RuntimeError("Checkpoint changed during failed evaluation") from error
            report = output / "evaluation.json"
            if not final and report.is_file() and load(report).get("status") in {"incomplete", "interrupted"}:
                raise EvaluationIncomplete("Evaluation stopped before every planned trial; no aggregate is eligible: " + label) from error
            raise
        data = checked_evaluation(output / "evaluation.json", seeds, digest_before, videos, self.plan["event_reward_config"])
        if digest(checkpoint) != digest_before: raise RuntimeError("Evaluation modified checkpoint")
        self.manifest["active_evaluation"] = None; self.persist(); self.verify_sources()
        return data

    def verify_segment(self, training, previous, predecessor, configuration):
        summary, config = load(training / "training_summary.json"), load(training / "config.json")
        if summary.get("status") != "completed" or not summary.get("all_parameters_finite"):
            raise RuntimeError("Training did not finish with finite parameters")
        for key, previous_key in (("base_num_timesteps", "num_timesteps"), ("base_optimizer_steps", "optimizer_steps")):
            if summary.get(key) != previous[previous_key] or config.get(key) != previous[previous_key]: raise RuntimeError("Continuation counter mismatch")
        if summary["policy_sha256_before"] != previous["policy_sha256"] or summary["policy_sha256_before"] == summary["policy_sha256_after"]:
            raise RuntimeError("Predecessor policy mismatch or no learned change")
        overrides = {key: configuration[key] for key in ("learning_rate", "target_kl", "ent_coef")}
        if config.get("hyperparameter_overrides") != overrides or config.get("reward_scale") != 1.0:
            raise RuntimeError("Hyperparameter overrides or reward scale differ from plan")
        if config.get("objective") != configuration["objective"] or config.get("score_weight") != configuration["score_weight"] or config.get("event_reward_config") != self.plan["event_reward_config"]:
            raise RuntimeError("Event objective configuration differs")
        if config.get("regression_guard") != self.plan["regression_guard"]:
            raise RuntimeError("Early regression guard differs from plan")
        if within(self.root, config["args"]["resume"]) != predecessor or config.get("effective_seed") != previous["effective_seed"]:
            raise RuntimeError("Predecessor path or saved RNG seed differs")
        expected = {key: value for key, value in previous["hyperparameters"].items() if key != "learning_rate_schedule"}
        expected.update(overrides)
        verify_parameters(config["hyperparameters"], expected, "Effective hyperparameters")
        metadata = self.checkpoint_metadata(training / "checkpoints/final.zip")
        verify_parameters(metadata["hyperparameters"], expected, "Saved hyperparameters")
        if not metadata["all_parameters_finite"] or metadata["policy_sha256"] != summary["policy_sha256_after"]:
            raise RuntimeError("Checkpoint does not match finite learned weights")
        for key, field, old in (("optimizer_steps_this_run", "optimizer_steps", "optimizer_steps"), ("decisions_this_run", "timesteps", "num_timesteps")):
            current = metadata["optimizer_steps" if key.startswith("optimizer") else "num_timesteps"]
            if summary[field] != current or summary[key] != current - previous[old] or summary[key] <= 0: raise RuntimeError("Learning update accounting mismatch")
        if summary.get("changed_parameter_tensors", 0) <= 0 or not math.isfinite(summary["elapsed_seconds"]) or not 0 < summary["elapsed_seconds"] <= 930:
            raise RuntimeError("Invalid learned change or stage duration")
        if config["args"]["max_seconds"] != 900: raise RuntimeError("Stage budget changed")
        return summary, metadata

    def stage(self, index, predecessor, configuration):
        self.check_stop(); self.verify_sources()
        if self.remaining("learning") < 900 + 600 + 30: raise DeadlineReached("No room for a full stage and validation before the reserve")
        stage_id = f"{index:02d}_stage"; training = self.run / "training" / stage_id
        if training.exists(): raise RuntimeError("Training directory already exists")
        previous = self.checkpoint_metadata(predecessor)
        self.manifest.update(active_stage=stage_id, active_training_dir=self.rel(training)); self.persist()
        command = [self.py, "overnight_train.py", "--run-dir", self.rel(training), "--resume", self.rel(predecessor),
                   "--objective", configuration["objective"], "--score-weight", str(configuration["score_weight"]),
                   "--learning-rate", str(configuration["learning_rate"]), "--target-kl", str(configuration["target_kl"]),
                   "--ent-coef", str(configuration["ent_coef"]), "--reward-scale", "1", "--device", "cpu", "--threads", "1", "--n-envs", "4",
                   "--max-decisions", "3000", "--max-seconds", "900", "--checkpoint-seconds", "60", "--archive-seconds", "0", "--live-preview",
                   "--deadline-utc", datetime.fromtimestamp(self.cutoff, timezone.utc).isoformat()]
        self.child(command, stage_id + "_training.log", 960, "learning", True)
        summary, metadata = self.verify_segment(training, previous, predecessor, configuration)
        checkpoint = training / "checkpoints/final.zip"
        self.manifest["elapsed_training_seconds"] += summary["elapsed_seconds"]
        self.manifest.update(latest_checkpoint=self.rel(checkpoint), latest_checkpoint_sha256=digest(checkpoint))
        entry = {"id": stage_id, "index": index, "label": f"Stage {index}: {self.manifest['elapsed_training_seconds'] / 60:.1f} min learned",
                 "elapsed_training_seconds": self.manifest["elapsed_training_seconds"], "training_timesteps": metadata["num_timesteps"],
                 "checkpoint_path": self.rel(checkpoint), "checkpoint_sha256": digest(checkpoint),
                 "training_summary_path": self.rel(training / "training_summary.json"), "training_configuration": configuration,
                 "resumed_checkpoint": self.rel(predecessor), "stop_reason": summary.get("stop_reason"),
                 "evaluation_path": self.rel(self.run / "stages" / stage_id / "evaluation.json"), "decision": "Validation pending"}
        self.manifest["stages"].append(entry); self.persist()
        progress = training / "logs/progress.csv"
        if progress.exists():
            import shutil; shutil.copy2(progress, training / "learning_metrics.csv")
        data = self.evaluate(checkpoint, self.run / "stages" / stage_id, self.plan["validation_seeds"], self.plan["validation_video_seeds"], stage_id + "_validation")
        self.manifest.update(active_stage=None, active_training_dir=None); self.persist()
        return {**entry, **metrics(data)}

    def confirm(self, candidate, reference):
        number = len(self.manifest["confirmation_checks"])
        if number >= len(self.plan["confirmation_seed_bank"]) or self.remaining("learning") < 2 * 600 + 30:
            return None
        seeds = self.plan["confirmation_seed_bank"][number]
        output = self.run / "confirmations" / candidate["id"]
        results = {}
        for label, row in (("candidate", candidate), ("reference", reference)):
            data = self.evaluate(within(self.root, row["checkpoint_path"]), output / label, seeds, [], candidate["id"] + "_confirmation_" + label)
            results[label] = metrics(data)
        bad = not qualified(results["candidate"]) or results["candidate"]["mean_completed_augmented_score"] < results["reference"]["mean_completed_augmented_score"]
        record = {"stage_id": candidate["id"], "seeds": seeds, **results, "confirmed_regression": bad,
                  "decision": "Confirmed regression; roll back to best" if bad else "Regression not confirmed; keep selection based on original validation", "record_path": self.rel(output / "comparison.json")}
        save(output / "comparison.json", record); self.manifest["confirmation_checks"].append(record); self.persist()
        return bad

    def freeze_selection(self, rows):
        self.verify_sources()
        chosen = best_stage(rows)
        if any((self.run / name).exists() for name in ("selection.json", "baseline_audit", "candidate_audit")):
            raise RuntimeError("Selection or holdouts already exist")
        selection = {"selected_at": utc(), "selected_stage_id": chosen["id"], "selected_checkpoint": chosen["checkpoint_path"],
                     "selected_checkpoint_sha256": chosen["checkpoint_sha256"], "holdouts_evaluated_at_selection": False,
                     "validation_seeds": self.plan["validation_seeds"], "holdout_seeds": self.plan["holdout_seeds"],
                     "ranking": sorted(rows, key=ranking_key, reverse=True), "rule": self.plan["selection_rule"]}
        save(self.run / "selection.json", selection)
        self.manifest.update(selected_stage_id=chosen["id"], selected_checkpoint=chosen["checkpoint_path"],
                             selected_checkpoint_sha256=chosen["checkpoint_sha256"], selection_path=self.rel(self.run / "selection.json"),
                             selection_sha256=digest(self.run / "selection.json")); self.persist()
        return chosen

    def run_experiment(self, show_window=False):
        if self.manifest_path.exists(): raise RuntimeError("Existing experiments are never restarted")
        self.launch_guard(); self.verify_sources(); self.verify_fresh_seeds()
        initial = self.checkpoint_metadata(self.baseline)
        self.manifest = {"session_id": self.run.name, "session_dir": self.rel(self.run), "status": "preparing", "objective": "overnight_events",
                         "created_at": utc(), "started_at": self.plan["launched_at"], "deadline_utc": self.plan["deadline_utc"], "pid": os.getpid(),
                         "experiment_plan_path": self.rel(self.plan_path), "experiment_plan_sha256": self.plan_hash,
                         "initial_checkpoint": self.rel(self.baseline), "initial_checkpoint_sha256": digest(self.baseline), "initial_checkpoint_metadata": initial,
                         "configuration": {**BRIDGE, "reward_scale": 1.0, "eval_seeds": self.plan["validation_seeds"], "chunk_seconds": 900, "training_seed": initial["effective_seed"]},
                         "source_hashes": self.plan["source_hashes"], "event_reward_config": self.plan["event_reward_config"], "stages": [],
                         "failed_attempts": [], "confirmation_checks": [], "adaptations": [], "elapsed_training_seconds": 0,
                         "planned_training_seconds": max(0, self.cutoff - parse_time(self.plan["launched_at"])), "planned_wall_seconds": self.plan["wall_budget_seconds"],
                         "budget_note": "Six-hour maximum wall budget includes setup, all evaluation and publication; final 45 minutes reserved. Learning can stop early.",
                         "interpretation": "Actual HUD points and a separate custom extra-life teaching bonus are measured under the event-aware environment. Adaptive choices are preregistered; final tests remain reserved.",
                         "comparison_report_path": self.rel(self.run / "README.md"), "latest_checkpoint": self.rel(self.baseline), "latest_checkpoint_sha256": digest(self.baseline),
                         "preferred_checkpoint": self.rel(self.baseline), "active_stage": None, "active_training_dir": None, "active_evaluation": None}
        self.persist(); rows = []; index = 0
        try:
            if show_window:
                try:
                    with (self.run / "logs/window.log").open("a") as stream:
                        viewer = subprocess.Popen([self.py, self.plan["viewer_script"], self.rel(self.run)], cwd=self.root, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                        self.manifest["window_pid"] = viewer.pid
                except OSError as error: self.manifest["window_error"] = str(error)
            import shutil
            if sys.platform == "darwin" and shutil.which("caffeinate"):
                self.keep_awake = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
            self.render()
            data = self.evaluate(self.baseline, self.run / "stages/00_baseline", self.plan["validation_seeds"], self.plan["validation_video_seeds"], "baseline_validation")
            baseline = {"id": "00_baseline", "index": 0, "label": "Preserved completion baseline", "elapsed_training_seconds": 0,
                        "training_timesteps": initial["num_timesteps"], "evaluation_path": self.rel(self.run / "stages/00_baseline/evaluation.json"),
                        "checkpoint_path": self.rel(self.baseline), "checkpoint_sha256": digest(self.baseline), "training_summary_path": None}
            self.manifest["stages"].append(baseline); rows.append({**baseline, **metrics(data)})
            self.manifest["status"] = "running"; self.persist(); self.render(); self.publish()
            success_counts = {}; banned = set(); active = dict(BRIDGE); working = self.baseline
            for index in range(1, self.plan["max_chunks"] + 1):
                best = best_stage(rows)
                configuration = dict(PURE if index == 1 else BRIDGE if index == 2 else active)
                predecessor = self.baseline if index <= 2 else working
                key = (configuration["objective"], configuration["score_weight"], configuration["learning_rate"])
                try:
                    row = self.stage(index, predecessor, configuration)
                except EvaluationIncomplete as error:
                    self.verify_sources()
                    self.manifest["failed_attempts"].append({"stage_id": f"{index:02d}_stage", "error": str(error), "at": utc()})
                    self.manifest.update(active_stage=None, active_training_dir=None, active_evaluation=None)
                    self.persist(); self.render(); self.publish()
                    if self.remaining("learning") >= 1530 and (index == 1 or configuration["learning_rate"] != 1e-5):
                        active = {**configuration, "learning_rate": 1e-5}
                        working = within(self.root, best_stage(rows)["checkpoint_path"])
                        continue  # Initial stage 2 still starts the bridge from the preserved baseline.
                    self.manifest["learning_stop_reason"] = "incomplete_validation_no_safe_retry_budget"; break
                except DeadlineReached as error:
                    self.manifest["failed_attempts"].append({"stage_id": f"{index:02d}_stage", "error": str(error), "at": utc()})
                    self.manifest["learning_stop_reason"] = "reserved_final_test_time"; break
                except (StopRequested, KeyboardInterrupt): raise
                except Exception as error:
                    self.manifest["failed_attempts"].append({"stage_id": f"{index:02d}_stage", "error": str(error), "at": utc()})
                    self.manifest["learning_stop_reason"] = "training_or_validation_invariant_error"; self.persist(); raise
                rows.append(row)
                improving = qualified(row) and ranking_key(row) > ranking_key(best)
                regression = not qualified(row) or row["mean_completed_augmented_score"] < best["mean_completed_augmented_score"]
                confirmed = self.confirm(row, best) if regression else False
                decision = "Qualified improvement" if improving else "Preserve best; no qualifying improvement"
                if improving: success_counts[key] = success_counts.get(key, 0) + 1
                if confirmed or not qualified(row):
                    decision = "Confirmed regression; resume best checkpoint" if confirmed else "Validation gate not met; resume best checkpoint"
                    if configuration["learning_rate"] == 1e-5: banned.add(key[:2])
                    active = {**configuration, "learning_rate": 1e-5}
                    working = within(self.root, best_stage(rows)["checkpoint_path"])
                elif index >= 2:
                    # Continue useful learning through plateaus while keeping the selection winner protected.
                    active = dict(configuration)
                    working = within(self.root, row["checkpoint_path"])
                    if improving and configuration["objective"] == "score_bridge" and success_counts.get(key, 0) >= 2 and configuration["score_weight"] < 1:
                        active = {**configuration, "score_weight": .5 if configuration["score_weight"] == .25 else 1.0}
                if index == 2:
                    eligible_probes = [probe for probe in rows if probe["index"] > 0 and qualified(probe)]
                    selected_approach = max(eligible_probes, key=ranking_key) if eligible_probes else best_stage(rows)
                    active = dict(selected_approach.get("training_configuration", {**BRIDGE, "learning_rate": 1e-5}))
                    working = within(self.root, selected_approach["checkpoint_path"])
                self.manifest["stages"][-1]["decision"] = decision
                row["decision"] = decision
                self.manifest["adaptations"].append({"after_stage": row["id"], "decision": decision, "configuration": configuration,
                                                     "next_configuration": active, "next_working_checkpoint": self.rel(working),
                                                     "protected_best_checkpoint": best_stage(rows)["checkpoint_path"],
                                                     "at": utc(), "improving": improving, "regression_confirmed": confirmed})
                self.persist(); self.render(); self.publish()
                if index >= 2 and (active["objective"], active["score_weight"]) in banned:
                    fallbacks = [candidate for candidate, count in success_counts.items() if count >= 2 and candidate[:2] not in banned]
                    if not fallbacks:
                        self.manifest["learning_stop_reason"] = "repeated_regression_no_tested_fallback"; break
                    objective, weight, _ = fallbacks[-1]; active = {**BRIDGE, "objective": objective, "score_weight": weight, "learning_rate": 1e-5}
                    working = within(self.root, best_stage(rows)["checkpoint_path"])
            else: self.manifest["learning_stop_reason"] = "stage_count_limit"
            self.manifest.update(active_stage=None, active_training_dir=None, active_evaluation=None); self.persist()
            if not rows: raise RuntimeError("Baseline evaluation unavailable")
            selected = self.freeze_selection(rows)
            self.render(); self.publish()
            for label, checkpoint in (("baseline", self.baseline), ("candidate", within(self.root, selected["checkpoint_path"]))):
                self.verify_selection()
                output = self.run / (label + "_audit")
                self.evaluate(checkpoint, output, self.plan["holdout_seeds"], self.plan["holdout_video_seeds"], label + "_final_test", final=True)
                self.manifest[label + "_audit_path"] = self.rel(output / "evaluation.json"); self.persist()
            self.verify_selection()
            original = metrics(load(self.run / "baseline_audit/evaluation.json")); candidate = metrics(load(self.run / "candidate_audit/evaluation.json"))
            if selected["index"] != 0 and candidate["clears"] >= 95 and candidate["mean_completed_augmented_score"] > original["mean_completed_augmented_score"]:
                self.manifest["preferred_checkpoint"] = selected["checkpoint_path"]
            self.manifest.update(status="completed", completion_reason="bounded_learning_and_paired_final_test_complete", finished_at=utc())
        except DeadlineReached as error:
            self.manifest.update(status="incomplete", completion_reason=str(error), finished_at=utc())
        except (StopRequested, KeyboardInterrupt) as error:
            self.manifest.update(status="interrupted", completion_reason=str(error) or "interrupt", finished_at=utc())
        except Exception as error:
            self.manifest.update(status="failed", completion_reason=str(error), finished_at=utc())
            import traceback; traceback.print_exc()
        finally:
            self.manifest.update(active_stage=None, active_training_dir=None, active_evaluation=None); self.persist()
            try:
                self.render(); published = self.publish()
                if self.publish_enabled and published and self.manifest["status"] == "completed" and self.remaining() > 150:
                    self.child([self.py, "publish_lesson_models.py", "--manifest", self.rel(self.manifest_path), "--max-seconds", str(min(480, self.remaining() - 100))], "models_publication.log", min(500, self.remaining() - 90))
                    self.manifest = load(self.manifest_path); self.render(); self.publish()
            except Exception as error:
                self.manifest["publication_note"] = str(error); self.persist()
            if self.keep_awake:
                self.keep_awake.terminate()
                try: self.keep_awake.wait(timeout=2)
                except subprocess.TimeoutExpired: self.keep_awake.kill()
            self.update_registry(finished=True)
        return 0 if self.manifest["status"] == "completed" else 1


def create_plan(root, run, args, launched):
    from overnight_env import EVENT_REWARD_CONFIG
    deadline = parse_time(args.deadline_utc) if args.deadline_utc else launched + 21600
    if not 2700 + 600 < deadline - launched <= 21600: raise ValueError("Deadline must leave final-test reserve and be within six hours of launch")
    sources = SOURCES
    if subprocess.check_output(["git", "status", "--porcelain", "--", *sources], cwd=root, text=True, timeout=15):
        raise RuntimeError("Commit experiment sources before starting")
    baseline = within(root, args.initial_model)
    plan = {"launched_at": datetime.fromtimestamp(launched, timezone.utc).isoformat(), "created_at": utc(),
            "deadline_utc": datetime.fromtimestamp(deadline, timezone.utc).isoformat(), "wall_budget_seconds": deadline - launched,
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, timeout=15).strip(),
            "source_hashes": {name: digest(root / name) for name in sources}, "initial_checkpoint": str(baseline.relative_to(root)),
            "initial_checkpoint_sha256": digest(baseline), "event_reward_config": EVENT_REWARD_CONFIG, "chunk_seconds": 900,
            "final_reserve_seconds": 2700, "max_chunks": 20, "validation_max_seconds": 600, "holdout_max_seconds": 1800,
            "validation_seeds": list(range(args.seed_base + 101, args.seed_base + 121)), "validation_video_seeds": [args.seed_base + n for n in (101, 110, 120)],
            "holdout_seeds": list(range(args.seed_base + 201, args.seed_base + 301)), "holdout_video_seeds": [args.seed_base + n for n in (201, 234, 267, 300)],
            "confirmation_seed_bank": [list(range(args.seed_base + 1000 + i * 20, args.seed_base + 1020 + i * 20)) for i in range(20)],
            "initial_trials": [PURE, BRIDGE], "viewer_script": "overnight_watch.py",
            "regression_guard": {"minimum_seconds": 300, "window_episodes": 100, "minimum_completion_rate": .2},
            "selection_rule": "Baseline always eligible. New stages require at least 19/20 validation clears. Rank by completed augmented points, completed actual HUD points, clears, then earlier stage. Freeze before either final test.",
            "adaptation_rule": "First sparse and bridge0.25 trials start independently from preserved baseline. Choose the best qualifying new approach, retaining baseline as protected selection candidate. Continue the latest qualified working checkpoint through ties and nonconfirmed regressions; preserve the best checkpoint separately for final selection. Unqualified/partial stages or confirmed regressions roll back to protected best and allow one retry at LR1e-5. Raise bridge weight0.25→0.5→1 only after two qualifying improvements at current weight. Recheck regressions on paired fresh validation seeds. Repeated failure ends path or uses only a previously twice-improving configuration.",
            "promotion_rule": "New selected stage needs at least95/100 final clears and greater completed augmented score; baseline remains available and actual HUD change is reported separately",
            "limitations": "Same World1-1 start, stochastic action seeds, RIGHT_ONLY no backtracking, one adaptive run, no claim of maximum score or cross-level generalization"}
    save(run / "experiment_plan.json", plan)


def main():
    launched = time.time()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=Path("results/teaching_overnight_20260921"))
    parser.add_argument("--initial-model", type=Path, default=Path("results/teaching_20260920/training/03_stage/checkpoints/final.zip"))
    parser.add_argument("--deadline-utc"); parser.add_argument("--seed-base", type=int, default=20000)
    parser.add_argument("--publish", action="store_true"); parser.add_argument("--show-window", action="store_true")
    parser.add_argument("--finish-only", action="store_true")
    parser.add_argument("--watchdog-parent", type=int, help=argparse.SUPPRESS); parser.add_argument("--watchdog-created", type=float, help=argparse.SUPPRESS)
    parser.add_argument("--watchdog-deadline", type=float, help=argparse.SUPPRESS); parser.add_argument("--watchdog-registry", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.watchdog_parent:
        return watchdog(args.watchdog_parent, args.watchdog_created, args.watchdog_deadline, args.watchdog_registry)
    root = Path(__file__).resolve().parent; run = within(root, args.run_dir)
    if run == root / "results" or not run.is_relative_to(root / "results") or not 0 <= args.seed_base < 2**32 - 2000:
        parser.error("Choose a new results directory and valid seed base")
    (root / ".cache").mkdir(exist_ok=True)
    with (root / ".cache/lesson_session.lock").open("a+") as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: parser.error("Another classroom training session is running")
        if not args.finish_only:
            run.mkdir(parents=True, exist_ok=False); create_plan(root, run, args, launched)
        experiment = OvernightExperiment(root, run / "experiment_plan.json", args.publish)
        experiment.validate_plan()
        if args.finish_only:
            # Presentation retries get a fresh short operation deadline, but launch no learning/evaluation.
            experiment.deadline = time.time() + 600; experiment.monotonic_deadline = time.monotonic() + 600
            experiment.launch_guard()
            try: return experiment.finish_only()
            finally: experiment.update_registry(finished=True)
        return experiment.run_experiment(args.show_window)


if __name__ == "__main__": raise SystemExit(main())
