"""Focused behavioral checks for score accounting and the objective boundary."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json

import gymnasium as gym
import numpy as np

from score_objective import GameScore, SCORE_REWARD_CONFIG


class ScriptedEnv(gym.Env):
    action_space = gym.spaces.Discrete(5)
    observation_space = gym.spaces.Box(0, 255, (2, 2, 3), dtype=np.uint8)

    def __init__(self, rows, initial_score=100):
        self.rows = rows
        self.initial_score = initial_score
        self.observation = np.zeros((2, 2, 3), np.uint8)
        self.last_info = None
        self.last_reward = None
        self.actions = []

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.index = 0
        self.native_sum = 0.0
        self.last_info = {"score": self.initial_score, "coins": 0, "flag_get": False}
        return self.observation, self.last_info

    def step(self, action):
        self.actions.append(action)
        row = self.rows[self.index]
        self.index += 1
        score, coins, native, clear, terminated, truncated = row
        self.last_reward = np.float64(native)
        self.native_sum += native
        self.last_info = {"score": score, "coins": coins, "flag_get": clear}
        if terminated or truncated:
            self.last_info["episode_metrics"] = {
                "native_reward_sum": self.native_sum,
                "completed": clear,
                "custom_field": "preserve me",
            }
        return self.observation, self.last_reward, terminated, truncated, self.last_info


def close(a, b):
    assert np.isclose(a, b), (a, b)


def main():
    json.dumps(SCORE_REWARD_CONFIG)
    rows = [(300, 1, 15.0, False, False, False), (400, 1, 7.0, True, True, False)]
    raw = ScriptedEnv(rows)
    env = GameScore(raw)
    observation, reset_info = env.reset(seed=123)
    assert observation is raw.observation
    assert "score_metrics" not in raw.last_info
    assert reset_info["score_metrics"]["score_gain"] == 0
    original_rng = raw.np_random.bit_generator.state
    for action in (2, 4):
        observation, reward, terminated, truncated, info = env.step(action)
        assert observation is raw.observation
        assert reward is raw.last_reward
        assert "score_metrics" not in raw.last_info
    assert raw.actions == [2, 4]
    assert raw.np_random.bit_generator.state == original_rng
    assert info["episode_metrics"]["native_reward_sum"] == 22.0
    assert info["episode_metrics"]["custom_field"] == "preserve me"
    assert "game_score" not in raw.last_info["episode_metrics"]
    assert info["episode_metrics"]["game_score"] == 400
    assert info["episode_metrics"]["score_gain"] == 300
    close(info["episode_metrics"]["objective_reward_sum"], 22.0)
    env.reset()
    assert env.objective_reward_sum == 0 and env.current_score == 100

    raw = ScriptedEnv(rows + [(400, 99, 99.0, True, True, False)])
    env = GameScore(raw, objective="score")
    env.reset()
    _, reward, _, _, info = env.step(0)
    close(reward, 0.2)
    assert info["score_metrics"]["objective_components"] == {
        "score": 0.2, "completion": 0.0, "failure": 0.0,
    }
    _, reward, terminated, truncated, info = env.step(0)
    close(reward, 5.1)
    close(info["episode_metrics"]["objective_reward_sum"], 5.3)
    assert info["episode_metrics"]["native_reward_sum"] == 22.0
    _, reward, _, _, info = env.step(0)
    close(reward, 0.0)  # Neither repeated clear nor extra coins adds points.
    assert info["episode_metrics"]["coins"] == 99
    env.reset()
    env.step(0)
    _, reward, _, _, _ = env.step(0)
    close(reward, 5.1)  # Reset permits the next episode's completion bonus.

    for terminated, truncated in ((True, False), (False, True), (True, True)):
        env = GameScore(ScriptedEnv([(300, 1, 15, False, terminated, truncated)]), "score")
        env.reset()
        _, reward, actual_term, actual_trunc, info = env.step(0)
        close(reward, -4.8)
        assert (actual_term, actual_trunc) == (terminated, truncated)
        assert info["score_metrics"]["objective_components"]["failure"] == -5
    env = GameScore(ScriptedEnv([(100, 0, 0, True, True, True)]), "score")
    env.reset()
    close(env.step(0)[1], 5.0)  # Clear wins over a simultaneous decision cap.

    env = GameScore(ScriptedEnv([(50, 0, 7, False, True, False)]), "score")
    env.reset()
    try:
        env.step(0)
        raise AssertionError("score decrease was not rejected")
    except ValueError as error:
        assert "HUD score decreased" in str(error)
    raw = ScriptedEnv([(50, 0, 7, False, True, False)])
    env = GameScore(raw)
    env.reset()
    _, reward, _, _, info = env.step(0)
    assert reward is raw.last_reward
    assert info["episode_metrics"]["score_gain"] == -50
    assert len(info["episode_metrics"]["score_anomalies"]) == 1
    env.reset()
    assert env.score_anomalies == []

    for invalid in ({}, {"score": -1}, {"score": 2.5}, {"score": True}):
        try:
            GameScore._score(invalid)
            raise AssertionError("invalid score accepted")
        except ValueError:
            pass
    assert GameScore._score({"score": np.int64(200)}) == 200
    try:
        GameScore(ScriptedEnv([]), objective="unknown")
        raise AssertionError("invalid objective accepted")
    except ValueError:
        pass
    print("PASS: native reward identity, observations/actions/RNG, score deltas, no extra coin reward, "
          "completion once, termination/truncation failure, reset, score guards, and metric preservation")


if __name__ == "__main__":
    main()
