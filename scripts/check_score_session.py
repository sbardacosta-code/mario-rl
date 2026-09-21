"""Fast score-experiment checks; no emulator, gradient updates, GUI or network."""
import copy
import csv
from pathlib import Path
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import patch

from continue_lesson import digest, load, save, utc
import score_report as report
import score_session as session


def fake_evaluation(path, seeds, checkpoint_hash, clears, points=1200, videos=()):
    path.parent.mkdir(parents=True)
    episodes = []
    for index, seed in enumerate(seeds):
        done = index < clears
        trace = path.parent / f"{seed}.csv"
        row = {"decision": 1, "native_reward": 1, "game_score": points, "score_gain": points - 100,
               "coins": 0, "max_x": 3100, "raw_frames": 4, "flag_get": int(done), "terminated": 1,
               "truncated": 0, "action": 0}
        with trace.open("w") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
        media = {}
        if seed in videos:
            clip = path.parent / f"{seed}.gif"; clip.write_bytes(b"test clip")
            media["beginning"] = {"path": clip.name, "first_decision": 1, "last_decision": 1, "is_full_episode": True}
        episodes.append({"seed": seed, "completed": done, "game_score": points, "initial_score": 100,
                         "score_gain": points - 100, "max_score": points, "coins": 0, "native_reward": 1,
                         "max_x": 3100, "raw_frames": 4, "decisions": 1, "trace_rows": 1,
                         "terminated": True, "truncated": False, "trace_csv": trace.name,
                         "action_counts": [1, 0, 0, 0, 0], "media": media})
    data = {"status": "complete", "partial_episode": None, "learning_updates": 0, "model_sha256": checkpoint_hash,
            "protocol": {"environment": "SuperMarioBros-1-1-v0", "max_decisions": 3000, "deterministic": False,
                         "action_space": "RIGHT_ONLY", "action_repeat": 4, "observation_shape": [4, 84, 84],
                         "reward": "native reward summed over repeated frames", "device": "cpu", "stall_threshold_decisions": 120, "seeds": seeds},
            "episodes": episodes, "started_at": utc(), "level_completions": clears, "completion_rate": clears / len(seeds)}
    data.update({k: v for k, v in report.metrics(data).items() if k.startswith("mean_")})
    save(path, data)
    return data


