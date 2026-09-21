#!/usr/bin/env python3
"""Independent floating Mario viewer: sampled live frames and saved clips.

Closing this process never sends a signal or writes instructions to training.
"""
from __future__ import annotations

import argparse
import base64
from io import BytesIO
from datetime import datetime
import json
from pathlib import Path
import time


def read_json(path, limit=8_000_000):
    """Bound reads and tolerate atomic writers by reading one complete file."""
    with Path(path).open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("metadata exceeds viewer size limit")
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("metadata must be an object")
    return value


def repo_path(value, root):
    path = Path(value)
    path = (root / path).resolve() if not path.is_absolute() else path.resolve()
    path.relative_to(root)
    return path


def snapshot(session, repo_root=None):
    """Return manifest, progress, and finished recorded episode clips.

    Paths stored by the Mario session runner are repository-relative. Reading an
    incomplete evaluation is safe: only finished episodes enter its list.
    """
    root = Path(repo_root or Path(__file__).resolve().parent).resolve()
    session = Path(session).resolve()
    manifest = read_json(session / "manifest.json")
    samples = []
    for stage in manifest.get("stages", []):
        if not stage.get("evaluation_path"):
            continue
        evaluation_path = repo_path(stage["evaluation_path"], root)
        try:
            evaluation = read_json(evaluation_path)
        except (OSError, ValueError):
            continue
        for episode in evaluation.get("episodes", []):
            media = episode.get("media", {})
            for part in ("beginning", "ending"):
                item = media.get(part, {})
                if not isinstance(item, dict) or not item.get("path"):
                    continue
                path = (evaluation_path.parent / item["path"]).resolve()
                path.relative_to(root)
                if not path.is_file() or path.suffix.lower() != ".gif":
                    continue
                samples.append({
                    "stage": stage["id"], "seed": episode["seed"], "part": part,
                    "path": path, "minutes": stage.get("elapsed_training_seconds", 0) / 60,
                    "score": episode.get("game_score", episode.get("score", episode.get("final_score"))),
                    "coins": episode.get("coins", episode.get("final_coins")),
                    "x": episode.get("max_x"), "completed": episode.get("completed", False),
                    "outcome": episode.get("end_reason", "unknown"),
                    "full_episode": item.get("is_full_episode", False),
                })
    active_dir = manifest.get("active_training_dir")
    training_dir = repo_path(active_dir, root) if active_dir else None
    progress = {}
    progress_age = None
    if training_dir:
        try:
            progress_path = training_dir / "progress.json"
            progress = read_json(progress_path)
            progress_age = max(0.0, time.time() - progress_path.stat().st_mtime)
        except (OSError, ValueError):
            pass
    # During evaluation the current segment is already included in the saved
    # total, though active_training_dir remains populated. max prevents overlap.
    saved_seconds = float(manifest.get("elapsed_training_seconds", 0))
    previous_seconds = max((float(stage.get("elapsed_training_seconds", 0))
                            for stage in manifest.get("stages", [])
                            if stage.get("id") != manifest.get("active_stage")), default=0.0)
    active_seconds = float(progress.get("elapsed_seconds", 0))
    total_seconds = max(saved_seconds, previous_seconds + active_seconds)
    decisions = max(int(progress.get("timesteps", 0)),
                    max((int(s.get("training_timesteps", 0))
                         for s in manifest.get("stages", [])), default=0))
    live_path = training_dir / "live_frame.json" if training_dir else None
    if live_path is None:
        # Archived/completed sessions may show their final sampled frame, with
        # an explicitly inactive label. This is never presented as live training.
        for stage in reversed(manifest.get("stages", [])):
            summary = stage.get("training_summary_path")
            if summary:
                candidate = repo_path(summary, root).parent / "live_frame.json"
                if candidate.is_file():
                    live_path = candidate
                    break
    return {
        "manifest": manifest, "progress": progress, "samples": samples,
        "live_path": live_path, "progress_age": progress_age,
        "training_seconds": total_seconds, "decisions": decisions,
        "training_active": bool(training_dir and manifest.get("status") == "running"
                                and not manifest.get("active_evaluation")
                                and not manifest.get("pending_stage")),
    }


