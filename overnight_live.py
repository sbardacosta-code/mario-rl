"""Best-effort, sampled RGB frames for an independent training viewer.

The wrapper neither changes transitions nor controls training. Its local atomic
JSON file contains one image and that image's metadata, so a reader cannot join
a new score with an older frame. No frame history is retained here.
"""
from __future__ import annotations

import base64
from io import BytesIO
import json
import math
import os
from pathlib import Path
import time
import warnings

import gymnasium as gym
import numpy as np
from PIL import Image


class LiveFrames(gym.Wrapper):
    """Sample at most five frames/second before preprocessing or auto-reset.

    Use ``render_mode='rgb_array'`` for the wrapped environment. Terminal and
    reset transitions use the same rate limit as ordinary steps; this is a
    sampled view, not a complete recording. Passing ``path=None`` disables it.
    Any publication error is counted and otherwise has no effect on training.
    """

    def __init__(self, env, path=None, *, max_fps=5.0):
        super().__init__(env)
        if not math.isfinite(max_fps) or not 0 < max_fps <= 5:
            raise ValueError("max_fps must be finite and between 0 and 5")
        self.path = Path(path) if path is not None else None
        self.interval = 1.0 / max_fps
        self.next_frame = -math.inf
        self.sequence = 0
        self.episode = 0
        self.published_frames = 0
        self.publish_errors = 0
        self._warned = False
        self._parent_ready = False

    def reset(self, **kwargs):
        observation, info = self.env.reset(**kwargs)
        self.episode += 1
        self._publish(info, action=None, reward=None, terminated=False,
                      truncated=False, event="reset")
        return observation, info

    def step(self, action):
        transition = self.env.step(action)
        _, reward, terminated, truncated, info = transition
        self._publish(info, action=action, reward=reward,
                      terminated=terminated, truncated=truncated, event="step")
        return transition

    def _publish(self, info, *, action, reward, terminated, truncated, event):
        if self.path is None:
            return
        now = time.monotonic()
        if now < self.next_frame:
            return
        self.next_frame = now + self.interval
        temporary = None
        try:
            temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
            # Render and copy before any caller can reset the emulator.
            frame = np.asarray(self.env.render()).copy()
            if frame.shape != (240, 256, 3) or frame.dtype != np.uint8:
                raise ValueError("live view expects a 256 by 240 uint8 RGB frame")
            buffer = BytesIO()
            Image.fromarray(frame).save(buffer, format="PNG", compress_level=1)
            self.sequence += 1
            numeric = lambda name: None if info.get(name) is None else int(info[name])
            objective = info.get("score_metrics", {}).get("objective_reward")
            payload = {
                "schema_version": 1, "timestamp": time.time(),
                "sequence": self.sequence, "episode": self.episode,
                "event": event, "environment_index": 0,
                "image_format": "PNG", "width": 256, "height": 240,
                "image_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
                "score": numeric("score"), "coins": numeric("coins"),
                "x": numeric("x_pos"), "time": numeric("time"),
                "flag": bool(info.get("flag_get", False)),
                "terminated": bool(terminated), "truncated": bool(truncated),
                "action": None if action is None else int(action),
                "objective_reward": None if objective is None else float(objective),
                "step_reward": None if reward is None else float(reward),
                "publish_errors": self.publish_errors,
                "one_ups": int(info.get("score_metrics", {}).get("one_ups", 0)),
                "custom_one_up_bonus": int(info.get("score_metrics", {}).get("custom_one_up_bonus", 0)),
                "flag_height_bonus": int(info.get("score_metrics", {}).get("flag_height_bonus", 0)),
                "augmented_score_gain": info.get("score_metrics", {}).get("augmented_score_gain"),
            }
            data = json.dumps(payload, allow_nan=False, separators=(",", ":"))
            if not self._parent_ready:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self._parent_ready = True
            temporary.write_text(data + "\n")
            temporary.replace(self.path)
            self.published_frames += 1
        except Exception as error:
            self.publish_errors += 1
            try:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            except OSError:
                pass
            if not self._warned:
                self._warned = True
                try:
                    warnings.warn(
                        f"Live preview unavailable ({type(error).__name__}); "
                        "training continues. Publication errors are counted on LiveFrames.",
                        RuntimeWarning, stacklevel=2,
                    )
                except Exception:
                    # A warnings-as-errors setting must not stop learning.
                    pass
