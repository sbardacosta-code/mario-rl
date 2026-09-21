"""Focused synthetic overnight checks; no ROM rollout, model load, or learning."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collections import deque
import csv
import io
import math
from pathlib import Path
import sys
import time
from types import SimpleNamespace

# Permit reviewing this staged file from the repository before installation.
sys.path.insert(1, str(Path.cwd()))

import gymnasium as gym
import numpy as np
from gymnasium.wrappers import TimeLimit

from mario_env import EpisodeMetrics
from overnight_env import EventActionRepeat, EventObjective
from overnight_train import SessionCallback


FIELDS = ["elapsed_seconds", "timesteps", "return", "length", "max_x", "completed",
          "game_score", "score_gain", "coins", "objective_reward_sum", "one_ups",
          "custom_one_up_bonus", "augmented_score_gain", "flag_height_bonus", "flag_touch_y", "flag_top_tier"]


def events(lives=0, flag=False, extra_frames=0):
    return {"one_ups": lives, "one_up_source_counts": {"coin_rollover": 0, "other_or_unknown": lives},
            "flag_height_bonus": 400 if flag else 0, "flag_touch_y": 120 if flag else None,
            "flag_contact_score": 1100 if flag else None, "flag_score_tier": 3 if flag else None,
            "flag_top_tier": False, "post_flag_frames": extra_frames,
            "flag_resolution_complete": flag, "flag_resolution_status": "complete" if flag else "not_reached"}


class RawEvents(gym.Env):
    action_space = gym.spaces.Discrete(5)
    observation_space = gym.spaces.Box(0, 255, (2, 2, 3), np.uint8)

    def __init__(self, rows):
        self.rows = rows
        self.screen = np.zeros((2, 2, 3), np.uint8)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.index = 0
        self.screen.fill(0)
        return self.screen, {"score": 100, "coins": 0, "x_pos": 0,
                             "flag_get": False, "event_metrics": events()}

    def step(self, action):
        assert self.index < len(self.rows), "stepped past scripted episode"
        score, lives, coins, native, flag, terminated, extra_frames = self.rows[self.index]
        self.index += 1
        self.screen.fill(self.index)
        info = {"score": score, "coins": coins, "x_pos": self.index * 10,
                "flag_get": flag, "event_metrics": events(lives, flag, extra_frames)}
        if extra_frames:
            info["flag_contact_frame"] = self.screen.copy()
            info["resolution_frames"] = [self.screen.copy(), self.screen.copy()]
            info["resolution_frame_counts"] = [4, extra_frames - 4]
        return self.screen, float(native), terminated, False, info


def wrapped(rows, *, objective="score_events", weight=1.0, repeat=4, limit=10):
    return EventObjective(EpisodeMetrics(TimeLimit(EventActionRepeat(RawEvents(rows), repeat=repeat), limit)),
                          objective=objective, score_weight=weight)


def same(actual, expected):
    assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12), (actual, expected)


def check_env():
    flag_rows = [(1100, 1, 2, 3, False, False, 0), (1500, 1, 2, 7, True, True, 6)]
    for objective, weight, expected in (("score_events", 0.25, 7.4),
                                         ("score_bridge", 0.25, 1.925),
                                         ("score_bridge", 1.0, 7.4)):
        env = wrapped(flag_rows, objective=objective, weight=weight)
        obs, info = env.reset(seed=44)
        rng = env.unwrapped.np_random.bit_generator.state
        assert info["score_metrics"]["initial_score"] == 100
        obs, reward, terminated, truncated, info = env.step(4)
        same(reward, expected)
        assert terminated and not truncated
        assert env.unwrapped.np_random.bit_generator.state == rng
        assert info["action_repeat_controlled_frames"] == 2
        assert info["action_repeat_frames"] == 8  # Two controlled + six automatic.
        assert sum(info["resolution_frame_counts"]) == 6
        assert info["episode_metrics"]["raw_frames"] == 8
        assert info["episode_metrics"]["decisions"] == 1
        assert info["episode_metrics"]["native_reward_sum"] == 10
        assert info["episode_metrics"]["completed"]
        score = info["score_metrics"]
        assert score["game_score"] == 1500 and score["score_gain"] == 1400
        assert score["custom_one_up_bonus"] == 1000
        assert score["augmented_score_gain"] == 2400
        assert score["flag_height_bonus"] == 400
        # The 400 flag points already appear in HUD delta; do not add them again.
        same(score["objective_components"]["event_reward"], 1.4 + 1 + 5)
        before_reset = obs.copy()
        env.reset()
        assert np.array_equal(obs, before_reset), "observation alias after reset"
        assert env.current_score == 100 and env.previous_lives == 0
        same(env.native_sum, 0)
        same(env.objective_sum, 0)

    # The same extra life persists in raw info for later frames but is paid once.
    rows = [(300, 0, 1, 8, False, False, 0), (300, 1, 1, 8, False, False, 0),
            (300, 1, 90, 8, False, False, 0)]
    env = wrapped(rows, repeat=1, limit=3)
    env.reset()
    same(env.step(0)[1], .2)
    same(env.step(0)[1], 1.0)
    _, reward, terminated, truncated, info = env.step(0)
    same(reward, -5.0)
    assert truncated and not terminated
    same(info["score_metrics"]["objective_reward_sum"], -3.8)
    assert info["episode_metrics"]["native_reward_sum"] == 24
    assert info["episode_metrics"]["one_ups"] == 1
    assert info["episode_metrics"]["augmented_score_gain"] == 1200
    assert info["episode_metrics"]["coins"] == 90  # More coins alone add no reward.

    # A flag at the exact decision limit is a clear, never a failure penalty.
    env = wrapped(flag_rows, limit=1)
    env.reset()
    _, reward, terminated, truncated, info = env.step(0)
    assert terminated and truncated
    same(reward, 7.4)
    assert info["score_metrics"]["objective_components"]["failure"] == 0

    for rows, error_text in (([(99, 0, 0, 0, False, False, 0)], "HUD decreased"),
                              ([(100, 1, 0, 0, False, False, 0), (100, 0, 0, 0, False, False, 0)], "Extra-life count")):
        env = wrapped(rows, repeat=1)
        env.reset()
        try:
            for _ in rows:
                env.step(0)
            raise AssertionError("invalid score/event transition accepted")
        except ValueError as error:
            assert error_text in str(error)

    raw = RawEvents([(1500, 0, 0, 0, True, True, 0)])
    env = EventObjective(EpisodeMetrics(TimeLimit(EventActionRepeat(raw), 10)))
    env.reset()
    original_step = raw.step

    def unresolved(action):
        obs, reward, terminated, truncated, info = original_step(action)
        info["event_metrics"]["flag_resolution_complete"] = False
        return obs, reward, terminated, truncated, info

    raw.step = unresolved
    try:
        env.step(0)
        raise AssertionError("unresolved flag accepted")
    except ValueError as error:
        assert "did not settle" in str(error)
    return info["episode_metrics"]


def callback_fixture(elapsed=301):
    callback = SessionCallback(Path("/private/tmp/unused-overnight-check"), 900, None, 60)
    callback.started = time.monotonic() - elapsed
    callback.next_progress = callback.next_print = callback.next_checkpoint = callback.next_archive = math.inf
    callback.model = SimpleNamespace(num_timesteps=123)
    callback.locals = {"dones": [], "infos": []}
    callback.csv_file = io.StringIO()
    callback.writer = csv.DictWriter(callback.csv_file, fieldnames=FIELDS)
    callback.writer.writeheader()
    return callback


def check_callback():
    # Exercise actual CSV extraction, so malformed metric keys cannot hide behind
    # a synthetic learner that never completes an episode.
    env = wrapped([(1100, 1, 2, 3, False, False, 0), (1500, 1, 2, 7, True, True, 6)])
    env.reset()
    info = env.step(0)[4]
    callback = callback_fixture()
    callback.locals = {"dones": [True], "infos": [info]}
    assert callback._on_step()
    row = list(csv.DictReader(io.StringIO(callback.csv_file.getvalue())))[0]
    assert row["one_ups"] == "1" and row["custom_one_up_bonus"] == "1000"
    assert row["flag_height_bonus"] == "400" and row["flag_touch_y"] == "120"
    same(float(row["objective_reward_sum"]), 7.4)
    assert set(callback.recent[-1]) == set(FIELDS)

    # The guard is deliberately not a checkpoint-selection decision. It stops
    # only after both the time and completed-episode sample limits are reached.
    for elapsed, count, clears, expected in ((299, 100, 0, True), (301, 99, 0, True),
                                             (301, 100, 20, True), (301, 100, 19, False)):
        callback = callback_fixture(elapsed)
        callback.recent = deque([{"completed": int(i < clears)} for i in range(count)], maxlen=100)
        assert callback._on_step() is expected, (elapsed, count, clears)
        if not expected:
            assert callback.stop_reason == "training_regression_requires_evaluation"


if __name__ == "__main__":
    check_env()
    print("PASS: bridge/event formulas, native metrics, no double-counted flag/1UP/coins, automatic frame accounting, reset, truncation, and unresolved-event guards")
    check_callback()
    print("PASS: callback CSV event extraction and regression-guard time/sample/threshold boundaries")
