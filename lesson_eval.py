#!/usr/bin/env python3
"""Evaluate a saved Mario policy and preserve portable evidence for a lesson.

No gradients, optimizer calls or weight updates occur here. Each output directory
is an immutable stage: reruns must use a new, empty directory.
"""

from __future__ import annotations

import argparse
from collections import deque
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time


TRACE_FIELDS = [
    "decision", "raw_frames", "x", "y", "max_x", "action", "action_name",
    "prob_0", "prob_1", "prob_2", "prob_3", "prob_4", "action_entropy_nats",
    "native_reward", "native_reward_sum", "no_progress_decisions", "life",
    "game_time", "flag_get", "terminated", "truncated",
]


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def positive_float(value: str) -> float:
    number = float(value)
    if not 0 < number < float("inf"):
        raise argparse.ArgumentTypeError("must be finite and positive")
    return number


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303, 404, 505])
    parser.add_argument("--video-seeds", nargs="*", type=int, default=[101, 202, 303])
    parser.add_argument("--max-decisions", type=positive_int, default=3000)
    parser.add_argument("--max-seconds", type=positive_float, default=180.0)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--deterministic", action="store_true", help="choose the most probable action instead of sampling")
    parser.add_argument("--beginning-decisions", type=positive_int, default=150)
    parser.add_argument("--ending-decisions", type=positive_int, default=75)
    parser.add_argument("--stall-decisions", type=positive_int, default=120)
    args = parser.parse_args()
    if len(set(args.seeds)) != len(args.seeds):
        parser.error("seeds must be distinct")
    if any(seed < 0 or seed >= 2**32 for seed in args.seeds):
        parser.error("seeds must be between 0 and 2**32 - 1")
    if not set(args.video_seeds).issubset(args.seeds):
        parser.error("video-seeds must be included in seeds; use --video-seeds to disable clips")
    if not args.model.is_file():
        parser.error(f"model does not exist: {args.model}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if any(args.output_dir.iterdir()):
        parser.error("output-dir must be empty; published stages must not be overwritten")
    # Exclusive creation also prevents two evaluators claiming the same directory.
    with (args.output_dir / ".stage-claimed").open("x") as claim:
        claim.write(datetime.now(timezone.utc).isoformat() + "\n")

    started = time.monotonic()
    deadline = started + args.max_seconds
    report_path = args.output_dir / "evaluation.json"
    report = {
        "schema_version": 2,
        "status": "running",
        "model": str(args.model.resolve()),
        "model_sha256": sha256(args.model),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "learning_updates": 0,
        "protocol": {
            "version": 2,
            "environment": "SuperMarioBros-1-1-v0",
            "seeds": args.seeds,
            "max_decisions": args.max_decisions,
            "deterministic": args.deterministic,
            "seed_method": "SB3 set_random_seed plus environment reset(seed)",
            "action_space": "RIGHT_ONLY",
            "action_repeat": 4,
            "observation_shape": [4, 84, 84],
            "reward": "native reward summed over repeated frames",
            "device": args.device,
            "stall_threshold_decisions": args.stall_decisions,
            "stall_definition": "consecutive decisions without a new maximum x position",
        },
        "media_protocol": {
            "video_seeds": args.video_seeds,
            "beginning_decisions": args.beginning_decisions,
            "ending_decisions": args.ending_decisions,
            "format": "GIF excerpts plus PNG last frame",
            "timing": "approximately game speed; repeated native frames / 60 fps, rounded to GIF centiseconds",
            "full_episode": False,
        },
        "max_seconds": args.max_seconds,
        "episodes": [],
        "partial_episode": None,
        "mean_max_x": None,
        "mean_native_reward": None,
        "level_completions": 0,
        "completion_rate": None,
        "limitations": [
            "Small fixed-seed evaluation is descriptive, not proof of general skill.",
            "Deterministic actions on the same level and initial state can repeat the same trajectory across seeds."
            if args.deterministic else "Seeds vary sampled policy actions on the same level and initial state.",
            "GIFs show excerpts; the CSV contains every decision in the trial.",
            "A stalled maximum does not establish that Mario cannot move or identify a collision.",
            "A non-clearing termination does not identify a death cause; inspect the clip.",
        ],
    }

    def save_report() -> None:
        episodes = report["episodes"]
        count = len(episodes)
        report["finished_episodes"] = count
        report["planned_episodes"] = len(args.seeds)
        report["mean_max_x"] = sum(e["max_x"] for e in episodes) / count if count else None
        report["mean_native_reward"] = sum(e["native_reward"] for e in episodes) / count if count else None
        report["level_completions"] = sum(e["completed"] for e in episodes)
        report["completion_rate"] = report["level_completions"] / count if count else None
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        write_json(report_path, report)

    save_report()
    exit_code = 0
    try:
        import numpy as np
        from PIL import Image
        import torch
        from stable_baselines3 import PPO
        from stable_baselines3.common.utils import set_random_seed
        from gym_super_mario_bros.actions import RIGHT_ONLY
        from mario_env import make_env

        torch.set_num_threads(1)
        model = PPO.load(args.model, device=args.device)
        model.policy.set_training_mode(False)
        if int(model.action_space.n) != 5:
            raise ValueError("This evaluator expects the five RIGHT_ONLY actions")
        report["action_labels"] = {str(i): "+".join(buttons) for i, buttons in enumerate(RIGHT_ONLY)}

        def save_media(seed_dir: Path, beginnings: list, endings: deque, last_image) -> dict:
            media = {}
            for label, frames in (("beginning", beginnings), ("ending", list(endings))):
                if not frames:
                    continue
                gif_path = seed_dir / f"{label}.gif"
                images = [frame[1] for frame in frames]
                durations = [max(10, round(frame[2] * 100 / 60) * 10) for frame in frames]
                images[0].save(gif_path, save_all=True, append_images=images[1:], duration=durations, loop=0, optimize=False)
                media[label] = {
                    "path": gif_path.relative_to(args.output_dir).as_posix(),
                    "first_decision": frames[0][0],
                    "last_decision": frames[-1][0],
                    "captured_frames": len(frames),
                    "duration_seconds": round(sum(durations) / 1000, 3),
                    "is_full_episode": complete_episode and frames[0][0] == 1 and frames[-1][0] == decisions,
                }
            if last_image is not None:
                image_path = seed_dir / "last-frame.png"
                last_image.save(image_path)
                media["terminal_frame"] = image_path.relative_to(args.output_dir).as_posix()
            return media

        for seed in args.seeds:
            if time.monotonic() >= deadline:
                report["status"] = "incomplete"
                report["reason"] = "overall wall-time limit reached"
                break
            set_random_seed(seed, using_cuda=str(args.device).startswith("cuda"))
            env = make_env(seed=seed, render_mode="rgb_array", max_decisions=args.max_decisions)
            seed_dir = args.output_dir / f"seed-{seed}"
            seed_dir.mkdir()
            trace_path = seed_dir / "trace.csv"
            beginnings, endings = [], deque(maxlen=args.ending_decisions)
            last_image = None
            decisions = raw_frames = 0
            native_reward = 0.0
            max_x = last_x = 0
            last_y = None
            stalled = longest_stall = 0
            stall_start = stall_x = None
            stall_events = []
            action_counts = [0] * 5
            entropy_sum = 0.0
            terminated = truncated = False
            info = {}
            episode_started = time.monotonic()
            complete_episode = False
            try:
                observation, info = env.reset(seed=seed)
                max_x = last_x = int(info.get("x_pos", 0))
                with trace_path.open("x", newline="") as trace:
                    writer = csv.DictWriter(trace, fieldnames=TRACE_FIELDS, lineterminator="\n")
                    writer.writeheader()
                    for decision in range(1, args.max_decisions + 1):
                        if time.monotonic() >= deadline:
                            report["status"] = "incomplete"
                            report["reason"] = "overall wall-time limit reached"
                            break
                        with torch.no_grad():
                            tensor, _ = model.policy.obs_to_tensor(observation)
                            distribution = model.policy.get_distribution(tensor)
                            probabilities = distribution.distribution.probs[0].cpu().numpy()
                            action = int(distribution.get_actions(deterministic=args.deterministic).cpu().item())
                            entropy = float(distribution.entropy().cpu().item())
                        observation, reward, terminated, truncated, info = env.step(action)
                        decisions = decision
                        frame_count = int(info.get("action_repeat_frames", 4))
                        raw_frames += frame_count
                        native_reward += float(reward)
                        last_x = int(info.get("x_pos", 0))
                        last_y = int(info["y_pos"]) if "y_pos" in info else None
                        reached_x = int(info.get("action_repeat_max_x", last_x))
                        if reached_x > max_x:
                            if stalled >= args.stall_decisions:
                                stall_events.append({"start_decision": stall_start, "end_decision": decision - 1, "decisions": stalled, "previous_max_x": stall_x, "resolved_with_new_max": True})
                            max_x = reached_x
                            stalled = 0
                            stall_start = stall_x = None
                        else:
                            if stalled == 0:
                                stall_start, stall_x = decision, max_x
                            stalled += 1
                            longest_stall = max(longest_stall, stalled)
                        action_counts[action] += 1
                        entropy_sum += entropy
                        row = {
                            "decision": decision, "raw_frames": raw_frames,
                            "x": last_x, "y": last_y, "max_x": max_x,
                            "action": action, "action_name": report["action_labels"][str(action)],
                            "action_entropy_nats": entropy,
                            "native_reward": float(reward), "native_reward_sum": native_reward,
                            "no_progress_decisions": stalled,
                            "life": info.get("life"), "game_time": info.get("time"),
                            "flag_get": int(bool(info.get("flag_get", False))),
                            "terminated": int(terminated), "truncated": int(truncated),
                        }
                        row.update({f"prob_{i}": float(probabilities[i]) for i in range(5)})
                        writer.writerow(row)
                        if seed in args.video_seeds:
                            frame = np.asarray(env.render())
                            if frame.ndim != 3 or frame.shape[-1] != 3:
                                raise ValueError(f"Expected native RGB rendering; got {frame.shape}")
                            last_image = Image.fromarray(frame.copy())
                            # Native NES colours fit comfortably within a 128-colour palette.
                            packed = last_image.convert("P", palette=Image.Palette.ADAPTIVE, colors=128)
                            record = (decision, packed, frame_count)
                            if len(beginnings) < args.beginning_decisions:
                                beginnings.append(record)
                            endings.append(record)
                        if terminated or truncated:
                            complete_episode = True
                            break
                if stalled >= args.stall_decisions:
                    stall_events.append({"start_decision": stall_start, "end_decision": decisions, "decisions": stalled, "previous_max_x": stall_x, "resolved_with_new_max": False})
                metrics = info.get("episode_metrics", {})
                completed = bool(metrics.get("completed", info.get("flag_get", False)))
                if completed:
                    end_reason = "level_completed"
                elif terminated:
                    end_reason = "episode_ended_without_flag"
                elif truncated:
                    end_reason = "decision_limit"
                else:
                    end_reason = "evaluation_wall_time_limit" if report["status"] == "incomplete" else "decision_limit_without_environment_boundary"
                episode = {
                    "seed": seed, "max_x": int(metrics.get("max_x", max_x)),
                    "last_x": last_x, "last_y": last_y,
                    "completed": completed, "flag_get": bool(info.get("flag_get", completed)),
                    "native_reward": float(metrics.get("native_reward_sum", native_reward)),
                    "decisions": decisions, "raw_frames": raw_frames,
                    "terminated": bool(terminated), "truncated": bool(truncated),
                    "end_reason": end_reason,
                    "death_cause": "unknown" if terminated and not completed else None,
                    "last_life": info.get("life"), "last_game_time": info.get("time"),
                    "longest_no_progress_decisions": longest_stall,
                    "stall_events": stall_events,
                    "action_counts": action_counts,
                    "mean_action_entropy_nats": entropy_sum / decisions if decisions else None,
                    "trace_csv": trace_path.relative_to(args.output_dir).as_posix(),
                    "trace_rows": decisions,
                    "media": save_media(seed_dir, beginnings, endings, last_image),
                    "elapsed_seconds": round(time.monotonic() - episode_started, 3),
                }
                if complete_episode:
                    report["episodes"].append(episode)
                else:
                    episode["excluded_from_episode_means"] = True
                    report["partial_episode"] = episode
                    report["status"] = "incomplete"
                save_report()
            finally:
                env.close()
            if report["status"] == "incomplete":
                break
        else:
            report["status"] = "complete"
    except BaseException as error:
        exit_code = 1
        report["status"] = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
        report["error"] = f"{type(error).__name__}: {error}"
        import traceback
        traceback.print_exc()
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        save_report()
    print(json.dumps({key: report[key] for key in ["status", "finished_episodes", "planned_episodes", "mean_max_x", "level_completions", "elapsed_seconds"]}, indent=2))
    return exit_code if report["status"] == "complete" else max(exit_code, 2)


if __name__ == "__main__":
    raise SystemExit(main())
