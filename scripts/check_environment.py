#!/usr/bin/env python3
"""Verify Mario World 1-1, rendering, and optional CNN inputs without training."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib import metadata
import json
import math
from pathlib import Path
import platform
import sys
import traceback


ENV_ID = "SuperMarioBros-1-1-v0"
SEED = 123
PACKAGES = (
    "gym-super-mario-bros",
    "nes-py",
    "gymnasium",
    "stable-baselines3",
    "numpy",
    "torch",
    "opencv-python",
    "pillow",
)


def bounded_steps(value: str) -> int:
    steps = int(value)
    if not 1 <= steps <= 1000:
        raise argparse.ArgumentTypeError("steps must be between 1 and 1000")
    return steps


def package_versions() -> dict[str, str | None]:
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def run_checks(args: argparse.Namespace, report: dict) -> None:
    import gymnasium as gym
    import gym_super_mario_bros  # noqa: F401: importing registers environments
    from gym_super_mario_bros.actions import RIGHT_ONLY
    from nes_py.wrappers import JoypadSpace
    import numpy as np
    from PIL import Image

    noop = RIGHT_ONLY.index(["NOOP"])
    right = RIGHT_ONLY.index(["right"])
    checks = report["checks"]

    def make_env(max_episode_steps: int = 1001):
        return JoypadSpace(
            gym.make(
                ENV_ID,
                render_mode="rgb_array",
                max_episode_steps=max_episode_steps,
            ),
            RIGHT_ONLY,
        )

    def check_observation(env, observation, expected_shape=(240, 256, 3)):
        assert isinstance(observation, np.ndarray), "observation is not an ndarray"
        assert observation.shape == expected_shape, observation.shape
        assert observation.dtype == np.uint8, observation.dtype
        assert env.observation_space.contains(observation), "observation outside space"

    def check_step(env, result, expected_shape=(240, 256, 3)):
        assert isinstance(result, tuple) and len(result) == 5, "invalid step API"
        observation, reward, terminated, truncated, info = result
        check_observation(env, observation, expected_shape)
        assert math.isfinite(float(reward)), f"non-finite reward: {reward}"
        assert isinstance(terminated, (bool, np.bool_)), type(terminated)
        assert isinstance(truncated, (bool, np.bool_)), type(truncated)
        assert isinstance(info, dict), type(info)
        return observation, float(reward), bool(terminated), bool(truncated), info

    env = make_env()
    try:
        observation, info = env.reset(seed=SEED)
        check_observation(env, observation)
        assert isinstance(info, dict), "reset info is not a dictionary"
        assert env.action_space.n == len(RIGHT_ONLY), env.action_space
        assert info["world"] == 1 and info["stage"] == 1, info
        # NES observations and RGB renders are mutable views of the native screen.
        initial_frame = observation.copy()
        rendered = env.render()
        check_observation(env, rendered)
        assert np.array_equal(rendered, initial_frame), "render differs from observation"
        assert int(rendered.max()) > int(rendered.min()), "render is a blank image"
        best_frame = rendered.copy()
        checks["native_render"] = {
            "status": "passed",
            "shape": list(rendered.shape),
            "dtype": str(rendered.dtype),
            "action_count": int(env.action_space.n),
        }

        # Seeding reset does not seed Discrete.sample(); seed the action space too.
        env.action_space.seed(SEED)
        sample_a = [int(env.action_space.sample()) for _ in range(16)]
        env.action_space.seed(SEED)
        sample_b = [int(env.action_space.sample()) for _ in range(16)]
        assert sample_a == sample_b, "action seeding is not reproducible"
        env.action_space.seed(SEED)

        total_reward = 0.0
        terminations = 0
        truncations = 0
        resets = 1
        changed_frames = 0
        best_x = int(info["x_pos"])
        previous_frame = initial_frame
        for _ in range(args.steps):
            observation, reward, terminated, truncated, info = check_step(
                env, env.step(int(env.action_space.sample()))
            )
            total_reward += reward
            changed_frames += int(not np.array_equal(observation, previous_frame))
            previous_frame = observation.copy()
            x_pos = int(info["x_pos"])
            if x_pos > best_x and not (terminated or truncated):
                best_x = x_pos
                best_frame = observation.copy()
            if terminated or truncated:
                terminations += int(terminated)
                truncations += int(truncated)
                observation, info = env.reset()
                check_observation(env, observation)
                previous_frame = observation.copy()
                resets += 1

        screenshot = args.output_dir / "mario-world-1-1.png"
        Image.fromarray(best_frame).save(screenshot)
        report["screenshot"] = str(screenshot.resolve())
        checks["random_play"] = {
            "status": "passed",
            "steps": args.steps,
            "seed": SEED,
            "action_space_seeded_separately": True,
            "total_reward": total_reward,
            "terminations": terminations,
            "truncations": truncations,
            "resets": resets,
            "changed_frames": changed_frames,
            "furthest_x": best_x,
        }
    finally:
        env.close()

    env = make_env(max_episode_steps=3)
    try:
        observation, _ = env.reset(seed=SEED)
        initial_frame = observation.copy()
        for index in range(1, 4):
            _, _, terminated, truncated, _ = check_step(env, env.step(noop))
            assert not terminated, f"unexpected termination at step {index}"
            assert truncated == (index == 3), f"incorrect truncation at step {index}"
        observation, _ = env.reset(seed=SEED)
        check_observation(env, observation)
        assert np.array_equal(initial_frame, observation), "seeded reset differs"
        _, _, terminated, truncated, _ = check_step(env, env.step(noop))
        assert not (terminated or truncated), "reset did not clear episode boundary"
        checks["time_limit"] = {
            "status": "passed",
            "truncated_at_step": 3,
            "reset_after_truncation": True,
        }
    finally:
        env.close()

    env = make_env()
    try:
        env.reset(seed=SEED)
        for index in range(1, 1001):
            _, _, terminated, truncated, info = check_step(env, env.step(right))
            assert not truncated, "death check was externally truncated"
            if terminated:
                assert not info.get("flag_get", False), "unexpected level completion"
                assert info.get("death", False), "termination was not reported as death"
                observation, _ = env.reset(seed=SEED)
                check_observation(env, observation)
                _, _, again_terminated, again_truncated, _ = check_step(
                    env, env.step(noop)
                )
                assert not (again_terminated or again_truncated), "reset after death failed"
                checks["natural_termination"] = {
                    "status": "passed",
                    "action": "right without jumping",
                    "steps_until_death": index,
                    "reset_after_death": True,
                }
                break
        else:
            raise AssertionError("holding right did not cause death within 1000 steps")
    finally:
        env.close()

    if args.skip_preprocessing:
        checks["cnn_preprocessing"] = {"status": "skipped", "reason": "CLI option"}
        return

    try:
        import cv2  # noqa: F401: ResizeObservation requires OpenCV
        from stable_baselines3.common.env_checker import check_env
    except ImportError as error:
        checks["cnn_preprocessing"] = {
            "status": "skipped",
            "reason": f"optional dependency unavailable: {error}",
        }
        return

    from gymnasium.wrappers import (
        FrameStackObservation,
        GrayscaleObservation,
        ResizeObservation,
    )

    env = make_env()
    try:
        # Resize/grayscale allocate independent images before the history is stored.
        env = ResizeObservation(env, (84, 84))
        env = GrayscaleObservation(env, keep_dim=False)
        env = FrameStackObservation(env, stack_size=4)
        check_env(env, warn=True, skip_render_check=True)
        observation, _ = env.reset(seed=SEED)
        check_observation(env, observation, (4, 84, 84))
        for _ in range(4):
            previous_stack = observation.copy()
            observation, _, terminated, truncated, _ = check_step(
                env, env.step(right), (4, 84, 84)
            )
            assert not (terminated or truncated), "unexpected preprocessing boundary"
            assert np.array_equal(previous_stack[1:], observation[:-1]), "invalid history"
        checks["cnn_preprocessing"] = {
            "status": "passed",
            "shape": list(observation.shape),
            "dtype": str(observation.dtype),
            "channel_order": "first",
            "sb3_check_env": "passed",
            "stack_history": "passed",
            "frame_skip": 1,
        }
    finally:
        env.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=bounded_steps, default=1000)
    parser.add_argument("--output-dir", type=Path, default=Path("results/setup"))
    parser.add_argument(
        "--skip-preprocessing",
        action="store_true",
        help="skip the optional Gymnasium image-wrapper and SB3 compatibility checks",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "environment": ENV_ID,
        "status": "running",
        "learning_updates": 0,
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": package_versions(),
        "checks": {},
    }
    exit_code = 0
    try:
        run_checks(args, report)
        report["status"] = "passed"
    except Exception as error:
        exit_code = 1
        report["status"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}"
        traceback.print_exc(file=sys.stderr)
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    report_file = args.output_dir / "report.json"
    report["report_file"] = str(report_file.resolve())
    encoded = json.dumps(report, indent=2, sort_keys=True)
    report_file.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