def decode_live(payload):
    """Validate size before decoding a single untrusted frame."""
    from PIL import Image
    encoded = payload.get("image_base64", "")
    if not isinstance(encoded, str) or len(encoded) > 1_000_000:
        raise ValueError("invalid live image size")
    raw = base64.b64decode(encoded, validate=True)
    with Image.open(BytesIO(raw)) as picture:
        if picture.format != "PNG" or picture.size != (256, 240):
            raise ValueError("invalid live image format or dimensions")
        return picture.convert("RGB").copy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path, nargs="?", help="session directory; omitted opens the most recently created session")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent,
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    if args.session is None:
        candidates = []
        for path in (repo / "results").glob("*/manifest.json"):
            try:
                created = datetime.fromisoformat(read_json(path)["created_at"])
                candidates.append((created.timestamp(), path.parent))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        if not candidates:
            parser.error("No saved session found; start a session or supply its directory")
        session = max(candidates, key=lambda item: item[0])[1]
    else:
        session = args.session.resolve() if args.session.is_absolute() else (repo / args.session).resolve()
    import tkinter as tk
    from tkinter import ttk
    from PIL import Image, ImageTk

    bg, muted, yellow = "#101522", "#b9c4d6", "#ffe260"
    root = tk.Tk()
    root.title("Super Mario Bros. — training viewer")
    root.configure(bg=bg)
    root.geometry("640x900+70+45")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    tk.Label(root, text="Super Mario Bros.", font=("Helvetica", 20, "bold"),
             fg=yellow, bg=bg).pack(pady=(12, 2))
    summary = tk.StringVar(value="Waiting for the training session…")
    tk.Label(root, textvariable=summary, fg="white", bg=bg,
             justify="center", wraplength=615).pack(pady=8)
    mode = tk.StringVar(value="Live training")
    mode_choice = ttk.Combobox(root, state="readonly", textvariable=mode,
                             values=("Live training", "Recorded checkpoints"), width=30)
    mode_choice.pack(pady=3)
    clip_choice = ttk.Combobox(root, state="disabled", width=72)
    clip_choice.pack(pady=3)
    caption = tk.StringVar(value="Waiting for sampled frames from environment 1…")
    tk.Label(root, textvariable=caption, fg=muted, bg=bg,
             wraplength=615, justify="center", height=3).pack(pady=4)
    screen = tk.Canvas(root, bg="black", width=512, height=480,
                       highlightthickness=0)
    screen.pack()
    screen_image = screen.create_image(0, 0, anchor="nw")
    detail = tk.StringVar(value="Score —  ·  Coins —  ·  Position —")
    tk.Label(root, textvariable=detail, fg=yellow, bg=bg,
             font=("Helvetica", 13, "bold")).pack(pady=8)
    state = {"snapshot": None, "samples": [], "selected": None,
             "latest_stage": None, "gif": None, "frame_index": 0,
             "loops": 0, "paused": False, "picture": None,
             "live_stamp": None, "live_data": None, "mode": mode.get()}
    follow = tk.BooleanVar(value=True)
    top = tk.BooleanVar(value=True)

    def show_picture(picture):
        state["picture"] = ImageTk.PhotoImage(
            picture.resize((512, 480), Image.Resampling.NEAREST), master=root)
        screen.itemconfigure(screen_image, image=state["picture"])

    def show_detail(score=None, coins=None, x=None):
        show = lambda value: "—" if value is None else f"{value:,}"
        detail.set(f"Score {show(score)}  ·  Coins {show(coins)}  ·  Position {show(x)}")

    def close_gif():
        if state["gif"] is not None:
            state["gif"].close()
            state["gif"] = None

    def select_clip(sample):
        close_gif()
        try:
            gif = Image.open(sample["path"])
            if gif.format != "GIF" or gif.size[0] > 1024 or gif.size[1] > 1024:
                gif.close()
                raise ValueError("unsupported checkpoint clip")
            # Keep only one decoded frame, rather than hundreds of PhotoImages.
            state.update(gif=gif, frame_index=0, loops=0, paused=False,
                         selected=str(sample["path"]))
            pause.configure(text="Pause")
            full = "full attempt" if sample["full_episode"] else "excerpt"
            caption.set(f"Recorded checkpoint · {sample['minutes']:.1f} training min · {full}\n"
                        f"Seed {sample['seed']} · {sample['outcome'].replace('_', ' ')}")
            show_detail(sample["score"], sample["coins"], sample["x"])
        except (OSError, ValueError) as error:
            caption.set(f"Clip unavailable: {type(error).__name__}")

    def chosen(_=None):
        index = clip_choice.current()
        if 0 <= index < len(state["samples"]):
            select_clip(state["samples"][index])

    def changed_mode(_=None):
        state["mode"] = mode.get()
        state["paused"] = False
        pause.configure(text="Pause")
        if mode.get() == "Recorded checkpoints":
            clip_choice.configure(state="readonly")
            replay.configure(state="normal")
            if state["samples"]:
                if clip_choice.current() < 0:
                    clip_choice.current(len(state["samples"]) - 1)
                chosen()
            else:
                caption.set("Recorded clips will appear after checkpoint evaluation.")
        else:
            close_gif()
            clip_choice.configure(state="disabled")
            replay.configure(state="disabled")
            state["live_stamp"] = None
            caption.set("Waiting for sampled frames from environment 1…")

    def toggle():
        if state["loops"] >= 2:
            state.update(frame_index=0, loops=0)
        state["paused"] = not state["paused"]
        pause.configure(text="Play" if state["paused"] else "Pause")

    def replay_clip():
        state.update(frame_index=0, loops=0, paused=False)
        pause.configure(text="Pause")

    controls = tk.Frame(root, bg=bg)
    controls.pack(pady=4)
    pause = tk.Button(controls, text="Pause", command=toggle)
    pause.pack(side="left", padx=5)
    replay = tk.Button(controls, text="Replay", command=replay_clip, state="disabled")
    replay.pack(side="left", padx=5)
    tk.Checkbutton(controls, text="Follow new clips", variable=follow, bg=bg,
                   fg="white", selectcolor=bg).pack(side="left")
    tk.Checkbutton(root, text="Keep above other windows", variable=top,
                   command=lambda: root.attributes("-topmost", top.get()),
                   bg=bg, fg="white", selectcolor=bg).pack()
    tk.Label(root, text="Pause affects the viewer only. Recorded clips play twice.\n"
             "Closing this window or pressing Esc leaves training running.",
             fg=muted, bg=bg, font=("Helvetica", 10)).pack(pady=6)
    mode_choice.bind("<<ComboboxSelected>>", changed_mode)
    clip_choice.bind("<<ComboboxSelected>>", chosen)

    def poll_metadata():
        try:
            data = snapshot(session, repo)
            state["snapshot"] = data
            manifest, progress = data["manifest"], data["progress"]
            phase = manifest.get("active_evaluation") or manifest.get("active_stage") or ""
            recent = []
            for key, label in (("recent_mean_game_score", "mean score"),
                               ("recent_mean_score_gain", "score gain")):
                if progress.get(key) is not None:
                    recent.append(f"{label} {progress[key]:,.0f}")
            if progress.get("recent_completion_rate") is not None:
                recent.append(f"clears {progress['recent_completion_rate']:.0%}")
            reward_details = []
            if progress.get("recent_mean_completed_score") is not None:
                reward_details.append(f"Mean points (failures = 0) {progress['recent_mean_completed_score']:,.0f}")
            if progress.get("recent_mean_objective_reward") is not None:
                reward_details.append(f"learning reward {progress['recent_mean_objective_reward']:.2f}")
            summary.set(f"Session: {manifest.get('status', 'unknown')} · {phase}\n"
                        f"{data['training_seconds'] / 60:.1f} active training min · "
                        f"{data['decisions']:,} cumulative decisions" +
                        ("\nRecent episodes: " + " · ".join(recent) if recent else "") +
                        ("\n" + " · ".join(reward_details) if reward_details else ""))
            old_selected = state["selected"]
            samples = data["samples"]
            state["samples"] = samples
            clip_choice["values"] = [f"{s['stage']} · seed {s['seed']} · {s['part']}" for s in samples]
            if samples:
                latest = samples[-1]["stage"]
                newest = next((s for s in samples if s["stage"] == latest and s["part"] == "beginning"), samples[-1])
                wanted = next((s for s in samples if str(s["path"]) == old_selected), newest)
                if follow.get() and latest != state["latest_stage"]:
                    wanted = newest
                clip_choice.current(samples.index(wanted))
                if mode.get() == "Recorded checkpoints" and str(wanted["path"]) != old_selected:
                    select_clip(wanted)
                state["latest_stage"] = latest
        except (OSError, ValueError, KeyError, TypeError) as error:
            summary.set(f"Waiting for session metadata ({type(error).__name__})…")
        root.after(2000, poll_metadata)

    def tick():
        delay = 200
        try:
            if mode.get() == "Live training":
                data = state["snapshot"]
                path = data.get("live_path") if data else None
                if path and not state["paused"]:
                    stat = path.stat()
                    stamp = (str(path), stat.st_mtime_ns, stat.st_size)
                    if stamp != state["live_stamp"]:
                        payload = read_json(path, limit=1_100_000)
                        show_picture(decode_live(payload))
                        state.update(live_stamp=stamp, live_data=payload)
                        show_detail(payload.get("score"), payload.get("coins"), payload.get("x"))
                payload = state["live_data"]
                if payload:
                    age = max(0, time.time() - payload["timestamp"])
                    active = bool(data and data["training_active"] and age < 5)
                    workers = data["manifest"].get("configuration", {}).get("n_envs", 4) if data else 4
                    label = f"Live training — environment 1 of {workers}; sampled frames" if active else "Last sampled training frame — currently inactive or waiting"
                    caption.set(f"{label}\nEpisode {payload['episode']} · game time {payload.get('time', '—')} · frame age {age:.1f}s"
                                + (" · viewer paused" if state["paused"] else ""))
            elif state["gif"] is not None:
                gif = state["gif"]
                gif.seek(state["frame_index"])
                show_picture(gif.convert("RGB"))
                delay = max(20, int(gif.info.get("duration", 67)))
                if not state["paused"]:
                    state["frame_index"] += 1
                    try:
                        gif.seek(state["frame_index"])
                    except EOFError:
                        state["loops"] += 1
                        if state["loops"] >= 2:
                            state["frame_index"] -= 1
                            state["paused"] = True
                            pause.configure(text="Play again")
                        else:
                            state["frame_index"] = 0
        except (OSError, ValueError, KeyError, TypeError, EOFError) as error:
            caption.set(f"Waiting for view data ({type(error).__name__})…")
            delay = 500
        root.after(delay, tick)

    def close():
        close_gif()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    root.bind("<Escape>", lambda _: close())
    root.lift()
    poll_metadata()
    tick()
    root.mainloop()


if __name__ == "__main__":
    main()
