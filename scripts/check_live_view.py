"""Bounded verification of transition isolation, sampling and viewer metadata."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import warnings

import gymnasium as gym
import numpy as np
from PIL import Image

from live_view import LiveFrames
from watch_training import decode_live, read_json, snapshot


class ProbeEnv(gym.Env):
    observation_space = gym.spaces.Box(0, 255, (240, 256, 3), np.uint8)
    action_space = gym.spaces.Discrete(2)

    def __init__(self):
        self.frame = np.zeros((240, 256, 3), np.uint8)
        self.calls = 0
        self.break_render = False

    def reset(self, **kwargs):
        self.calls = 0
        self.frame.fill(0)
        self.initial = (self.frame, {"score": 0, "coins": 0, "x_pos": 40, "time": 400})
        return self.initial

    def step(self, action):
        self.calls += 1
        self.frame.fill(self.calls)
        self.transition = (self.frame, 2.0, self.calls == 3, False,
                           {"score": self.calls * 100, "coins": self.calls,
                            "x_pos": 40 + self.calls, "time": 400 - self.calls,
                            "flag_get": self.calls == 3,
                            "score_metrics": {"objective_reward": 2.0}})
        return self.transition

    def render(self):
        if self.break_render:
            raise RuntimeError("probe render failure")
        return self.frame


with TemporaryDirectory(prefix="mario-view-check-") as folder:
    root = Path(folder)
    path = root / "live_frame.json"
    raw = ProbeEnv()
    env = LiveFrames(raw, path)
    with patch("live_view.time.monotonic", side_effect=[0, 0.1, 0.19, 0.21, 0.22, 0.43]):
        observed, info = env.reset()
        assert observed is raw.initial[0] and info is raw.initial[1]
        for _ in range(3):
            assert env.step(1) is raw.transition
        terminal = read_json(path)
        assert terminal["terminated"] and terminal["flag"]
        assert terminal["score"] == 300 and terminal["episode"] == 1
        assert terminal["objective_reward"] == 2.0
        assert np.all(np.asarray(decode_live(terminal)) == 3)
        env.reset()
        # Rate-limited reset cannot overwrite a just-published terminal frame.
        assert read_json(path) == terminal
        env.step(0)
    assert env.published_frames == 3 and env.publish_errors == 0
    current = read_json(path)
    assert current["episode"] == 2 and current["score"] == 100
    assert not list(root.glob(".*.tmp"))
    raw.break_render = True
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for _ in range(2):
            env.next_frame = -1
            assert env.step(0) is raw.transition
        assert len(caught) == 1 and env.publish_errors == 2
    broken = LiveFrames(raw, root / "broken.json")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        broken.reset()  # Even warning promotion must not terminate training.
    assert broken.publish_errors == 1
    disabled = LiveFrames(raw, None)
    disabled.reset()
    assert disabled.publish_errors == disabled.published_frames == 0

    session = root / "results" / "test"
    stage_dir = session / "stages" / "01_stage"
    stage_dir.mkdir(parents=True)
    training = session / "training" / "01_stage"
    training.mkdir(parents=True)
    Image.new("RGB", (256, 240)).save(stage_dir / "beginning.gif")
    evaluation = {"episodes": [{"seed": 1, "game_score": 1200, "coins": 2,
                  "max_x": 1000, "completed": False, "end_reason": "game_terminated",
                  "media": {"beginning": {"path": "beginning.gif", "is_full_episode": True},
                            "terminal_frame": "last-frame.png"}}]}
    (stage_dir / "evaluation.json").write_text(json.dumps(evaluation))
    (training / "progress.json").write_text(json.dumps({"elapsed_seconds": 900, "timesteps": 1000}))
    manifest = {"status": "running", "elapsed_training_seconds": 900,
                "active_stage": "01_stage", "active_training_dir": str(training.relative_to(root)),
                "active_evaluation": "01_validation", "pending_stage": {"id": "01_stage"},
                "stages": [{"id": "00_baseline", "elapsed_training_seconds": 0,
                            "training_timesteps": 500},
                           {"id": "01_stage", "elapsed_training_seconds": 900,
                            "training_timesteps": 1000,
                            "evaluation_path": str((stage_dir / "evaluation.json").relative_to(root))}]}
    (session / "manifest.json").write_text(json.dumps(manifest))
    snap = snapshot(session, root)
    assert snap["training_seconds"] == 900, "evaluation must not double count training time"
    assert snap["decisions"] == 1000 and not snap["training_active"]
    assert len(snap["samples"]) == 1 and snap["samples"][0]["score"] == 1200
    assert snap["samples"][0]["full_episode"]
    manifest["stages"].pop()
    manifest.update(elapsed_training_seconds=0, active_evaluation=None, pending_stage=None)
    (session / "manifest.json").write_text(json.dumps(manifest))
    snap = snapshot(session, root)
    assert snap["training_seconds"] == 900 and snap["training_active"]
    oversized = root / "oversized.json"
    oversized.write_text('{"test": "123456789"}')
    try:
        read_json(oversized, limit=10)
        raise AssertionError("size bound not enforced")
    except ValueError:
        pass

print("PASS: exact transition pass-through; 5 Hz shared reset/step sampling; terminal frame/info consistency; atomic replacement; disabled/error isolation including warnings-as-errors; GIF discovery and score fields; active/evaluation time accounting; bounded reads.")
