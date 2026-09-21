"""Synthetic checks for flag resolution and life accounting; no game rollouts."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json

import gymnasium as gym
import numpy as np

from mario_events import EVENT_CONFIG, MarioEvents


class NativeFixture(gym.Env):
    action_space = gym.spaces.Discrete(256)
    observation_space = gym.spaces.Box(0, 255, (2, 2, 3), np.uint8)

    def __init__(self, rows, initial_life=2, initial_coins=0, tier=2, resolution_frames=6, actual_award=None):
        self.rows = rows
        self.initial_life = initial_life
        self.initial_coins = initial_coins
        self.tier = tier
        self.resolution_frames = resolution_frames
        self.actual_award = EVENT_CONFIG["flag_tier_points"][tier] if actual_award is None else actual_award
        self.ram = np.zeros(2048, np.uint8)
        self.screen = np.zeros((2, 2, 3), np.uint8)
        self.actions = []

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.row = self.extra_frames = 0
        self.done = False
        self.ram.fill(0)
        self.ram[0x0e] = 8
        self.info = {"score": 100, "life": self.initial_life, "coins": self.initial_coins,
                     "time": 300, "flag_get": False, "world": 1, "stage": 1, "area": 1}
        self.screen.fill(0)
        return self.screen, dict(self.info)

    def step(self, action):
        assert not self.done, "normal step called after terminal"
        self.actions.append(action)
        score, life, coins, flag, terminated = self.rows[self.row]
        self.row += 1
        self.info.update(score=score, life=life, coins=coins, flag_get=flag)
        self.done = terminated
        if flag:
            self.ram[0x0e] = 4
            self.ram[0x010f] = self.tier
            self.ram[0x070f] = 80
        self.reward = np.float64(13.25)
        return self.screen, self.reward, terminated, False, dict(self.info)

    def _frame_advance(self, action):
        assert action == 0 and self.done
        assert self.extra_frames < self.resolution_frames + 2, "advanced beyond bounded presentation phase"
        self.extra_frames += 1
        self.screen.fill(self.extra_frames)
        if self.extra_frames == self.resolution_frames:
            self.ram[0x0e] = 5
            self.info["score"] += self.actual_award

    def _get_info(self):
        return dict(self.info)


def main():
    json.dumps(EVENT_CONFIG)
    raw = NativeFixture([(100, 3, 1, False, False), (300, 3, 1, False, False), (300, 2, 1, False, True)])
    env = MarioEvents(raw)
    obs, info = env.reset(seed=10)
    rng_before = raw.np_random.bit_generator.state
    assert obs is raw.screen and info["event_metrics"]["one_ups"] == 0
    first_info = env.step(0)[4]
    assert first_info["event_metrics"]["one_ups"] == 1
    for action in (1, 2):
        obs, reward, terminated, truncated, info = env.step(action)
        assert obs is raw.screen and reward is raw.reward
    assert info["event_metrics"]["one_ups"] == 1
    assert info["event_metrics"]["one_up_source_counts"] == {"coin_rollover": 0, "other_or_unknown": 1}
    assert raw.actions == [0, 1, 2] and raw.extra_frames == 0
    assert raw.np_random.bit_generator.state == rng_before
    env.reset()
    assert env.events["one_ups"] == 0 and first_info["event_metrics"]["one_ups"] == 1

    raw = NativeFixture([(300, 3, 0, False, False)], initial_coins=99)
    env = MarioEvents(raw)
    env.reset()
    info = env.step(0)[4]
    assert info["event_metrics"]["one_ups"] == 1
    assert info["event_metrics"]["one_up_source_counts"] == {"coin_rollover": 1, "other_or_unknown": 0}
    for old_life, new_life in ((0, 255), (255, 2), (2, 1)):
        env = MarioEvents(NativeFixture([(100, new_life, 0, False, True)], initial_life=old_life))
        env.reset()
        assert env.step(0)[4]["event_metrics"]["one_ups"] == 0

    for tier, award in enumerate(EVENT_CONFIG["flag_tier_points"]):
        for frame_count in (4, 6):
            raw = NativeFixture([(700, 2, 0, True, True)], tier=tier, resolution_frames=frame_count)
            env = MarioEvents(raw, record_resolution=True)
            env.reset()
            obs, reward, terminated, truncated, info = env.step(17)
            event = info["event_metrics"]
            assert reward is raw.reward and terminated and not truncated
            assert info["score"] == 700 + award
            assert event["flag_height_bonus"] == award and event["flag_contact_score"] == 700
            assert event["flag_top_tier"] == (tier == 0)
            assert event["flag_touch_y"] == 80 and event["flag_resolution_complete"]
            assert event["post_flag_frames"] == frame_count + 2
            assert event["flag_presentation_frames"] == 2
            assert info["time"] == 300 and raw.actions == [17]
            assert sum(info["resolution_frame_counts"]) == frame_count + 2
            assert len(info["resolution_frames"]) == (frame_count + 5) // 4
            assert np.all(info["flag_contact_frame"] == 0)
            assert np.all(obs == frame_count + 2)
            raw.screen.fill(99)
            assert np.all(obs == frame_count + 2)
            assert np.all(info["resolution_frames"][-1] == frame_count + 2)

    raw = NativeFixture([(700, 2, 0, True, True)], resolution_frames=6)
    env = MarioEvents(raw, max_post_flag_frames=2)
    env.reset()
    info = env.step(0)[4]
    assert info["score"] == 700 and info["event_metrics"]["flag_height_bonus"] == 0
    assert info["event_metrics"]["flag_resolution_status"] == "frame_limit"
    assert not info["event_metrics"]["flag_resolution_complete"]
    assert raw.extra_frames == 2 and "resolution_frames" not in info

    raw = NativeFixture([(700, 2, 0, True, True)], resolution_frames=6)
    env = MarioEvents(raw, max_post_flag_frames=7)
    env.reset()
    info = env.step(0)[4]
    assert info["event_metrics"]["post_flag_frames"] == 7
    assert info["event_metrics"]["flag_presentation_frames"] == 1
    assert info["event_metrics"]["flag_resolution_status"] == "presentation_frame_limit"
    assert not info["event_metrics"]["flag_resolution_complete"]
    assert raw.extra_frames == 7 and "resolution_frames" not in info

    raw = NativeFixture([(700, 2, 0, True, True)], actual_award=200)
    env = MarioEvents(raw)
    env.reset()
    info = env.step(0)[4]
    assert info["score"] == 900 and info["event_metrics"]["flag_height_bonus"] == 200
    assert info["event_metrics"]["flag_resolution_status"] == "award_mismatch"
    assert not info["event_metrics"]["flag_resolution_complete"]
    print("PASS: native identity/RNG, cumulative life gains, death/reset/sentinel guards, coin-rollover attribution, "
          "all five real-award tier checks, bounded NOOP resolution, score mismatch, independent media and exact frame counts")


if __name__ == "__main__":
    main()
