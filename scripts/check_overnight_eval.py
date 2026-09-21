"""Exercise the evaluator contract without running a game or changing a model."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import contextlib
import csv
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import types
from unittest.mock import patch

import numpy as np
import torch
from PIL import Image, ImageSequence
from stable_baselines3 import PPO

from overnight_eval import main, summarize_episodes


class Distribution:
    distribution = types.SimpleNamespace(probs=torch.tensor([[0.0, 1.0, 0.0, 0.0, 0.0]]))
    def get_actions(self, deterministic=False): return torch.tensor([1])
    def entropy(self): return torch.tensor([0.0])


class Policy:
    def set_training_mode(self, enabled): assert enabled is False
    def obs_to_tensor(self, observation): return None, False
    def get_distribution(self, tensor): return Distribution()
    def state_dict(self): return {"probe": torch.tensor([1.0, 2.0])}


class ProbeEnv:
    def __init__(self, seed, record_resolution, **kwargs):
        assert kwargs["objective"] == "score_events" and kwargs["score_weight"] == 1.0
        self.seed, self.video = seed, record_resolution
        self.i = 0
        self.frame = np.zeros((240, 256, 3), np.uint8)
        self.events = {"one_ups": 0, "one_up_source_counts": {"coin_rollover": 0, "other_or_unknown": 0},
                       "flag_height_bonus": 0, "flag_touch_y": None, "flag_contact_score": None,
                       "flag_score_tier": None, "flag_top_tier": False, "post_flag_frames": 0,
                       "flag_resolution_complete": False, "flag_resolution_status": "not_touched"}

    def reset(self, seed):
        assert seed == self.seed
        return np.zeros((4, 84, 84), np.uint8), self.info()

    def info(self):
        done, clear = self.i == 2, self.i == 2 and self.seed == 1
        score = 2000 if clear else self.i * 100
        reward_sum = score / 1000 + (6 if clear else -5 if done else 0)
        if clear:
            self.events.update(one_ups=1, one_up_source_counts={"coin_rollover": 0, "other_or_unknown": 1},
                               flag_height_bonus=500, flag_touch_y=80, flag_contact_score=1500,
                               flag_score_tier=2, post_flag_frames=7, flag_resolution_complete=True,
                               flag_resolution_status="award_observed")
        value = {"x_pos": 3161 if clear else 40 + self.i * 100, "y_pos": 80,
                 "score": score, "coins": self.i, "life": 2 + int(clear), "time": 380,
                 "flag_get": clear, "action_repeat_frames": 8 if clear else 4,
                 "action_repeat_controlled_frames": 1 if clear else 4,
                 "event_metrics": dict(self.events),
                 "score_metrics": {"initial_score": 0, "current_score": score,
                    "score_gain": score, "max_score": score,
                    "custom_one_up_bonus": 1000 if clear else 0,
                    "augmented_score_gain": score + (1000 if clear else 0),
                    "objective_reward": reward_sum - (0.1 if done else 0),
                    "objective_reward_sum": reward_sum, "native_reward_sum": self.i * 2.5}}
        if done:
            value["episode_metrics"] = {"completed": clear, "max_x": value["x_pos"],
                                        "native_reward_sum": 5.0}
        if clear and self.video:
            value["flag_contact_frame"] = np.full_like(self.frame, 20)
            value["resolution_frames"] = [np.full_like(self.frame, 30), np.full_like(self.frame, 40)]
            value["resolution_frame_counts"] = [4, 3]
        return value

    def step(self, action):
        assert action == 1
        self.i += 1
        self.frame.fill(40 if self.i == 2 and self.seed == 1 else 10)
        info = self.info()
        return np.zeros((4, 84, 84), np.uint8), info["score_metrics"]["objective_reward"], self.i == 2, False, info

    def render(self): return self.frame
    def close(self): pass


fake_model = types.SimpleNamespace(policy=Policy(), num_timesteps=123,
                                   action_space=types.SimpleNamespace(n=5))
fake_module = types.ModuleType("overnight_env")
fake_module.make_env = ProbeEnv
fake_module.EVENT_REWARD_CONFIG = {"one_up_teaching_points": 1000}

with tempfile.TemporaryDirectory(prefix="mario-overnight-eval-check-") as folder:
    root = Path(folder)
    model = root / "model.zip"
    model.write_bytes(b"unchanged simulated checkpoint")
    output = root / "evaluation"
    args = ["overnight_eval.py", "--model", str(model), "--output-dir", str(output),
            "--seeds", "1", "2", "--video-seeds", "1", "--max-decisions", "3",
            "--beginning-decisions", "3", "--max-seconds", "30"]
    with patch.object(sys, "argv", args), patch.object(PPO, "load", return_value=fake_model), \
         patch.dict(sys.modules, {"overnight_env": fake_module}), contextlib.redirect_stdout(StringIO()):
        assert main() == 0
    report = json.loads((output / "evaluation.json").read_text())
    assert report["status"] == "complete" and report["level_completions"] == 1
    assert report["model_file_unchanged"] and report["policy_unchanged"]
    assert report["model_timesteps_before"] == report["model_timesteps_after"] == 123
    assert report["mean_native_reward"] == 5.0
    assert report["mean_completed_score"] == 1000 and report["mean_completed_augmented_score"] == 1500
    assert report["mean_custom_one_up_bonus"] == 500 and report["mean_flag_height_bonus"] == 250
    first = report["episodes"][0]
    assert first["game_score"] == 2000 and first["custom_one_up_bonus"] == 1000
    assert first["raw_frames"] == 12 and first["post_flag_frames"] == 7
    assert first["media"]["beginning"]["captured_frames"] == 4
    assert first["media"]["beginning"]["is_full_episode"]
    with (output / first["trace_csv"]).open() as file:
        rows = list(csv.DictReader(file))
    assert [float(row["native_reward"]) for row in rows] == [2.5, 2.5]
    assert [float(row["objective_reward"]) for row in rows] == [0.1, 7.9]
    events = [json.loads(line) for line in (output / first["event_trace_jsonl"]).read_text().splitlines()]
    assert len(events) == 2 and events[-1]["event_metrics"]["flag_resolution_complete"]
    with Image.open(output / first["media"]["beginning"]["path"]) as gif:
        colors = [frame.convert("RGB").getpixel((0, 0))[0] for frame in ImageSequence.Iterator(gif)]
    assert colors == [10, 20, 30, 40], "GIF must show contact before the pole-slide settlement"
    before = (output / "evaluation.json").read_bytes()
    with patch.object(sys, "argv", args), contextlib.redirect_stderr(StringIO()):
        try:
            main()
            raise AssertionError("existing archive was not rejected")
        except SystemExit as error:
            assert error.code == 2
    assert (output / "evaluation.json").read_bytes() == before
    assert summarize_episodes([])["mean_completed_augmented_score"] is None

print("PASS: frozen simulated evaluation; actual HUD/custom bonus separation; native vs objective rewards; weighted summaries; chronological flag animation with exact raw-frame accounting; trace/JSON evidence; archive overwrite refusal; empty summaries.")
