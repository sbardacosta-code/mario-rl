"""World 1-1 observations and episode accounting shared by training and evaluation."""

from __future__ import annotations

import gymnasium as gym
import gym_super_mario_bros  # noqa: F401: registers the Mario environments
from gym_super_mario_bros.actions import RIGHT_ONLY
from gymnasium.wrappers import (
    FrameStackObservation,
    GrayscaleObservation,
    ResizeObservation,
    TimeLimit,
)
from nes_py.wrappers import JoypadSpace
import numpy as np


ENV_ID = "SuperMarioBros-1-1-v0"
FRAME_SKIP = 4
STACK_SIZE = 4
IMAGE_SIZE = (84, 84)


class ActionRepeat(gym.Wrapper):
    """Repeat an action, summing native rewards and stopping at either boundary."""

    def __init__(self, env: gym.Env, repeat: int = FRAME_SKIP):
        super().__init__(env)
        if repeat < 1:
            raise ValueError("repeat must be at least 1")
        self.repeat = repeat

    def step(self, action):
        total_reward = 0.0
        max_x = 0
        completed = False
        for count in range(1, self.repeat + 1):
            observation, reward, terminated, truncated, info = self.env.step(action)
            total_reward += float(reward)
            max_x = max(max_x, int(info.get("x_pos", 0)))
            completed |= bool(info.get("flag_get", False))
            if terminated or truncated:
                break
        info = dict(info)
        info["action_repeat_frames"] = count
        info["action_repeat_max_x"] = max_x
        info["action_repeat_flag_get"] = completed
        # The NES screen is mutable native memory; do not expose a retained view.
        return observation.copy(), total_reward, terminated, truncated, info


class EpisodeMetrics(gym.Wrapper):
    """Summarize a full episode after the decision-level time limit is applied."""

    def __init__(self, env: gym.Env, initial_seed: int | None = None):
        super().__init__(env)
        self.initial_seed = initial_seed
        self.max_x = 0
        self.completed = False
        self.raw_frames = 0
        self.decisions = 0
        self.native_reward_sum = 0.0

    def reset(self, *, seed=None, options=None):
        if seed is None and self.initial_seed is not None:
            seed = self.initial_seed
        self.initial_seed = None
        if seed is not None:
            self.action_space.seed(seed)
        observation, info = self.env.reset(seed=seed, options=options)
        self.max_x = int(info.get("x_pos", 0))
        self.completed = bool(info.get("flag_get", False))
        self.raw_frames = 0
        self.decisions = 0
        self.native_reward_sum = 0.0
        return observation, info

    def step(self, action):
        observation, reward, terminated, truncated, info = self.env.step(action)
        self.decisions += 1
        self.raw_frames += int(info["action_repeat_frames"])
        self.max_x = max(self.max_x, int(info["action_repeat_max_x"]))
        self.completed |= bool(info["action_repeat_flag_get"])
        self.native_reward_sum += float(reward)
        if terminated or truncated:
            info = dict(info)
            info["episode_metrics"] = {
                "max_x": self.max_x,
                "flag_get": self.completed,
                "completed": self.completed,
                "raw_frames": self.raw_frames,
                "decisions": self.decisions,
                "native_reward_sum": self.native_reward_sum,
            }
        return observation, reward, terminated, truncated, info


def make_env(
    *, seed: int | None = None, render_mode: str | None = None,
    max_decisions: int = 3000,
) -> gym.Env:
    """Create an unreset env with (4, 84, 84) uint8 pixels and five actions.

    ``seed`` seeds action sampling immediately and the first reset if it has no
    explicit seed. ``max_decisions`` counts agent actions, not emulator frames.
    Native RGB frames remain available through ``render_mode='rgb_array'`` and
    ``env.render()``; callers retaining renders must copy them.
    """
    if max_decisions < 1:
        raise ValueError("max_decisions must be at least 1")
    env = gym.make(
        ENV_ID, render_mode=render_mode,
        # The outer TimeLimit defines the episode budget in agent decisions.
        max_episode_steps=-1,
    )
    env = JoypadSpace(env, RIGHT_ONLY)
    env = ActionRepeat(env)
    env = TimeLimit(env, max_episode_steps=max_decisions)
    env = EpisodeMetrics(env, initial_seed=seed)
    # Resize/grayscale allocate independent images before history is retained.
    env = ResizeObservation(env, IMAGE_SIZE)
    env = GrayscaleObservation(env, keep_dim=False)
    env = FrameStackObservation(env, stack_size=STACK_SIZE)
    if seed is not None:
        env.action_space.seed(seed)
    return env


def _self_check():
    """Small boundary and actual-emulator checks; no training or file writes."""
    class BoundaryEnv(gym.Env):
        observation_space = gym.spaces.Box(0, 255, (2, 2, 3), np.uint8)
        action_space = gym.spaces.Discrete(1)

        def __init__(self, truncate):
            self.truncate = truncate
            self.calls = 0
            self.screen = np.zeros((2, 2, 3), dtype=np.uint8)

        def reset(self, *, seed=None, options=None):
            super().reset(seed=seed)
            self.calls = 0
            self.screen.fill(0)
            return self.screen, {"x_pos": 0}

        def step(self, action):
            self.calls += 1
            assert self.calls <= 3, "stepped beyond an episode boundary"
            self.screen.fill(self.calls)
            done = self.calls == 3
            return (
                self.screen, float(self.calls), done and not self.truncate,
                done and self.truncate,
                {"x_pos": self.calls, "flag_get": done, "base_info": True},
            )

    for truncated in (False, True):
        raw = BoundaryEnv(truncated)
        env = EpisodeMetrics(TimeLimit(ActionRepeat(raw), 10))
        env.reset()
        observation, reward, terminated, was_truncated, info = env.step(0)
        assert reward == 6.0 and raw.calls == 3
        assert terminated == (not truncated) and was_truncated == truncated
        assert info["base_info"]
        assert info["episode_metrics"] == {
            "max_x": 3, "flag_get": True, "completed": True,
            "raw_frames": 3, "decisions": 1, "native_reward_sum": 6.0,
        }
        env.reset()
        assert np.all(observation == 3), "returned raw observation was aliased"
        assert env.decisions == env.raw_frames == 0
        assert env.native_reward_sum == 0 and not env.completed
        env.close()

    env = make_env(seed=123, render_mode="rgb_array", max_decisions=3)
    try:
        first, info = env.reset()
        assert first.shape == (4, 84, 84) and first.dtype == np.uint8
        assert env.observation_space.contains(first)
        assert env.action_space.n == 5
        assert all(np.array_equal(first[0], frame) for frame in first)
        assert env.render().shape == (240, 256, 3)
        total_reward = 0.0
        previous = first.copy()
        for decision in range(1, 4):
            observation, reward, terminated, truncated, info = env.step(1)
            assert np.array_equal(previous[1:], observation[:-1])
            assert not terminated and truncated == (decision == 3)
            total_reward += reward
            previous = observation.copy()
        metrics = info["episode_metrics"]
        assert metrics["raw_frames"] == 12 and metrics["decisions"] == 3
        assert metrics["native_reward_sum"] == total_reward
        reset_observation, _ = env.reset(seed=123)
        assert np.array_equal(first, reset_observation)
        _, _, terminated, truncated, info = env.step(0)
        assert not (terminated or truncated) and "episode_metrics" not in info
    finally:
        env.close()
    print("PASS: early termination/truncation, reward sums, info preservation, "
          "copy isolation, decision limits, reset, stack history, and native RGB rendering")


if __name__ == "__main__":
    _self_check()
