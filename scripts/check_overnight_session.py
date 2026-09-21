"""Bounded tests; no real training, GUI or network calls."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import csv
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import psutil
from continue_lesson import digest, load, save, utc
import overnight_session as runner
from overnight_report import best_stage, checked_evaluation, metrics, qualified


def evaluation(path, seeds, model_hash, reward_config, points=1000, clears=None, videos=()):
    path.parent.mkdir(parents=True, exist_ok=False)
    clears = len(seeds) if clears is None else clears
    row = {"decision": 1, "game_score": points, "score_gain": points, "one_ups": 1,
           "custom_one_up_bonus": 1000, "augmented_score_gain": points + 1000, "flag_height_bonus": 100,
           "native_reward": 1, "native_reward_sum": 1, "objective_reward": 2, "objective_reward_sum": 2}
    with (path.parent / "trace.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
    (path.parent / "events.jsonl").write_text(json.dumps({"decision": 1, "event_metrics": {}, "score_metrics": row}) + "\n")
    (path.parent / "full.gif").write_bytes(b"test clip")
    episodes = [{"seed": seed, "completed": index < clears, "game_score": points, "initial_score": 0,
                 "score_gain": points, "one_ups": 1, "custom_one_up_bonus": 1000, "augmented_score_gain": points + 1000,
                 "flag_height_bonus": 100, "native_reward": 1, "objective_reward_sum": 2,
                 "decisions": 1, "terminated": True, "truncated": False, "trace_csv": "trace.csv", "trace_rows": 1,
                 "event_trace_jsonl": "events.jsonl", "event_trace_rows": 1,
                 "media": {"beginning": {"path": "full.gif", "first_decision": 1, "last_decision": 1, "is_full_episode": True}} if seed in videos else {}}
                for index, seed in enumerate(seeds)]
    data = {"status": "complete", "learning_updates": 0, "model_sha256": model_hash, "model_sha256_after": model_hash,
            "model_file_unchanged": True, "policy_sha256_before": "policy", "policy_sha256_after": "policy", "policy_unchanged": True,
            "started_at": utc(), "episodes": episodes, "level_completions": clears,
            "protocol": {"deterministic": False, "max_decisions": 3000, "action_space": "RIGHT_ONLY", "seeds": seeds,
                         "objective": "score_events", "score_weight": 1.0, "event_reward_config": reward_config}}
    data.update(metrics(data)); save(path, data); return data


class OvernightTests(unittest.TestCase):
    def test_baseline_eligibility_and_completion_gate(self):
        baseline = {"index": 0, "trials": 20, "clears": 18, "mean_completed_augmented_score": 900, "mean_completed_score": 900}
        bad = {**baseline, "index": 1, "clears": 18, "mean_completed_augmented_score": 10000}
        good = {**bad, "index": 2, "clears": 19}
        self.assertFalse(qualified(bad)); self.assertIs(best_stage([baseline, bad]), baseline)
        self.assertIs(best_stage([baseline, bad, good]), good)

    def test_event_trace_and_missing_freeze_proof_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "eval/evaluation.json"
            data = evaluation(path, [1, 2], "hash", {}, videos=[1])
            checked_evaluation(path, [1, 2], "hash", [1], {})
            for key in ("policy_unchanged", "model_file_unchanged", "model_sha256_after"):
                changed = dict(data); changed.pop(key); save(path, changed)
                with self.assertRaises(ValueError): checked_evaluation(path, [1, 2], "hash", [1], {})
            save(path, data)
            (path.parent / "events.jsonl").write_text((path.parent / "events.jsonl").read_text().replace('"one_ups": 1', '"one_ups": 2'))
            with self.assertRaises(ValueError): checked_evaluation(path, [1, 2], "hash", [1], {})

    def experiment(self, root):
        root = root.resolve(); run = root / "results/overnight_test"; run.mkdir(parents=True)
        baseline = root / "baseline.zip"; baseline.write_bytes(b"baseline")
        deadline = time.time() + 20000
        plan = {"deadline_utc": runner.datetime.fromtimestamp(deadline, runner.timezone.utc).isoformat(), "launched_at": utc(),
                "wall_budget_seconds": 20000, "final_reserve_seconds": 2700, "initial_checkpoint": "baseline.zip",
                "initial_checkpoint_sha256": digest(baseline), "source_hashes": {}, "event_reward_config": {}, "chunk_seconds": 900,
                "max_chunks": 4, "validation_seeds": list(range(101, 121)), "validation_video_seeds": [101, 110, 120],
                "holdout_seeds": list(range(201, 301)), "holdout_video_seeds": [201, 234, 267, 300],
                "confirmation_seed_bank": [list(range(1000, 1020))], "selection_rule": "test", "viewer_script": "watch.py"}
        save(run / "experiment_plan.json", plan)

        class MockExperiment(runner.OvernightExperiment):
            configurations = None
            def launch_guard(self): self.configurations = []; self.update_registry()
            def verify_sources(self): pass
            def verify_fresh_seeds(self): pass
            def checkpoint_metadata(self, path): return {"num_timesteps": 1, "effective_seed": 123}
            def publish(self): return True
            def render(self):
                from overnight_report import build_report
                build_report(self.root, self.manifest_path)
            def evaluate(self, checkpoint, output, seeds, videos, label, final=False):
                if final: self.verify_selection()
                points = 1000 if checkpoint == self.baseline else 2000
                return evaluation(output / "evaluation.json", seeds, digest(checkpoint), {}, points=points, videos=videos)
            def stage(self, index, predecessor, configuration):
                self.configurations.append((index, predecessor, dict(configuration)))
                checkpoint = self.run / f"model_{index}.zip"; checkpoint.write_bytes(str(index).encode())
                path = self.run / f"stages/{index:02d}_stage/evaluation.json"
                data = evaluation(path, self.plan["validation_seeds"], digest(checkpoint), {}, points=1000 + index * 500,
                                  clears=0 if index == 1 else 20, videos=self.plan["validation_video_seeds"])
                self.manifest["elapsed_training_seconds"] += 900
                entry = {"id": f"{index:02d}_stage", "index": index, "checkpoint_path": self.rel(checkpoint), "checkpoint_sha256": digest(checkpoint),
                         "training_configuration": dict(configuration), "elapsed_training_seconds": index * 900,
                         "evaluation_path": self.rel(path), "training_summary_path": None}
                self.manifest["stages"].append(entry)
                return {**entry, **metrics(data)}
            def confirm(self, candidate, reference): return True

        return MockExperiment(root, run / "experiment_plan.json", False)

    def test_mocked_adaptation_frozen_selection_and_partial_report(self):
        with tempfile.TemporaryDirectory() as directory:
            exp = self.experiment(Path(directory))
            with patch("shutil.which", return_value=None): self.assertEqual(exp.run_experiment(), 0)
            configs = exp.configurations
            self.assertEqual(configs[0][1], exp.baseline); self.assertEqual(configs[1][1], exp.baseline)
            self.assertEqual(configs[0][2], runner.PURE); self.assertEqual(configs[1][2], runner.BRIDGE)
            self.assertEqual(configs[2][2]["score_weight"], .25)
            self.assertEqual(configs[3][2]["score_weight"], .5)
            self.assertTrue(load(exp.run / "verification.json")["selection_preceded_holdouts"])
            entry = dict(exp.manifest["stages"][-1]); entry.update(id="05_partial", index=5, evaluation_path=exp.rel(exp.run / "partial/evaluation.json"))
            save(exp.run / "partial/evaluation.json", {"status": "incomplete", "episodes": []})
            exp.manifest["stages"].append(entry); exp.persist(); exp.render()
            self.assertIn("Incomplete; excluded", (exp.run / "README.md").read_text())

    def test_incomplete_sparse_probe_still_runs_independent_bridge(self):
        with tempfile.TemporaryDirectory() as directory:
            exp = self.experiment(Path(directory))
            original = exp.stage
            def partial_first(index, predecessor, configuration):
                row = original(index, predecessor, configuration)
                if index == 1:
                    path = exp.root / row["evaluation_path"]
                    data = load(path); data["status"] = "incomplete"; save(path, data)
                    raise runner.EvaluationIncomplete("sparse probe timed out")
                return row
            with patch.object(exp, "stage", side_effect=partial_first), patch("shutil.which", return_value=None):
                self.assertEqual(exp.run_experiment(), 0)
            self.assertEqual(exp.configurations[1][1], exp.baseline)
            self.assertEqual(exp.configurations[1][2], runner.BRIDGE)
            self.assertNotEqual(exp.manifest["selected_stage_id"], "01_stage")
            self.assertIn("Incomplete; excluded", (exp.run / "README.md").read_text())
            self.assertEqual(len(exp.manifest["failed_attempts"]), 1)

    def test_tied_qualified_stages_continue_working_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            exp = self.experiment(Path(directory)); original = exp.stage
            def plateau(index, predecessor, configuration):
                row = original(index, predecessor, configuration)
                if index >= 2:
                    path = exp.root / row["evaluation_path"]
                    # All three new qualified stages tie; earliest remains protected best.
                    data = load(path)
                    for ep in data["episodes"]:
                        ep.update(game_score=2000, score_gain=2000, augmented_score_gain=3000)
                    data.update(metrics(data)); save(path, data)
                    row.update(metrics(data))
                return row
            # This test targets checkpoint flow, not rebuilding already-tested CSV fixtures.
            with patch.object(exp, "stage", side_effect=plateau), patch.object(exp, "render"), patch("shutil.which", return_value=None):
                self.assertEqual(exp.run_experiment(), 0)
            self.assertEqual(exp.configurations[2][1], exp.run / "model_2.zip")
            self.assertEqual(exp.configurations[3][1], exp.run / "model_3.zip")
            self.assertEqual(exp.manifest["selected_stage_id"], "02_stage")

    def test_watchdog_stops_detached_descendant_at_hard_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory).resolve(); pidfile = directory / "child.pid"
            code = "import subprocess,sys,time,signal;signal.signal(signal.SIGINT,signal.SIG_IGN);p=subprocess.Popen([sys.executable,'-c','import time,signal;signal.signal(signal.SIGINT,signal.SIG_IGN);time.sleep(60)'],start_new_session=True);open(sys.argv[1],'w').write(str(p.pid));time.sleep(60)"
            parent = subprocess.Popen([sys.executable, "-c", code, str(pidfile)])
            try:
                limit = time.time() + 3
                while not pidfile.exists() and time.time() < limit: time.sleep(.02)
                child = psutil.Process(int(pidfile.read_text()))
                registry = directory / "registry.json"; save(registry, {"children": [], "finished": False})
                started = time.monotonic()
                guard = subprocess.Popen([sys.executable, str(Path(runner.__file__)), "--watchdog-parent", str(parent.pid),
                                          "--watchdog-created", str(psutil.Process(parent.pid).create_time()),
                                          "--watchdog-deadline", str(time.time() + 1.5), "--watchdog-registry", str(registry)])
                guard.wait(timeout=5); parent.wait(timeout=2)
                self.assertLess(time.monotonic() - started, 4)
                self.assertTrue(not child.is_running() or child.status() == psutil.STATUS_ZOMBIE)
                self.assertEqual(load(directory / "deadline_watchdog_result.json")["status"], "hard_deadline")
            finally:
                if parent.poll() is None: parent.kill(); parent.wait()
                if 'child' in locals():
                    try:
                        if child.is_running(): child.kill()
                    except psutil.Error: pass


if __name__ == "__main__": unittest.main()
