#!/usr/bin/env python3
"""Verify reward scaling preserves game transitions and native episode metrics."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from stable_baselines3.common.monitor import Monitor
from mario_env import make_env
from train import ScaleReward


def check(actions, max_decisions, scale, expected_boundary):
    native = Monitor(make_env(seed=123, max_decisions=max_decisions))
    scaled = Monitor(ScaleReward(make_env(seed=123, max_decisions=max_decisions), scale))
    try:
        first, _ = native.reset()
        other, _ = scaled.reset()
        assert np.array_equal(first, other)
        total_native = total_scaled = 0.0
        for step in range(max_decisions):
            action = actions[step % len(actions)]
            obs_a, reward_a, term_a, trunc_a, info_a = native.step(action)
            obs_b, reward_b, term_b, trunc_b, info_b = scaled.step(action)
            assert np.array_equal(obs_a, obs_b)
            assert (term_a, trunc_a) == (term_b, trunc_b)
            assert np.isclose(reward_b, reward_a * scale)
            assert info_a.get('episode_metrics') == info_b.get('episode_metrics')
            total_native += reward_a
            total_scaled += reward_b
            if term_a or trunc_a:
                assert (term_a, trunc_a) == expected_boundary
                assert np.isclose(info_b['episode_metrics']['native_reward_sum'], total_native)
                assert np.isclose(total_scaled, total_native * scale)
                assert np.isclose(info_b['episode']['r'], total_scaled)
                return
        raise AssertionError('No episode boundary checked')
    finally:
        native.close()
        scaled.close()


if __name__ == '__main__':
    for scale in (1.0, 0.01):
        check([2], 100, scale, (True, False))
        check([1, 3, 2, 4, 0], 100, scale, (False, True))
    for scale in (0, -1, float('nan'), float('inf')):
        env = make_env(max_decisions=1)
        try:
            try:
                ScaleReward(env, scale)
            except ValueError:
                pass
            else:
                raise AssertionError('Accepted an invalid reward scale')
        finally:
            env.close()
    print('PASS: scaled rewards, unchanged observations/native scores, termination, truncation, Monitor units, and invalid scales')
