"""Optional HUD-score rewards without changing the historical native objective.

Place ``GameScore`` outside ``EpisodeMetrics`` so its native reward totals keep
their original meaning. Observations, actions, RNGs, and episode boundaries are
unchanged. World 1-1 terminates at flag touch; later flag and time bonuses are
therefore excluded from these score measurements.
"""

from __future__ import annotations

from numbers import Integral

import gymnasium as gym


SCORE_REWARD_CONFIG = {
    "name": "score_before_flag_v1",
    "score_divisor": 1000.0,
    "completion_bonus": 5.0,
    "failure_penalty": -5.0,
    "formula": "score_delta / 1000 + 5 once on clear - 5 on nonclear episode end",
    "metric_definition": (
        "points earned before flag touch; postflag/time bonuses excluded"
    ),
    "coins_reward": 0.0,
    "progress_reward": 0.0,
    "time_reward": 0.0,
    "score_decrease_policy": "error in score mode; explicit anomaly in native mode",
}


class GameScore(gym.Wrapper):
    """Track actual game points and optionally reward their increase.

    Native mode returns the exact original reward object, including for episodes
    with a score decrease. Such decreases are recorded as anomalies and retain
    their signed contribution to score gain. Score mode rejects a decrease
    because neither a score rollover nor a reset may be silently rewarded.
    """

    def __init__(self, env: gym.Env, objective: str = "native"):
        super().__init__(env)
        if objective not in {"native", "score"}:
            raise ValueError("objective must be 'native' or 'score'")
        self.objective = objective
        self.initial_score = None
        self.current_score = None
        self.max_score = None
        self.coins = None
        self.objective_reward_sum = 0.0
        self.score_anomalies = []
        self.completed = False
        self.failure_rewarded = False
        self.transitions = 0

    @staticmethod
    def _score(info):
        if "score" not in info:
            raise ValueError("GameScore requires info['score'] on reset and every step")
        score = info["score"]
        if isinstance(score, bool) or not isinstance(score, Integral) or score < 0:
            raise ValueError("GameScore requires a nonnegative integer HUD score")
        return int(score)

    def _metrics(self, reward, components):
        metrics = {
            "initial_score": self.initial_score,
            "current_score": self.current_score,
            "score_gain": self.current_score - self.initial_score,
            "max_score": self.max_score,
            "coins": self.coins,
            "objective": self.objective,
            "objective_reward": float(reward),
            "objective_reward_sum": self.objective_reward_sum,
            "objective_components": dict(components),
        }
        if self.score_anomalies:
            metrics["score_anomalies"] = [dict(item) for item in self.score_anomalies]
        return metrics

    def reset(self, *, seed=None, options=None):
        observation, info = self.env.reset(seed=seed, options=options)
        score = self._score(info)
        self.initial_score = self.current_score = self.max_score = score
        self.coins = info.get("coins")
        self.objective_reward_sum = 0.0
        self.score_anomalies = []
        self.completed = False
        self.failure_rewarded = False
        self.transitions = 0
        info = dict(info)
        components = {"native_reward": 0.0} if self.objective == "native" else {
            "score": 0.0, "completion": 0.0, "failure": 0.0,
        }
        info["score_metrics"] = self._metrics(0.0, components)
        return observation, info

    def step(self, action):
        if self.initial_score is None:
            raise RuntimeError("GameScore requires reset() before step()")
        observation, native_reward, terminated, truncated, info = self.env.step(action)
        score = self._score(info)
        delta = score - self.current_score
        self.transitions += 1
        if delta < 0:
            anomaly = {
                "transition": self.transitions,
                "previous_score": self.current_score,
                "current_score": score,
                "score_delta": delta,
                "reason": "HUD score decreased within one episode",
            }
            if self.objective == "score":
                raise ValueError(
                    f"HUD score decreased within one episode: "
                    f"{self.current_score} -> {score}; score reward is undefined"
                )
            self.score_anomalies.append(anomaly)
        self.current_score = score
        self.max_score = max(self.max_score, score)
        self.coins = info.get("coins")
        metrics = info.get("episode_metrics", {})
        clear = bool(
            info.get("flag_get", False)
            or info.get("action_repeat_flag_get", False)
            or metrics.get("completed", False)
            or metrics.get("flag_get", False)
        )
        new_clear = clear and not self.completed
        self.completed |= clear
        failed = bool(terminated or truncated) and not self.completed
        new_failure = failed and not self.failure_rewarded
        self.failure_rewarded |= failed

        if self.objective == "native":
            reward = native_reward
            components = {"native_reward": float(native_reward)}
        else:
            components = {
                "score": delta / SCORE_REWARD_CONFIG["score_divisor"],
                "completion": SCORE_REWARD_CONFIG["completion_bonus"] if new_clear else 0.0,
                "failure": SCORE_REWARD_CONFIG["failure_penalty"] if new_failure else 0.0,
            }
            reward = float(sum(components.values()))
        self.objective_reward_sum += float(reward)
        info = dict(info)
        info["score_metrics"] = self._metrics(reward, components)
        if terminated or truncated:
            episode_metrics = dict(metrics)
            episode_metrics.update(
                game_score=self.current_score,
                initial_score=self.initial_score,
                score_gain=self.current_score - self.initial_score,
                max_score=self.max_score,
                coins=self.coins,
                objective_reward_sum=self.objective_reward_sum,
            )
            if self.score_anomalies:
                episode_metrics["score_anomalies"] = [
                    dict(item) for item in self.score_anomalies
                ]
            info["episode_metrics"] = episode_metrics
        return observation, reward, terminated, truncated, info
