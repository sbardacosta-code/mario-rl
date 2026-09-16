#!/usr/bin/env python3
"""Summarize matched Mario evaluations and logged training episodes."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path


def read_evaluation(path: Path) -> dict:
    if not path.exists():
        return {"status": "missing", "episodes": [], "protocol": {}}
    return json.loads(path.read_text())


def read_training(path: Path) -> tuple[list[dict], int]:
    records, skipped = [], 0
    if not path.exists():
        return records, skipped
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                record = {key: float(row[key]) for key in ("elapsed_seconds", "timesteps", "return", "length", "max_x")}
                if not all(math.isfinite(value) for value in record.values()):
                    raise ValueError("nonfinite training value")
                record["completed"] = str(row["completed"]).lower() in ("1", "1.0", "true", "yes")
                records.append(record)
            except (ValueError, KeyError, TypeError):
                skipped += 1
    return records, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args()
    args.run_dir.mkdir(parents=True, exist_ok=True)
    baseline = read_evaluation(args.run_dir / "baseline/evaluation.json")
    final = read_evaluation(args.run_dir / "final/evaluation.json")
    training, skipped = read_training(args.run_dir / "episodes.csv")
    before = {int(episode["seed"]): episode for episode in baseline.get("episodes", [])}
    after = {int(episode["seed"]): episode for episode in final.get("episodes", [])}
    seeds = sorted(before.keys() & after.keys())
    matched = [{"seed": seed, "baseline": before[seed], "final": after[seed], "max_x_change": after[seed]["max_x"] - before[seed]["max_x"]} for seed in seeds]
    protocol_matches = bool(baseline.get("protocol")) and baseline.get("protocol") == final.get("protocol")
    planned_seeds = baseline.get("protocol", {}).get("seeds", [])
    all_three = protocol_matches and len(seeds) == 3 and set(seeds) == set(planned_seeds) and baseline.get("status") == "complete" and final.get("status") == "complete"

    def matched_stats(records: dict) -> dict:
        selected = [records[seed] for seed in seeds]
        count = len(selected)
        return {
            "episodes": count,
            "mean_max_x": sum(e["max_x"] for e in selected) / count if count else None,
            "mean_native_reward": sum(e["native_reward"] for e in selected) / count if count else None,
            "level_completions": sum(bool(e["completed"]) for e in selected),
            "completion_rate": sum(bool(e["completed"]) for e in selected) / count if count else None,
        }

    baseline_stats, final_stats = matched_stats(before), matched_stats(after)
    notes = ["Three seeded trials are a small sample and cannot establish reliable performance.", "Partial episodes stopped by the evaluation wall-time limit are excluded.", "Training curves contain finished episodes only."]
    if not all_three:
        notes.append("The complete matched three-trial comparison is unavailable; inspect evaluation status and protocol differences.")
    if not protocol_matches:
        notes.append("Evaluation protocols differ or are missing; reported numbers are descriptive and not a controlled comparison.")
    observed_final_completions = sum(bool(e.get("completed")) for e in final.get("episodes", []))
    if final.get("episodes") and observed_final_completions == 0:
        notes.append("No level completion was observed in the finished final evaluation trials.")
    if not final.get("episodes"):
        notes.append("No finished final evaluation trials are available.")
    comparison = {
        "baseline_status": baseline.get("status"),
        "final_status": final.get("status"),
        "protocol_matches": protocol_matches,
        "complete_matched_three_trial_comparison": all_three,
        "matched_seeds": seeds,
        "baseline": baseline_stats,
        "final": final_stats,
        "mean_max_x_change": final_stats["mean_max_x"] - baseline_stats["mean_max_x"] if seeds else None,
        "matched_trials": matched,
        "training": {
            "finished_episodes": len(training),
            "skipped_csv_rows": skipped,
            "last_logged_timesteps": int(training[-1]["timesteps"]) if training else 0,
            "last_logged_elapsed_seconds": training[-1]["elapsed_seconds"] if training else 0,
            "best_max_x": max(row["max_x"] for row in training) if training else None,
            "level_completions": sum(row["completed"] for row in training),
        },
        "notes": notes,
    }
    report_path = args.run_dir / "comparison.json"
    report_path.write_text(json.dumps(comparison, indent=2, allow_nan=False) + "\n")

    config_dir = args.run_dir / ".matplotlib"
    config_dir.mkdir(exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(config_dir.resolve())
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 11})
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.patch.set_facecolor("#fafbfc")
    fig.suptitle("Mario World 1-1 · training progress", fontsize=18, x=0.07, ha="left", y=0.97)
    subtitle = f"Matched evaluation seeds: {', '.join(map(str, seeds)) or 'none'} · stochastic actions · final level completions: {observed_final_completions}/{len(final.get('episodes', []))}"
    fig.text(0.07, 0.92, subtitle, fontsize=10, color="#4b5563")
    colors = ("#94a3b8", "#2563eb")
    for axis, metric, title, ylabel in ((axes[0, 0], "max_x", "Distance reached by seed", "Furthest horizontal position (pixels)"), (axes[0, 1], "native_reward", "Native episode reward by seed", "Native reward sum")):
        if seeds:
            positions = np.arange(len(seeds))
            axis.bar(positions - 0.18, [before[s][metric] for s in seeds], width=0.36, color=colors[0], label="Before training")
            axis.bar(positions + 0.18, [after[s][metric] for s in seeds], width=0.36, color=colors[1], label="After training")
            axis.set_xticks(positions, [str(seed) for seed in seeds])
            axis.set_xlabel("Evaluation seed")
            axis.legend(frameon=False, fontsize=8)
        else:
            axis.text(0.5, 0.5, "No matched finished trials", transform=axis.transAxes, ha="center")
        axis.set_title(title, loc="left")
        axis.set_ylabel(ylabel)

    for axis, metric, title, ylabel in ((axes[1, 0], "max_x", "Distance during training", "Furthest horizontal position (pixels)"), (axes[1, 1], "return", "Return during training", "Training episode return")):
        if training:
            minutes = [row["elapsed_seconds"] / 60 for row in training]
            values = [row[metric] for row in training]
            axis.scatter(minutes, values, s=8, alpha=0.22, color="#2563eb", label="Finished episode")
            window = min(20, len(values))
            rolling = np.convolve(values, np.ones(window) / window, mode="valid")
            axis.plot(minutes[window - 1:], rolling, color="#173b75", linewidth=1.8, label=f"Mean of {window} episodes")
            axis.legend(frameon=False, fontsize=8)
        else:
            axis.text(0.5, 0.5, "No finished training episodes logged", transform=axis.transAxes, ha="center")
        axis.set_title(title, loc="left")
        axis.set_ylabel(ylabel)
        axis.set_xlabel("Elapsed training minutes")
    for axis in axes.flat:
        axis.grid(axis="y", alpha=0.15)
        axis.set_axisbelow(True)
    footer = "Small sample: these trials do not establish reliable performance."
    if not all_three:
        footer += " Complete matched three-trial comparison unavailable."
    if final.get("episodes") and observed_final_completions == 0:
        footer += " No final level clear observed."
    fig.text(0.07, 0.025, footer, fontsize=8, color="#4b5563")
    fig.tight_layout(rect=(0.025, 0.055, 0.99, 0.89), h_pad=2.2, w_pad=2.5)
    fig.savefig(args.run_dir / "progress.png", dpi=170, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(json.dumps(comparison, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
