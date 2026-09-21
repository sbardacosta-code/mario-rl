#!/usr/bin/env python3
"""Build the English classroom index and an archived report from a session manifest.

Paths in the manifest are relative to the repository. Media and trace paths in
evaluation.json are relative to that evaluation file. No training is performed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import statistics
from urllib.parse import quote


COMPARISON_KEYS = (
    "environment", "seeds", "max_decisions", "deterministic", "seed_method",
    "action_space", "action_repeat", "observation_shape", "reward",
    "stall_threshold_decisions", "stall_definition",
)
STATUS = {"preparing": "preparing initial evaluation", "prepared": "ready for training", "running": "in progress", "completed": "completed", "interrupted": "interrupted", "failed": "interrupted by an error"}
END_REASONS = {
    "level_completed": "flag reached",
    "episode_ended_without_flag": "ended without reaching the flag; cause unknown",
    "decision_limit": "decision limit",
}


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def within(root: Path, relative: str | Path) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes repository: {relative}")
    return path


def number(value: object, digits: int = 0) -> str:
    if value is None:
        return "—"
    result = f"{float(value):,.{digits}f}"
    return result


def cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def link(label: str, target: Path, document: Path, image: bool = False) -> str:
    relative = quote(os.path.relpath(target, document.parent), safe="/._-")
    return f"{'!' if image else ''}[{cell(label)}]({relative})"


def existing_link(label: str, target: Path, document: Path) -> str:
    return link(label, target, document) if target.is_file() else "—"


def finite(value: object, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Non-finite {label}: {value}")
    return result


def load_stages(repo: Path, manifest: dict) -> list[dict]:
    stages = []
    expected_seeds = manifest.get("configuration", {}).get("eval_seeds")
    reference_protocol = None
    seen_ids = set()
    last_seconds = -1.0
    for source in manifest.get("stages", []):
        stage = dict(source)
        if not stage.get("id") or stage["id"] in seen_ids:
            raise ValueError("Stage IDs must be present and unique")
        seen_ids.add(stage["id"])
        stage["seconds"] = finite(stage.get("elapsed_training_seconds", 0), "stage elapsed seconds")
        if stage["seconds"] < last_seconds or stage["seconds"] < 0:
            raise ValueError("Stages must be ordered by nonnegative elapsed training time")
        last_seconds = stage["seconds"]
        stage["minutes"] = stage["seconds"] / 60
        stage["evaluation_file"] = within(repo, stage["evaluation_path"])
        stage["evaluation"] = None
        stage["episodes"] = []
        stage["comparable"] = False
        stage["warning"] = "Evaluation pending; this is not treated as a zero result."
        if stage["evaluation_file"].is_file():
            evaluation = read_json(stage["evaluation_file"])
            stage["evaluation"] = evaluation
            episodes = evaluation.get("episodes", [])
            protocol = evaluation.get("protocol", {})
            stage["episodes"] = episodes
            seeds = [episode["seed"] for episode in episodes]
            planned = protocol.get("seeds", [])
            for episode in episodes:
                finite(episode["max_x"], "max_x")
                finite(episode["native_reward"], "native_reward")
            signature = {key: protocol.get(key) for key in COMPARISON_KEYS}
            issues = []
            if evaluation.get("status") != "complete":
                issues.append("incomplete evaluation")
            if not planned or seeds != planned or len(set(seeds)) != len(seeds):
                issues.append("planned trials are missing or seeds are duplicated")
            if expected_seeds is not None and planned != expected_seeds:
                issues.append("seeds differ from the manifest")
            if reference_protocol is None and not issues:
                reference_protocol = signature
            elif reference_protocol is not None and signature != reference_protocol:
                issues.append("protocol differs from the first complete evaluation")
            if issues:
                stage["warning"] = "; ".join(issues) + ". Excluded from aggregate comparisons."
            else:
                stage["comparable"] = True
                stage["warning"] = None
                distances = [float(episode["max_x"]) for episode in episodes]
                stalls = [len(episode.get("stall_events", [])) for episode in episodes]
                stage.update({
                    "mean": statistics.mean(distances),
                    "median": statistics.median(distances),
                    "minimum": min(distances),
                    "maximum": max(distances),
                    "clears": sum(bool(episode["completed"]) for episode in episodes),
                    "count": len(episodes),
                    "mean_reward": statistics.mean(float(episode["native_reward"]) for episode in episodes),
                    "stalls": sum(stalls),
                    "stall_trials": sum(count > 0 for count in stalls),
                    "mean_stalls": statistics.mean(stalls),
                })
        stages.append(stage)
    return stages


def draw_chart(stages: list[dict], output: Path, session_id: str) -> None:
    os.environ.setdefault("MPLCONFIGDIR", str(output.parent / ".matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    plt.rcParams.update({"font.size": 10, "axes.titlesize": 12, "axes.labelsize": 10})
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.2), layout="constrained")
    fig.suptitle("Mario RL · session progress\n" + session_id, fontsize=15)
    complete = [stage for stage in stages if stage["comparable"]]
    score_data = bool(complete and all("mean_score_gain" in stage["evaluation"] for stage in complete))
    for axis in axes.flat:
        axis.grid(axis="y", alpha=0.22)
        axis.spines[["top", "right"]].set_visible(False)
        axis.set_xlabel("Additional training time (minutes)")
    axes[0, 0].set_title("Progress: mean, median, and observed range")
    axes[0, 0].set_ylabel("Maximum x position (level pixels)")
    axes[0, 1].set_title("Each seed, including regressions")
    axes[0, 1].set_ylabel("Maximum x position (level pixels)")
    axes[1, 0].set_title("Levels completed")
    axes[1, 0].set_ylabel("Trials reaching the flag")
    axes[1, 1].set_title("Game points earned before flag touch" if score_data else "Prolonged runs without a new maximum x")
    axes[1, 1].set_ylabel("Mean game points" if score_data else "Mean runs per trial")
    if complete:
        times = [stage["minutes"] for stage in complete]
        axes[0, 0].fill_between(times, [s["minimum"] for s in complete], [s["maximum"] for s in complete], color="#cce5ef", alpha=.65, label="minimum–maximum (not a CI)")
        axes[0, 0].plot(times, [s["mean"] for s in complete], "o-", color="#137b8c", label="mean")
        axes[0, 0].plot(times, [s["median"] for s in complete], "s--", color="#ef8b2c", label="median")
        axes[0, 0].legend(fontsize=8, loc="best")
        seeds = [episode["seed"] for episode in complete[0]["episodes"]]
        for seed in seeds:
            values = [next(episode["max_x"] for episode in stage["episodes"] if episode["seed"] == seed) for stage in complete]
            axes[0, 1].plot(times, values, "o-", linewidth=1.2, markersize=3, label=str(seed))
        axes[0, 1].legend(title="Seed", fontsize=8, ncol=3)
        axes[1, 0].plot(times, [s["clears"] for s in complete], "o-", color="#326f48")
        count = complete[0]["count"]
        axes[1, 0].set_ylim(-.2, count + .3)
        axes[1, 0].set_yticks(range(count + 1))
        axes[1, 0].set_ylabel(f"Trials reaching the flag (out of {count})")
        if score_data:
            axes[1, 1].plot(times, [s["evaluation"]["mean_score_gain"] for s in complete], "o-", color="#9b4560", label="All attempts")
            axes[1, 1].plot(times, [s["evaluation"]["mean_completed_score"] for s in complete], "s--", color="#326f48", label="Failures count as zero")
            axes[1, 1].legend(fontsize=8)
        else:
            axes[1, 1].plot(times, [s["mean_stalls"] for s in complete], "o-", color="#9b4560")
        axes[1, 1].set_ylim(bottom=0)
        for axis in axes.flat:
            axis.set_xlim(left=-.5, right=max(times[-1] + 1, 1))
    else:
        for axis in axes.flat:
            axis.text(.5, .5, "No complete, comparable\nevaluations yet", ha="center", va="center", transform=axis.transAxes)
    fig.savefig(output, dpi=150, facecolor="white")
    plt.close(fig)


def evaluation_asset(repo: Path, stage: dict, relative: str | None) -> Path | None:
    if not relative:
        return None
    path = (stage["evaluation_file"].parent / relative).resolve()
    if not path.is_relative_to(repo):
        raise ValueError(f"Evaluation asset escapes repository: {relative}")
    return path if path.is_file() else None


def make_report(repo: Path, manifest_path: Path, manifest: dict, stages: list[dict], document: Path, chart: Path, generated_at: str) -> str:
    guide = repo / "docs" / "aula" / "GUIA_DOCENTE.md"
    session = within(repo, manifest["session_dir"])
    config = manifest.get("configuration", {})
    trial_count = len(config.get("eval_seeds", []))
    planned_trials = f"{trial_count} trials" if trial_count else "planned trials"
    repeated_trials = f"{trial_count} repeated trials" if trial_count else "repeated trials"
    navigation = [
        existing_link("Teacher guide: a 35–45 minute lesson", guide, document),
        link("Session data and configuration", manifest_path, document),
        existing_link("Project and previous experiments", repo / "README.md", document),
    ]
    for key, label in (
        ("diagnostic_report_path", "Failure diagnosis and playback comparison"),
        ("comparison_report_path", "Baseline and trained-model comparison"),
    ):
        if manifest.get(key):
            report_file = within(repo, manifest[key])
            if report_file.is_file():
                navigation.append(existing_link(label, report_file, document))
    complete = [stage for stage in stages if stage["comparable"]]
    content = [
        "# Mario Learns: A Classroom Lab", "",
        "Compare how a reinforcement learning policy changes across saved stages. This dashboard brings together measurements, observable errors, and clips from the same level; results may improve or worsen.", "",
        f"**Session:** `{cell(manifest['session_id'])}` · **Status:** {STATUS.get(manifest.get('status'), cell(manifest.get('status', 'not specified')))} · **Updated:** {generated_at}.", "",
        " · ".join(navigation), "",
        "This dashboard keeps the same path, `docs/aula/README.md`, when new sessions are published. Previous reports remain in their results folders. GitHub shows the most recently uploaded version; it does not stream local training live. Access depends on repository permissions.", "",
        "## Using this in class", "",
        "1. Watch the first stage and write down a prediction.",
        "2. Compare the same seed at another stage: first the beginning, then the ending.",
        f"3. Check your visual impression against all {planned_trials}, the maximum position, and whether the flag was reached.",
        "4. Describe an observable error and a hypothesis; look for evidence that distinguishes observation from explanation.", "",
        "## What has happened so far", "",
    ]
    if len(complete) >= 2:
        first, last = complete[0], complete[-1]
        delta = last["mean"] - first["mean"]
        direction = "increased" if delta > 0 else "decreased" if delta < 0 else "did not change"
        content.append(f"Between the first and last comparable stages, the mean maximum position **{direction}: {number(first['mean'], 1)} → {number(last['mean'], 1)} pixels**. The last stage reached the flag in **{last['clears']} of {last['count']} trials**. This describes these trials on the same level; it does not establish general performance or consistent improvement.")
    elif complete:
        content.append("The starting point has been evaluated. Another comparable stage is needed to measure change during this session.")
    else:
        content.append("There are no complete, comparable evaluations yet. Pending stages are not counted as failures or zero values.")
    if config.get("objective") == "score":
        content += ["", "## Current objective: more game points while still finishing", "",
            "This session rewards actual score increases, with a separate bonus for finishing and a penalty for a non-clearing episode end. Native reward is retained only as a diagnostic. The score is measured at flag touch; the emulator stops before the later flag animation and remaining-time bonuses.", "",
            "| Stage | Mean points, all attempts | Mean points with failures counted as zero | Flag reached |",
            "| --- | ---: | ---: | ---: |",
        ]
        for stage in complete:
            evaluation = stage["evaluation"]
            content.append(f"| {cell(stage.get('label', stage['id']))} | {number(evaluation.get('mean_score_gain'), 1)} | {number(evaluation.get('mean_completed_score'), 1)} | {stage['clears']}/{stage['count']} |")
        if manifest.get("comparison_report_path"):
            target = within(repo, manifest["comparison_report_path"])
            if target.is_file():
                content += ["", link("Score experiment, selection rule, and final comparison", target, document)]
    followups = manifest.get("followup_evaluations", [])
    if followups:
        content += ["", "## Later evaluations of the saved model", "",
            "These evaluations use frozen model weights. Each trial set is reported separately; none is added to the training-stage curve or the original final test.", "",
        ]
        for followup in followups:
            report_file = within(repo, followup["report_path"])
            evaluation_file = within(repo, followup["evaluation_path"])
            label = followup.get("label", "Follow-up evaluation")
            title = link(label, report_file, document) if report_file.is_file() else f"{cell(label)} (report pending)"
            result = "**Evaluation pending.** No completed result is available."
            if evaluation_file.is_file():
                evaluation = read_json(evaluation_file)
                episodes = evaluation.get("episodes", [])
                planned = evaluation.get("protocol", {}).get("seeds", [])
                recorded = [episode.get("seed") for episode in episodes]
                if evaluation.get("status") == "complete" and planned and recorded == planned and len(set(recorded)) == len(recorded):
                    clears = sum(bool(episode["completed"]) for episode in episodes)
                    result = f"**Flag reached: {clears}/{len(episodes)} trials.** All {len(planned)} planned trials are complete."
                else:
                    result = "**Evaluation incomplete.** Partial or mismatched trials are not presented as a completed result."
                result += " " + link("Evaluation data", evaluation_file, document) + "."
            content.append(f"- {title} — {result}")
        content += ["", "## Training-stage progress"]
    content += ["", link("Progress chart for all comparable stages", chart, document, image=True), "",
        "The horizontal axis measures **additional training during this session**. The decisions in the table are cumulative and may include earlier training. The band shows the minimum and maximum across trials; it is not a confidence interval. The x position is a coordinate within the level, not a completion percentage.", "",
        "| Stage | Additional minutes | Cumulative decisions | Mean x | Median x | Min.–max. x | Flag |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for stage in stages:
        lead = f"| {cell(stage.get('label', stage['id']))} | {number(stage['minutes'], 1)} | {number(stage.get('training_timesteps'))}"
        if stage["comparable"]:
            content.append(lead + f" | {number(stage['mean'], 1)} | {number(stage['median'], 1)} | {number(stage['minimum'])}–{number(stage['maximum'])} | {stage['clears']}/{stage['count']} |")
        else:
            content.append(lead + " | pending/not comparable | — | — | — |")
    content += ["", "| Stage | Mean native reward | Runs without progress | Trials with a run |", "| --- | ---: | ---: | ---: |"]
    for stage in complete:
        content.append(f"| {cell(stage.get('label', stage['id']))} | {number(stage['mean_reward'], 1)} | {stage['stalls']} | {stage['stall_trials']}/{stage['count']} |")
    content += ["", "## How performance was measured", "",
        f"Planned seeds: **{', '.join(str(seed) for seed in config.get('eval_seeds', [])) or 'see manifest'}**. Sampling is reset for each trial; the seeds change the sampled actions in World 1-1, not the level layout. Evaluation uses frozen weights and native reward. The recorded training configuration is:", "",
        "| Parameter | Value |", "| --- | --- |",
    ]
    for key, label in (("reward_scale", "Training reward multiplier"), ("learning_rate", "Learning rate"), ("target_kl", "Target KL threshold"), ("ent_coef", "Entropy coefficient"), ("training_seed", "Training seed"), ("chunk_seconds", "Planned seconds per stage")):
        if key in config:
            content.append(f"| {label} | `{cell(config[key])}` |")
    protocol = complete[0]["evaluation"]["protocol"] if complete else {}
    threshold = protocol.get("stall_threshold_decisions")
    deterministic = protocol.get("deterministic")
    mode = "deterministic (preferred action)" if deterministic is True else "stochastic (sampled actions)" if deterministic is False else "see protocol"
    content += ["", f"Evaluation mode: **{mode}**. Limit per attempt: **{number(protocol.get('max_decisions'))} decisions**. A run without progress is recorded after **{number(threshold)} decisions without increasing the previous maximum x**, as defined by the protocol. This can include jumps or movement within an area already traversed; it does not automatically detect walls or the cause of a death.", "",
        "All recorded stages are shown, including regressions. Averages exclude evaluations that are incomplete or use a different protocol. Any partial attempt is documented in its JSON file. If a stage was selected for demonstration, that selection is labeled and does not replace the latest stage.", "",
        "Clips can cover an entire trial or an excerpt from its beginning or ending. The capture boundaries and full-episode marker are recorded in `evaluation.json`. Not every seed needs video: each row retains its trace and metrics.", "",
        "## Stages and evidence", "",
    ]
    for stage in stages:
        content += [f"### {cell(stage.get('label', stage['id']))}", "", f"Stage `{cell(stage['id'])}` · {number(stage['minutes'], 1)} additional minutes · {number(stage.get('training_timesteps'))} cumulative decisions.", ""]
        if stage.get("selected_for_demo"):
            content += ["**Selected for demonstration.** This stage was chosen from the observed stages; it is not an independent evaluation.", ""]
        if stage["warning"]:
            content += [f"**Note:** {stage['warning']}", ""]
        if stage["evaluation"] is None:
            continue
        evidence_links = [link("Full evaluation JSON", stage["evaluation_file"], document)]
        if stage.get("training_summary_path"):
            summary_path = within(repo, stage["training_summary_path"])
            if summary_path.is_file():
                evidence_links.append(link("Training summary", summary_path, document))
        content += [" · ".join(evidence_links), "", "| Seed | Max. x | Last x | Native reward | How the attempt ended | Runs without progress | Longest run (decisions) | Evidence |", "| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |"]
        for episode in stage["episodes"]:
            evidence = []
            for key, label in (("beginning", "beginning"), ("ending", "ending")):
                asset = evaluation_asset(repo, stage, episode.get("media", {}).get(key, {}).get("path"))
                if asset:
                    evidence.append(link(label, asset, document))
            trace = evaluation_asset(repo, stage, episode.get("trace_csv"))
            if trace:
                evidence.append(link("CSV trace", trace, document))
            terminal = evaluation_asset(repo, stage, episode.get("media", {}).get("terminal_frame"))
            if terminal:
                evidence.append(link("last frame", terminal, document))
            reason = END_REASONS.get(episode.get("end_reason"), cell(episode.get("end_reason", "unclassified")))
            content.append(f"| {episode['seed']} | {number(episode['max_x'])} | {number(episode.get('last_x'))} | {number(episode['native_reward'], 1)} | {reason} | {len(episode.get('stall_events', []))} | {number(episode.get('longest_no_progress_decisions'))} | {' · '.join(evidence) or 'no sample files'} |")
        # Keep the same predeclared seed visible across all stages; link all others.
        seed_order = config.get("eval_seeds", [])
        fixed_seed = seed_order[0] if seed_order else None
        displayed = next((episode for episode in stage["episodes"] if episode["seed"] == fixed_seed), None)
        if displayed:
            columns = []
            for key, label in (("beginning", "Beginning"), ("ending", "Ending")):
                metadata = displayed.get("media", {}).get(key, {})
                asset = evaluation_asset(repo, stage, metadata.get("path"))
                if asset:
                    caption = f"{label}, seed {fixed_seed}, decisions {metadata.get('first_decision', '?')}–{metadata.get('last_decision', '?')}"
                    columns.append((caption, link(caption, asset, document, image=True)))
            if len(columns) == 2:
                content += ["", f"| {columns[0][0]} | {columns[1][0]} |", "| --- | --- |", f"| {columns[0][1]} | {columns[1][1]} |"]
        content += ["", "**Discuss:** What can you observe at the end of this attempt? What evidence distinguishes a late jump, repeated actions, or a decision limit? Identifying the specific cause requires reviewing the clips; position alone does not reveal it.", ""]
    if manifest.get("final_audit_path"):
        audit_file = within(repo, manifest["final_audit_path"])
        if audit_file.is_file():
            audit = read_json(audit_file)
            audit_stage = {"evaluation_file": audit_file}
            audit_episodes = audit.get("episodes", [])
            content += ["## Final test with new seeds", "", f"These seeds were reserved for the final model; they are not included in the curve of {repeated_trials} or used to select a stage. They are still attempts on the same World 1-1 level.", "", link("Final test data", audit_file, document), ""]
            planned = audit.get("protocol", {}).get("seeds", [])
            if audit.get("status") == "complete" and planned and [ep["seed"] for ep in audit_episodes] == planned:
                values = [float(ep["max_x"]) for ep in audit_episodes]
                clears = sum(bool(ep["completed"]) for ep in audit_episodes)
                content += [f"Mean maximum position: **{number(statistics.mean(values), 1)} px** · Median: **{number(statistics.median(values), 1)} px** · Flag: **{clears}/{len(values)} trials**.", ""]
            else:
                content += ["**Final test incomplete.** Its partial attempts are not presented as a comparable aggregate result.", ""]
            content += ["| Seed | Max. x | Flag | Evidence |", "| ---: | ---: | ---: | --- |"]
            for episode in audit_episodes:
                evidence = []
                for key, label in (("beginning", "beginning"), ("ending", "ending")):
                    asset = evaluation_asset(repo, audit_stage, episode.get("media", {}).get(key, {}).get("path"))
                    if asset:
                        evidence.append(link(label, asset, document))
                trace = evaluation_asset(repo, audit_stage, episode.get("trace_csv"))
                if trace:
                    evidence.append(link("CSV trace", trace, document))
                content.append(f"| {episode['seed']} | {number(episode['max_x'])} | {'yes' if episode['completed'] else 'no'} | {' · '.join(evidence) or 'see JSON'} |")
            content.append("")
    content += ["## Saved materials and future sessions", ""]
    release_url = manifest.get("model_release_url")
    if release_url:
        if not str(release_url).startswith("https://github.com/"):
            raise ValueError("model_release_url must be a GitHub HTTPS release URL")
        content += [f"Published checkpoints can be downloaded from the [model release for this session]({release_url}). These files are separate from the code history and require repository access. The link is added to the manifest after the upload is confirmed; check the release for the files actually published.", ""]
    else:
        content += ["Checkpoint `.zip` files are stored locally; this manifest does not yet confirm a published release of model weights. Downloading the code from GitHub does not include those models. The manifest records their paths for anyone with that local copy.", ""]
    content += ["The repository retains the reports, metrics, and published samples. Detailed logs remain local.", ""]
    if manifest.get("latest_checkpoint"):
        content += [f"Latest recorded local checkpoint: `{cell(manifest['latest_checkpoint'])}`.", ""]
    if manifest.get("pending_stage"):
        content += [f"Stage still awaiting a complete evaluation: `{cell(manifest['pending_stage'])}`. Its weights may exist even if comparable metrics are not yet available.", ""]
    content += [
        link("Session report", session / "INFORME.md", document) + " · " + existing_link("Teacher guide", guide, document), "",
    ]
    archives = sorted((repo / "results").glob("teaching_*/INFORME.md"))
    if archives:
        content += ["Archived sessions:", ""]
        content += ["- " + link(path.parent.name, path, document) for path in archives]
        content.append("")
    if manifest.get("completion_reason"):
        content += [f"Recorded reason for ending the session: `{cell(manifest['completion_reason'])}`.", ""]
    content += ["To update this dashboard after generating new evaluations:", "", "```sh", f".venv/bin/python lesson_report.py --manifest {manifest_path.relative_to(repo).as_posix()} --repo-root .", "```", "", "The dashboard update remains local until it is committed and uploaded to GitHub. It does not run training or modify model weights.", ""]
    return "\n".join(content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output-dir", type=Path, default=Path("docs/aula"))
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    manifest_path = within(repo, args.manifest)
    manifest = read_json(manifest_path)
    if not manifest.get("session_id") or not manifest.get("session_dir"):
        parser.error("manifest must include session_id and session_dir")
    session = within(repo, manifest["session_dir"])
    output = within(repo, args.output_dir)
    session.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    stages = load_stages(repo, manifest)
    chart = session / "progress.png"
    draw_chart(stages, chart, str(manifest["session_id"]))
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    archive = session / "INFORME.md"
    # Create the current archive before discovering the session list.
    archive.touch(exist_ok=True)
    for document in (archive, output / "README.md"):
        contents = make_report(repo, manifest_path, manifest, stages, document, chart, generated_at)
        temporary = document.with_suffix(document.suffix + ".tmp")
        temporary.write_text(contents, encoding="utf-8")
        temporary.replace(document)
    summary = {"session_id": manifest["session_id"], "stages": len(stages), "comparable_stages": sum(s["comparable"] for s in stages), "index": str(output / "README.md"), "archive": str(archive), "chart": str(chart)}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
