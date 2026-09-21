"""Opt-in Mario scoring with settled flag points and explicit extra-life utility."""
from __future__ import annotations

import math
from pathlib import Path
import gymnasium as gym
import gym_super_mario_bros  # noqa: F401
from gym_super_mario_bros.actions import RIGHT_ONLY
from gymnasium.wrappers import FrameStackObservation, GrayscaleObservation, ResizeObservation, TimeLimit
from nes_py.wrappers import JoypadSpace

from mario_env import ENV_ID, FRAME_SKIP, STACK_SIZE, IMAGE_SIZE, EpisodeMetrics
from mario_events import MarioEvents


EVENT_REWARD_CONFIG = {
    "name": "settled_flag_and_extra_lives_v1",
    "score_divisor": 1000.0,
    "one_up_teaching_points": 1000,
    "completion_bonus": 5.0,
    "failure_penalty": -5.0,
    "native_scale": 0.01,
    "max_post_flag_frames": 300,
    "formula": "score_events = HUD delta / 1000 + new extra lives + 5 once on clear - 5 on nonclear end",
    "bridge_formula": "(1 - score_weight) * native_reward * 0.01 + score_weight * score_events",
    "score_measurement": "actual HUD at failure or after the flagpole award; later timer/fireworks bonuses excluded",
    "life_measurement": "positive life-counter increases within an attempt; source is coin rollover or other/unknown, not proof of a hidden block",
    "selection_metric": "actual earned HUD points + 1000 teaching points per extra life; failures count zero",
}


class EventActionRepeat(gym.Wrapper):
    """Repeat decisions while accounting for bounded automatic flag frames."""
    def __init__(self, env, repeat=FRAME_SKIP):
        super().__init__(env)
        self.repeat = repeat

    def step(self, action):
        total_reward = 0.0
        max_x = 0
        completed = False
        frames = 0
        resolution_frames = []
        for count in range(1, self.repeat + 1):
            observation, reward, terminated, truncated, info = self.env.step(action)
            total_reward += float(reward)
            max_x = max(max_x, int(info.get("x_pos", 0)))
            completed |= bool(info.get("flag_get", False))
            frames += 1
            if info.get("resolution_frames"):
                resolution_frames.extend(info["resolution_frames"])
            if terminated or truncated:
                # Settlement occurs once, on the terminal raw-frame call.
                frames += int(info.get("event_metrics", {}).get("post_flag_frames", 0))
                break
        info = dict(info)
        info.update(action_repeat_frames=frames, action_repeat_max_x=max_x,
                    action_repeat_flag_get=completed,
                    action_repeat_controlled_frames=count)
        if resolution_frames:
            info["resolution_frames"] = resolution_frames
        return observation.copy(), total_reward, terminated, truncated, info


class EventObjective(gym.Wrapper):
    def __init__(self, env, objective="score_events", score_weight=1.0):
        super().__init__(env)
        if objective not in ("score_events", "score_bridge"):
            raise ValueError("Choose score_events or score_bridge")
        if not math.isfinite(score_weight) or not 0 < score_weight <= 1:
            raise ValueError("score_weight must be in (0, 1]")
        self.objective = objective
        self.score_weight = 1.0 if objective == "score_events" else float(score_weight)

    def enrich(self, info, reward=0.0, components=None):
        info = dict(info)
        events = dict(info.get("event_metrics", {}))
        lives = int(events.get("one_ups", 0))
        points = lives * EVENT_REWARD_CONFIG["one_up_teaching_points"]
        metrics = {
            **events, "objective": self.objective, "score_weight": self.score_weight,
            "initial_score": self.initial_score, "current_score": self.current_score,
            "game_score": self.current_score, "score_gain": self.current_score - self.initial_score,
            "max_score": self.max_score, "coins": int(info.get("coins", 0)),
            "one_ups": lives, "custom_one_up_bonus": points,
            "augmented_score_gain": self.current_score - self.initial_score + points,
            "native_reward_sum": self.native_sum,
            "objective_reward": float(reward), "objective_reward_sum": self.objective_sum,
            "objective_components": dict(components or {}),
        }
        info["score_metrics"] = metrics
        if "episode_metrics" in info:
            info["episode_metrics"] = {**info["episode_metrics"], **metrics}
        return info

    def reset(self, *, seed=None, options=None):
        observation, info = self.env.reset(seed=seed, options=options)
        self.initial_score = self.current_score = self.max_score = int(info["score"])
        self.previous_lives = 0
        self.completed = False
        self.objective_sum = self.native_sum = 0.0
        return observation, self.enrich(info)

    def step(self, action):
        observation, native, terminated, truncated, info = self.env.step(action)
        current = int(info["score"])
        gain = current - self.current_score
        if gain < 0:
            raise ValueError("HUD decreased within an attempt; scoring must be investigated")
        events = info["event_metrics"]
        lives = int(events["one_ups"])
        if lives < self.previous_lives:
            raise ValueError("Extra-life count decreased within an attempt")
        clear = bool(info.get("action_repeat_flag_get") or info.get("flag_get"))
        if clear and not events.get("flag_resolution_complete", False):
            raise ValueError("Flagpole award did not settle within its bounded animation")
        components = {
            "game_points": gain / EVENT_REWARD_CONFIG["score_divisor"],
            "extra_lives": (lives - self.previous_lives) * EVENT_REWARD_CONFIG["one_up_teaching_points"] / EVENT_REWARD_CONFIG["score_divisor"],
            "completion": EVENT_REWARD_CONFIG["completion_bonus"] if clear and not self.completed else 0.0,
            "failure": EVENT_REWARD_CONFIG["failure_penalty"] if (terminated or truncated) and not (self.completed or clear) else 0.0,
        }
        event_reward = sum(components.values())
        reward = (1-self.score_weight) * float(native) * EVENT_REWARD_CONFIG["native_scale"] + self.score_weight * event_reward
        components.update(event_reward=event_reward, native_reward=float(native), weighted_native=(1-self.score_weight)*float(native)*EVENT_REWARD_CONFIG["native_scale"], weighted_events=self.score_weight*event_reward)
        self.current_score = current
        self.max_score = max(self.max_score, current)
        self.previous_lives = lives
        self.completed |= clear
        self.native_sum += float(native)
        self.objective_sum += float(reward)
        return observation, float(reward), terminated, truncated, self.enrich(info, reward, components)


def make_env(*, seed=None, render_mode=None, max_decisions=3000,
             objective="score_events", score_weight=1.0,
             live_frame_path: str | Path | None = None, record_resolution=False):
    if max_decisions < 1:
        raise ValueError("max_decisions must be positive")
    if live_frame_path is not None or record_resolution:
        render_mode = "rgb_array"
    env = gym.make(ENV_ID, render_mode=render_mode, max_episode_steps=-1)
    env = MarioEvents(env, max_post_flag_frames=EVENT_REWARD_CONFIG["max_post_flag_frames"], record_resolution=record_resolution)
    env = JoypadSpace(env, RIGHT_ONLY)
    env = EventActionRepeat(env)
    env = TimeLimit(env, max_episode_steps=max_decisions)
    env = EpisodeMetrics(env, initial_seed=seed)
    env = EventObjective(env, objective=objective, score_weight=score_weight)
    if live_frame_path is not None:
        from overnight_live import LiveFrames
        env = LiveFrames(env, path=live_frame_path)
    env = ResizeObservation(env, IMAGE_SIZE)
    env = GrayscaleObservation(env, keep_dim=False)
    env = FrameStackObservation(env, stack_size=STACK_SIZE)
    if seed is not None:
        env.action_space.seed(seed)
    return env
