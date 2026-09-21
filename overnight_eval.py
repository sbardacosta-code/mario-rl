#!/usr/bin/env python3
"""Evaluate a frozen Mario policy with flag settlement and explicit 1UP metrics.

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
    "game_score", "score_gain", "coins", "one_ups", "custom_one_up_bonus",
    "augmented_score_gain", "flag_height_bonus", "flag_touch_y",
    "flag_score_tier", "flag_top_tier", "post_flag_frames",
    "flag_resolution_complete", "flag_resolution_status",
    "objective_reward", "objective_reward_sum",
]


def event_record(info: dict) -> dict:
    """Keep actual HUD points separate from user-requested teaching bonuses."""
    score = info["score_metrics"]
    event = info["event_metrics"]
    return {
        "game_score": int(score["current_score"]),
        "initial_score": int(score["initial_score"]),
        "score_gain": int(score["score_gain"]),
        "max_score": int(score["max_score"]),
        "coins": int(info["coins"]),
        "one_ups": int(event["one_ups"]),
        "custom_one_up_bonus": float(score["custom_one_up_bonus"]),
        "augmented_score_gain": float(score["augmented_score_gain"]),
        "flag_height_bonus": int(event["flag_height_bonus"]),
        "flag_touch_y": event["flag_touch_y"],
        "flag_score_tier": event["flag_score_tier"],
        "flag_top_tier": event["flag_top_tier"],
        "post_flag_frames": int(event["post_flag_frames"]),
        "flag_resolution_complete": bool(event["flag_resolution_complete"]),
        "flag_resolution_status": event["flag_resolution_status"],
        "objective_reward": float(score["objective_reward"]),
        "objective_reward_sum": float(score["objective_reward_sum"]),
        "native_reward_sum": float(score["native_reward_sum"]),
    }


def summarize_episodes(episodes: list[dict]) -> dict:
    """The completed metrics average all attempts, assigning failures zero."""
    count = len(episodes)
    average = lambda key: sum(e[key] for e in episodes) / count if count else None
    clears = [e for e in episodes if e["completed"]]
    touched = [e for e in episodes if e["flag_touch_y"] is not None]
    return {
        "mean_game_score": average("game_score"),
        "mean_score_gain": average("score_gain"),
        "mean_completed_score": sum(e["score_gain"] if e["completed"] else 0
                                    for e in episodes) / count if count else None,
        "mean_score_on_clears": sum(e["score_gain"] for e in clears) / len(clears) if clears else None,
        "mean_augmented_score_gain": average("augmented_score_gain"),
        "mean_completed_augmented_score": sum(e["augmented_score_gain"] if e["completed"] else 0
                                              for e in episodes) / count if count else None,
        "mean_one_ups": average("one_ups"),
        "mean_custom_one_up_bonus": average("custom_one_up_bonus"),
        "mean_flag_height_bonus": average("flag_height_bonus"),
        "mean_flag_touch_y_on_contacts": sum(e["flag_touch_y"] for e in touched) / len(touched) if touched else None,
        "flag_contacts": len(touched),
        "top_flag_contacts": sum(bool(e["flag_top_tier"]) for e in touched),
        "flag_resolutions_complete": sum(e["flag_resolution_complete"] for e in episodes),
        "mean_objective_reward": average("objective_reward_sum"),
    }


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


def policy_sha256(model) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(model.policy.state_dict().items()):
        digest.update(name.encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
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
        "schema_version": 4,
        "status": "running",
        "model": str(args.model.resolve()),
        "model_sha256": sha256(args.model),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "learning_updates": 0,
        "protocol": {
            "version": 3,
            "environment": "SuperMarioBros-1-1-v0",
            "seeds": args.seeds,
            "max_decisions": args.max_decisions,
            "deterministic": args.deterministic,
            "seed_method": "SB3 set_random_seed plus environment reset(seed)",
            "action_space": "RIGHT_ONLY",
            "action_repeat": 4,
            "observation_shape": [4, 84, 84],
            "reward": "score_events with score_weight=1.0; native emulator reward recorded separately",
            "objective": "score_events",
            "score_weight": 1.0,
            "score_metric": "actual HUD points including the resolved flag-height award; later remaining-time conversion excluded",
            "custom_metric": "augmented score gain = actual HUD score gain + explicit custom 1UP teaching bonus; custom bonus is not in-game score",
            "flag_height_metric": "raw RAM y at first pole contact; smaller y means higher contact; actual flag award recorded separately",
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
            "full_episode": args.beginning_decisions >= args.max_decisions,
            "flag_animation": "video trials include sampled automatic pole-slide frames; durations account for the extra emulator frames",
            "ending_limit": "ending_decisions is the maximum retained sampled images, including any pole-slide snapshots",
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
            "Beginning clips cover each completed video trial; ending clips are excerpts."
            if args.beginning_decisions >= args.max_decisions else "GIFs show excerpts; the CSV contains every decision in the trial.",
            "A stalled maximum does not establish that Mario cannot move or identify a collision.",
            "A non-clearing termination does not identify a death cause; inspect the clip.",
            "This event-aware boundary differs from older flag-touch-only evaluations; compare policies evaluated with this exact protocol.",
            "1UP source counts distinguish coin rollovers from other or unknown sources; they do not prove a hidden-block pickup.",
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
        report.update(summarize_episodes(episodes))
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        write_json(report_path, report)

    save_report()
    exit_code = 0
    model = None
    try:
        import numpy as np
        from PIL import Image
        import torch
        from stable_baselines3 import PPO
        from stable_baselines3.common.utils import set_random_seed
        from gym_super_mario_bros.actions import RIGHT_ONLY
        from overnight_env import make_env, EVENT_REWARD_CONFIG

        report["protocol"]["event_reward_config"] = dict(EVENT_REWARD_CONFIG)
        save_report()

        torch.set_num_threads(1)
        model = PPO.load(args.model, device=args.device)
        model.policy.set_training_mode(False)
        report["policy_sha256_before"] = policy_sha256(model)
        report["model_timesteps_before"] = int(model.num_timesteps)
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
            env = make_env(seed=seed, render_mode="rgb_array", max_decisions=args.max_decisions,
                           objective="score_events", score_weight=1.0,
                           record_resolution=seed in args.video_seeds)
            seed_dir = args.output_dir / f"seed-{seed}"
            seed_dir.mkdir()
            trace_path = seed_dir / "trace.csv"
            event_path = seed_dir / "events.jsonl"
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
                with trace_path.open("x", newline="") as trace, event_path.open("x") as event_trace:
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
                        recorded = event_record(info)
                        native_step_reward = recorded["native_reward_sum"] - native_reward
                        native_reward = recorded["native_reward_sum"]
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
                            "native_reward": native_step_reward, "native_reward_sum": native_reward,
                            "no_progress_decisions": stalled,
                            "life": info.get("life"), "game_time": info.get("time"),
                            "flag_get": int(bool(info.get("flag_get", False))),
                            "terminated": int(terminated), "truncated": int(truncated),
                        }
                        row.update({key: value for key, value in recorded.items()
                                    if key in TRACE_FIELDS})
                        row.update({f"prob_{i}": float(probabilities[i]) for i in range(5)})
                        writer.writerow(row)
                        event_trace.write(json.dumps({"decision": decision,
                            "event_metrics": info["event_metrics"],
                            "score_metrics": info["score_metrics"]}, allow_nan=False) + "\n")
                        if seed in args.video_seeds:
                            frame = np.asarray(env.render())
                            if frame.ndim != 3 or frame.shape[-1] != 3:
                                raise ValueError(f"Expected native RGB rendering; got {frame.shape}")
                            last_image = Image.fromarray(frame.copy())
                            resolution = info.get("resolution_frames", [])
                            # First show pole contact, then the automatic animation;
                            # env.render() already contains the final settled frame.
                            if resolution:
                                images = [Image.fromarray(np.asarray(info["flag_contact_frame"]).copy())]
                                images.extend(Image.fromarray(np.asarray(item).copy()) for item in resolution)
                                durations = [int(info["action_repeat_controlled_frames"])]
                                durations.extend(int(value) for value in info["resolution_frame_counts"])
                                if (len(images) != len(durations) or sum(durations) != frame_count
                                        or sum(durations[1:]) != recorded["post_flag_frames"]
                                        or min(durations) < 1):
                                    raise ValueError("resolution-frame accounting mismatch")
                            else:
                                images = [last_image]
                                durations = [frame_count]
                            for image, duration in zip(images, durations):
                                packed = image.convert("P", palette=Image.Palette.ADAPTIVE, colors=128)
                                record = (decision, packed, duration)
                                if decision <= args.beginning_decisions:
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
                    **event_record(info),
                    "event_metrics": dict(info["event_metrics"]),
                    "score_anomalies": info["score_metrics"].get("score_anomalies", []),
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
                    "event_trace_jsonl": event_path.relative_to(args.output_dir).as_posix(),
                    "event_trace_rows": decisions,
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
        try:
            report["model_sha256_after"] = sha256(args.model)
        except OSError as error:
            report["model_sha256_after"] = None
            report["checkpoint_read_error"] = f"{type(error).__name__}: {error}"
        report["model_file_unchanged"] = report["model_sha256_after"] == report["model_sha256"]
        if model is not None and "policy_sha256_before" in report:
            report["policy_sha256_after"] = policy_sha256(model)
            report["policy_unchanged"] = report["policy_sha256_after"] == report["policy_sha256_before"]
            report["model_timesteps_after"] = int(model.num_timesteps)
        if not report["model_file_unchanged"] or not report.get("policy_unchanged", model is None):
            report["status"] = "failed"
            report["error"] = "checkpoint file or policy weights changed during frozen evaluation"
            exit_code = 1
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        save_report()
    print(json.dumps({key: report[key] for key in ["status", "finished_episodes", "planned_episodes", "mean_max_x", "level_completions", "elapsed_seconds"]}, indent=2))
    return exit_code if report["status"] == "complete" else max(exit_code, 2)


if __name__ == "__main__":
    raise SystemExit(main())