class ScoreChecks(unittest.TestCase):
    def test_ranking_requires_clear_threshold_and_uses_score(self):
        rows = [{"stage_id": "01", "trials": 20, "clears": 18, "mean_completed_score": 9000, "mean_score_gain": 9100},
                {"stage_id": "02", "trials": 20, "clears": 20, "mean_completed_score": 1000, "mean_score_gain": 1000},
                {"stage_id": "03", "trials": 20, "clears": 19, "mean_completed_score": 2000, "mean_score_gain": 2100}]
        ranking, eligible = report.rank_candidates(rows)
        self.assertTrue(eligible); self.assertEqual(ranking[0]["stage_id"], "03")
        rows[1]["clears"] = 17; rows[2]["clears"] = 17
        ranking, eligible = report.rank_candidates(rows)
        self.assertFalse(eligible); self.assertEqual(ranking[0]["stage_id"], "01")
        rows[0]["trials"] = 19
        with self.assertRaises(ValueError): report.rank_candidates(rows)

    def test_ties_prefer_earlier(self):
        rows = [{"stage_id": index, "trials": 20, "clears": 20, "mean_completed_score": 1000, "mean_score_gain": 1000} for index in ("02", "01")]
        self.assertEqual(report.rank_candidates(rows)[0][0]["stage_id"], "01")

    def test_complete_trace_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "evaluation" / "evaluation.json"
            original = fake_evaluation(path, [1, 2], "hash", 1, videos=[1])
            self.assertEqual(report.checked_evaluation(path, [1, 2], "hash", [1], True)["mean_completed_score"], 550)
            for mutate in (lambda d: d.update(status="running"), lambda d: d.update(partial_episode={}),
                           lambda d: d.update(learning_updates=1), lambda d: d.update(mean_completed_score=600),
                           lambda d: d["episodes"].reverse(), lambda d: d["episodes"][0].update(score_gain=999)):
                data = copy.deepcopy(original); mutate(data); save(path, data)
                with self.assertRaises(ValueError): report.checked_evaluation(path, [1, 2], "hash", [1], True)
            save(path, original)
            (path.parent / "1.csv").write_text((path.parent / "1.csv").read_text().replace("1200", "1300"))
            with self.assertRaises(ValueError): report.checked_evaluation(path, [1, 2], "hash", [1], True)

    def make_experiment(self, root, chunks=2):
        root = root.resolve()
        run = root / "results" / "score_test"; run.mkdir(parents=True)
        baseline = root / "baseline.zip"; baseline.write_bytes(b"unchanged baseline")
        plan = {"initial_checkpoint": "baseline.zip", "initial_checkpoint_sha256": digest(baseline), "source_hashes": {},
                "expected_hyperparameters": {"learning_rate": .0001, "target_kl": .02, "ent_coef": .01},
                "score_reward_config": session.REWARD, "reward_scale": 1.0, "chunk_seconds": 900, "max_chunks": chunks,
                "validation_seeds": list(range(7101, 7121)), "validation_video_seeds": [7101, 7110, 7120],
                "holdout_seeds": list(range(7201, 7301)), "holdout_video_seeds": [7201, 7234, 7267, 7300]}
        save(run / "experiment_plan.json", plan)

        class MockExperiment(session.ScoreExperiment):
            def verify_sources(self):
                if digest(self.baseline) != self.plan["initial_checkpoint_sha256"]: raise RuntimeError("changed baseline")
            def verify_fresh_seeds(self): pass
            def checkpoint_metadata(self, path):
                return {"all_parameters_finite": True, "hyperparameters": plan["expected_hyperparameters"], "effective_seed": 123, "num_timesteps": 100}
            def evaluate(self, model, output, seeds, videos, label):
                self.check_stop()
                # Fail immediately if either holdout could run before frozen selection.
                if "final_test" in label: self.verify_selection()
                data = fake_evaluation(output / "evaluation.json", seeds, digest(model), len(seeds),
                                       1000 if model == self.baseline else 2000, videos)
                return report.checked_evaluation(output / "evaluation.json", seeds, digest(model), videos, True)
            def verify_training(self, training, previous, previous_model, stopped):
                data = load(training / "training_summary.json")
                if not data["all_parameters_finite"]: raise RuntimeError("non-finite")
                return data, self.checkpoint_metadata(training / "checkpoints/final.zip")
            def render(self): report.build_report(self.root, self.manifest_path)
            def publish(self): return True

        exp = MockExperiment(root, run / "experiment_plan.json", False)
        exp.baseline = baseline
        return exp

    def test_mocked_lifecycle_and_finish_only_never_retrains(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); exp = self.make_experiment(root)
            commands = []
            def run_training(command, workdir, log, timeout, stop):
                commands.append(command)
                self.assertEqual(timeout, 990)
                self.assertEqual(command[command.index("--objective") + 1], "score")
                self.assertEqual(command[command.index("--reward-scale") + 1], "1.0")
                self.assertEqual(command[command.index("--max-seconds") + 1], "900")
                self.assertIn("--live-preview", command)
                training = root / command[command.index("--run-dir") + 1]
                (training / "checkpoints").mkdir(parents=True)
                (training / "checkpoints/final.zip").write_bytes(str(len(commands)).encode())
                save(training / "training_summary.json", {"elapsed_seconds": 900, "timesteps": 100 + len(commands), "all_parameters_finite": True})
                (training / "logs").mkdir(); (training / "logs/progress.csv").write_text("loss\n1\n")
                return 0, None
            with patch.object(session, "run_process", side_effect=run_training), patch.object(session.shutil, "which", return_value=None):
                self.assertEqual(exp.run_experiment(), 0)
            self.assertEqual(len(commands), 2)
            self.assertTrue(exp.manifest["selected_qualified"])
            self.assertEqual(exp.manifest["selected_stage_id"], "01_stage")
            self.assertEqual(exp.manifest["preferred_checkpoint"], exp.manifest["selected_checkpoint"])
            self.assertIn("Every final-test attempt", (exp.run / "README.md").read_text())
            self.assertTrue(load(exp.run / "verification.json")["candidate_meets_predeclared_criteria"])
            with patch.object(exp, "stage", side_effect=AssertionError("training")), patch.object(exp, "evaluate", side_effect=AssertionError("evaluation")):
                self.assertEqual(exp.finish_only(), 0)
            with self.assertRaises(RuntimeError): exp.run_experiment()

    def test_partial_or_failed_stage_leaves_no_final_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            exp = self.make_experiment(Path(folder))
            with patch.object(exp, "stage", side_effect=RuntimeError("training failed")), patch.object(session.shutil, "which", return_value=None):
                self.assertEqual(exp.run_experiment(), 1)
            content = (exp.run / "README.md").read_text()
            self.assertIn("Pending. Both models", content)
            self.assertNotIn("Every final-test attempt", content)
            self.assertFalse((exp.run / "selection.json").exists())
            with self.assertRaises(RuntimeError): exp.finish_only()


if __name__ == "__main__": unittest.main()
