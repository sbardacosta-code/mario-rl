#!/usr/bin/env python3
"""Compare the prespecified Mario reward-scaling pilot with its original run."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def evaluation_complete(evaluation: dict, seeds: list[int]) -> bool:
    episodes = evaluation.get("episodes", [])
    return (
        evaluation.get("status") == "complete"
        and evaluation.get("partial_episode") is None
        and evaluation.get("planned_episodes") == len(seeds)
        and evaluation.get("finished_episodes") == len(seeds)
        and len(episodes) == len(seeds)
        and [episode.get("seed") for episode in episodes] == seeds
        and all(
            math.isfinite(float(episode[metric]))
            for episode in episodes for metric in ("max_x", "native_reward")
        )
    )


def stats(evaluation: dict) -> dict:
    episodes = evaluation.get("episodes", [])
    count = len(episodes)
    return {
        "status": evaluation.get("status"),
        "finished_trials": count,
        "mean_max_x": sum(e["max_x"] for e in episodes) / count if count else None,
        "mean_native_reward": sum(e["native_reward"] for e in episodes) / count if count else None,
        "level_completions": sum(bool(e["completed"]) for e in episodes),
        "trials": [
            {key: e[key] for key in ("seed", "max_x", "native_reward", "completed", "decisions")}
            for e in episodes
        ],
    }


def optimized_decisions(epochs: int, config: dict) -> int | None:
    hyperparameters = config["hyperparameters"]
    n_epochs = int(hyperparameters["n_epochs"])
    if epochs < 0 or epochs % n_epochs:
        return None
    return (epochs // n_epochs) * int(hyperparameters["n_steps"]) * int(config["args"]["n_envs"])


def training_rows(path: Path, limit: int) -> list[dict]:
    rows = []
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            parsed = {key: float(row[key]) for key in ("timesteps", "return", "max_x")}
            if not all(math.isfinite(value) for value in parsed.values()):
                raise ValueError(f"Nonfinite training data in {path}")
            if parsed["timesteps"] <= limit:
                rows.append(parsed)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    original = repo / "results/first_training"
    pilot = repo / "results/reward_scaled"
    baseline = read_json(original / "baseline/evaluation.json")
    reference = read_json(original / "intermediate/step_000102796/evaluation.json")
    scaled = read_json(pilot / "final/evaluation.json")
    full_original = read_json(original / "final/evaluation.json")
    preflight = read_json(pilot / "preflight.json")
    old_config = read_json(original / "config.json")
    new_config = read_json(pilot / "config.json")
    old_summary = read_json(original / "training_summary.json")
    new_summary = read_json(pilot / "training_summary.json")
    plan = read_json(pilot / "experiment_plan.json")

    seeds = plan["evaluation_seeds"]
    reference_steps = optimized_decisions(int(preflight["reference_epochs"]), old_config)
    new_steps = optimized_decisions(int(new_summary["ppo_epochs_this_run"]), new_config)
    original_full_steps = optimized_decisions(int(old_summary["ppo_epochs_this_run"]), old_config)
    hp = new_config["hyperparameters"]
    reference_expected_adam_steps = (
        int(preflight["reference_epochs"])
        * math.ceil(int(hp["n_steps"]) * int(new_config["args"]["n_envs"]) / int(hp["batch_size"]))
    )
    new_expected_adam_steps = (
        int(new_summary["ppo_epochs_this_run"])
        * math.ceil(int(hp["n_steps"]) * int(new_config["args"]["n_envs"]) / int(hp["batch_size"]))
    )
    protocol_matches = bool(baseline.get("protocol")) and baseline["protocol"] == reference.get("protocol") == scaled.get("protocol")
    checks = {
        "same_evaluation_protocol": protocol_matches,
        "three_distinct_prespecified_seeds": len(seeds) == 3 and len(set(seeds)) == 3,
        "all_three_evaluations_complete": all(evaluation_complete(e, seeds) for e in (baseline, reference, scaled)),
        "native_evaluation_reward": scaled.get("protocol", {}).get("reward") == "native reward summed over repeated frames",
        "same_initial_policy": (
            preflight["initial_policy_sha256"]
            == new_summary["policy_sha256_before"]
            == old_summary["policy_sha256_before"]
        ),
        "initial_optimizer_empty": preflight["initial_optimizer_steps"] == 0,
        "same_ppo_hyperparameters": old_config["hyperparameters"] == new_config["hyperparameters"],
        "same_dependency_versions": old_config["packages"] == new_config["packages"],
        "same_execution_configuration": all(
            old_config["args"][key] == new_config["args"][key]
            for key in ("device", "threads", "n_envs", "seed", "max_decisions", "resume")
        ),
        "same_environment_preprocessing": all(
            old_config[key] == new_config[key]
            for key in ("environment", "algorithm", "policy", "action_set", "action_repeat", "observation_shape")
        ),
        "reward_scaling_preflight_passed": all(preflight.get(key) is True for key in (
            "observations_identical", "termination_identical", "native_metrics_identical", "scaled_rewards_verified"
        )) and preflight.get("reward_scale") == 0.01 and new_config["args"].get("reward_scale") == 0.01,
        "training_completed_with_finite_changed_weights": (
            new_summary["status"] == "completed"
            and new_summary["all_parameters_finite"] is True
            and new_summary["changed_parameter_tensors"] > 0
        ),
        "reference_optimizer_count_consistent": preflight["reference_optimizer_steps"] == reference_expected_adam_steps,
        "pilot_optimizer_count_consistent": new_summary["optimizer_steps_this_run"] == new_expected_adam_steps,
        "same_optimized_decision_budget": reference_steps == new_steps == plan["max_timesteps"] == 102400,
        "same_optimizer_step_budget": preflight["reference_optimizer_steps"] == new_summary["optimizer_steps_this_run"] == 1600,
        "same_epoch_budget": preflight["reference_epochs"] == new_summary["ppo_epochs_this_run"] == 400,
        "optimized_decisions_do_not_exceed_collection": (
            reference_steps is not None and new_steps is not None
            and reference_steps <= preflight["reference_timesteps"]
            and new_steps <= new_summary["timesteps"]
        ),
    }
    budget_checks = ("reference_optimizer_count_consistent", "pilot_optimizer_count_consistent", "same_optimized_decision_budget", "same_optimizer_step_budget", "same_epoch_budget")
    budget_matches = all(checks[name] for name in budget_checks)
    controlled_comparison = all(checks.values())
    groups = {"untrained": stats(baseline), "native_rewards": stats(reference), "scaled_rewards_0_01": stats(scaled)}
    groups["untrained"]["optimized_decisions"] = 0
    groups["native_rewards"].update({"optimized_decisions": reference_steps, "checkpoint_collected_decisions": preflight["reference_timesteps"], "optimizer_steps": preflight["reference_optimizer_steps"]})
    groups["scaled_rewards_0_01"].update({"optimized_decisions": new_steps, "checkpoint_collected_decisions": new_summary["timesteps"], "optimizer_steps": new_summary["optimizer_steps_this_run"]})
    notes = [
        "One training seed and three sampled-action evaluation trials are exploratory, not conclusive evidence.",
        "All evaluation rewards and training episode returns shown here use the game's native units.",
        "Different evaluation seeds vary sampled actions; they do not create different levels.",
        "The native-reward reference archive contains 396 additional collected decisions that had not been optimized.",
        "Training curves include only finished episodes at or before 102,400 collected decisions and use a trailing mean of up to 20 episodes.",
        "Final checkpoints are chosen by the prespecified budgets, not by their evaluation scores.",
    ]
    if not controlled_comparison:
        notes.append("Some verification checks failed; use descriptive results only and inspect failed_checks before drawing a controlled-comparison conclusion.")
    if not budget_matches:
        notes.append("Training update budgets differ or could not be confirmed.")
    native_rows = training_rows(original / "episodes.csv", 102400)
    scaled_rows = training_rows(pilot / "episodes.csv", 102400)
    pilot_mean = groups["scaled_rewards_0_01"]["mean_max_x"]
    reference_mean = groups["native_rewards"]["mean_max_x"]
    baseline_mean = groups["untrained"]["mean_max_x"]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "identical_training_update_budget_confirmed": budget_matches,
        "controlled_comparison_verified": controlled_comparison,
        "evaluation_seeds": seeds,
        "groups": groups,
        "scaled_minus_native_mean_max_x": pilot_mean - reference_mean if pilot_mean is not None and reference_mean is not None else None,
        "scaled_minus_untrained_mean_max_x": pilot_mean - baseline_mean if pilot_mean is not None and baseline_mean is not None else None,
        "context_only_original_25_minute_final": {
            **stats(full_original),
            "optimized_decisions": original_full_steps,
            "checkpoint_collected_decisions": old_summary["timesteps"],
            "equal_budget_comparator": False,
        },
        "training_curve": {"decision_limit": 102400, "trailing_episode_window": 20, "native_finished_episodes": len(native_rows), "scaled_finished_episodes": len(scaled_rows)},
        "notes": notes,
    }
    write_json(pilot / "ab_comparison.json", report)

    cache = pilot / ".matplotlib"
    cache.mkdir(exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(cache)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 12})
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.6))
    fig.patch.set_facecolor("#fafbfc")
    fig.suptitle("Reward scaling · Mario World 1-1", x=0.065, y=0.975, ha="left", fontsize=21, fontweight="bold")
    subtitle = "Both trained policies: 102,400 optimized decisions · 1,600 optimizer steps" if budget_matches else f"Training budgets differ or are unverified · native: {reference_steps} · scaled: {new_steps} optimized decisions"
    fig.text(0.065, 0.926, subtitle, fontsize=11, color="#334155")
    fig.text(0.065, 0.899, "Evaluation: 3 fixed seeds · stochastic actions · untrained model shown for context", fontsize=10, color="#64748b")
    palette = ["#94a3b8", "#d97706", "#2563eb"]
    labels = ["Untrained", "Native rewards", "Rewards × 0.01"]
    evals = [baseline, reference, scaled]
    seed_maps = [{e["seed"]: e for e in ev.get("episodes", [])} for ev in evals]
    common_seeds = [seed for seed in seeds if all(seed in group for group in seed_maps)]
    for axis, metric, title, ylabel in (
        (axes[0, 0], "max_x", "Distance reached in each evaluation trial", "Furthest horizontal position (pixels)"),
        (axes[0, 1], "native_reward", "Native reward in each evaluation trial", "Native episode reward"),
    ):
        positions = np.arange(len(common_seeds))
        for index, (mapping, label, color) in enumerate(zip(seed_maps, labels, palette)):
            axis.bar(positions + (index - 1) * 0.25, [mapping[seed][metric] for seed in common_seeds], width=0.23, label=label, color=color)
        axis.set_xticks(positions, [str(seed) for seed in common_seeds])
        axis.set_xlabel("Evaluation seed")
        axis.set_ylabel(ylabel)
        axis.set_title(title, loc="left", pad=12)
        axis.legend(frameon=False, fontsize=8, loc="upper left")
        axis.margins(y=0.24)
        if not common_seeds:
            axis.text(0.5, 0.5, "No common finished trials", transform=axis.transAxes, ha="center")
    for axis, metric, title, ylabel in (
        (axes[1, 0], "max_x", "Distance during training", "Furthest horizontal position (pixels)"),
        (axes[1, 1], "return", "Native return during training", "Native episode reward"),
    ):
        for rows, label, color in zip([native_rows, scaled_rows], labels[1:], palette[1:]):
            if not rows:
                continue
            x = np.array([row["timesteps"] / 1000 for row in rows])
            y = np.array([row[metric] for row in rows])
            axis.scatter(x, y, color=color, s=6, alpha=0.12, rasterized=True)
            window = min(20, len(rows))
            rolling = np.convolve(y, np.ones(window) / window, mode="valid")
            axis.plot(x[window - 1:], rolling, color=color, linewidth=1.8, label=label)
        axis.set_title(title + " · trailing 20-episode mean", loc="left", pad=12, fontsize=11)
        axis.set_xlim(0, 102.4)
        axis.set_xlabel("Collected agent decisions (thousands)")
        axis.set_ylabel(ylabel)
        axis.legend(frameon=False, fontsize=8)
    for axis in axes.flat:
        axis.grid(axis="y", alpha=0.14)
        axis.set_axisbelow(True)
    completions = " · ".join(f"{label}: {group['level_completions']}/{group['finished_trials']} clears" for label, group in zip(labels, groups.values()))
    fig.text(0.065, 0.058, completions, fontsize=10, color="#334155")
    fig.text(0.065, 0.032, "One training seed and three evaluation trials: a pilot, not reliable evidence of general performance.", fontsize=9, color="#64748b")
    if not controlled_comparison:
        fig.text(0.065, 0.008, "Verification incomplete: results are descriptive; inspect ab_comparison.json.", fontsize=9, color="#b45309")
    fig.tight_layout(rect=(0.02, 0.086, 0.99, 0.877), h_pad=2.4, w_pad=2.5)
    fig.savefig(pilot / "reward_scale_comparison.png", dpi=170, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(json.dumps({"report": str(pilot / "ab_comparison.json"), "chart": str(pilot / "reward_scale_comparison.png"), "controlled_comparison_verified": controlled_comparison, "failed_checks": report["failed_checks"], "groups": groups}, indent=2, allow_nan=False))
    return 0 if controlled_comparison else 1


if __name__ == "__main__":
    raise SystemExit(main())
