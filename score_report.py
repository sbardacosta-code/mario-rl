#!/usr/bin/env python3
"""Verify frozen score evaluations and explain every saved classroom stage."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime
import math
from pathlib import Path
import statistics

from continue_lesson import digest, load, same_number, save, utc, within
from lesson_report import link


SELECTION_RULE = ("Among new stages with at least 19/20 validation clears, choose greatest mean completed score "
                  "(failed attempts count zero), then clear count, then mean score gain, then earliest stage. "
                  "If none qualifies, choose most clears, then mean completed score, then mean score gain, then earliest stage "
                  "as a diagnostic candidate only. Save this choice before either final test; preserve the baseline.")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def metrics(data):
    episodes = data["episodes"]
    require(bool(episodes), "No complete episodes")
    points = [float(e["game_score"]) for e in episodes]
    clears = [float(e["score_gain"]) for e in episodes if e["completed"]]
    return {"trials": len(episodes), "clears": len(clears), "mean_game_score": statistics.mean(points),
            "mean_score_gain": statistics.mean(float(e["score_gain"]) for e in episodes),
            "mean_completed_score": sum(clears) / len(episodes), "mean_score_on_clears": statistics.mean(clears) if clears else None,
            "median_game_score": statistics.median(points), "max_game_score": max(points)}


def rank_candidates(entries):
    require(bool(entries), "No candidate stages")
    require(len({e["stage_id"] for e in entries}) == len(entries), "Duplicate candidate stage IDs")
    for item in entries:
        require(item["trials"] == 20 and 0 <= item["clears"] <= 20, "Incomplete candidate validation")
        require(all(math.isfinite(float(item[k])) for k in ("mean_completed_score", "mean_score_gain")), "Non-finite ranking")
    qualified = any(item["clears"] >= 19 for item in entries)

    def key(item):
        tail = (-item["mean_score_gain"], item["stage_id"])
        if qualified:
            return (item["clears"] < 19, -item["mean_completed_score"], -item["clears"], *tail)
        return (-item["clears"], -item["mean_completed_score"], *tail)

    return sorted(entries, key=key), qualified


def checked_evaluation(path, seeds, expected_hash, videos=(), verify_traces=False):
    path = path.resolve()
    data = load(path)
    episodes = data.get("episodes", [])
    protocol = data.get("protocol", {})
    require(data.get("status") == "complete" and data.get("partial_episode") is None, "Evaluation is not complete")
    require(data.get("learning_updates") == 0 and data.get("model_sha256") == expected_hash, "Frozen checkpoint mismatch")
    require(seeds and len(set(seeds)) == len(seeds) and protocol.get("seeds") == seeds and [e.get("seed") for e in episodes] == seeds, "Missing, reordered or duplicate trials")
    expected = {"environment": "SuperMarioBros-1-1-v0", "max_decisions": 3000, "deterministic": False,
                "action_space": "RIGHT_ONLY", "action_repeat": 4, "observation_shape": [4, 84, 84],
                "reward": "native reward summed over repeated frames", "device": "cpu",
                "stall_threshold_decisions": 120}
    require(all(protocol.get(k) == v for k, v in expected.items()), "Evaluation protocol changed")
    for ep in episodes:
        for key in ("game_score", "initial_score", "score_gain", "max_score", "coins", "native_reward", "max_x"):
            require(math.isfinite(float(ep[key])), "Non-finite " + key)
        require(ep["game_score"] >= 0 and ep["coins"] >= 0 and ep["score_gain"] == ep["game_score"] - ep["initial_score"], "Score accounting mismatch")
        require(not ep.get("score_anomalies"), "Score anomaly must be resolved before comparison")
        require(ep["max_score"] >= max(ep["initial_score"], ep["game_score"]), "Maximum score mismatch")
        require(1 <= ep["decisions"] <= 3000 and (ep["terminated"] or ep["truncated"]), "Missing episode boundary")
        require(type(ep["completed"]) is bool, "Completion must be boolean")
        for media in ep.get("media", {}).values():
            asset = within(path.parent, media if isinstance(media, str) else media["path"])
            require(asset.is_file(), "Missing recorded media")
        if ep["seed"] in videos:
            clip = ep.get("media", {}).get("beginning", {})
            require(clip.get("is_full_episode") and clip.get("first_decision") == 1 and clip.get("last_decision") == ep["decisions"], "Missing full preselected clip")
        trace_path = within(path.parent, ep["trace_csv"])
        require(trace_path.is_file(), "Missing decision trace")
        if verify_traces:
            with trace_path.open() as stream:
                rows = list(csv.DictReader(stream))
            require(len(rows) == ep["decisions"] == ep["trace_rows"] and [int(r["decision"]) for r in rows] == list(range(1, len(rows) + 1)), "Decision trace length mismatch")
            require(math.isclose(sum(float(r["native_reward"]) for r in rows), ep["native_reward"], abs_tol=1e-7), "Native reward trace mismatch")
            for field in ("game_score", "score_gain", "coins", "max_x", "raw_frames"):
                require(same_number(float(rows[-1][field]), ep[field]), "Final trace field mismatch: " + field)
            for field, episode_field in (("flag_get", "completed"), ("terminated", "terminated"), ("truncated", "truncated")):
                require(bool(int(rows[-1][field])) == ep[episode_field], "Final boundary mismatch")
            counts = Counter(int(row["action"]) for row in rows)
            require([counts[i] for i in range(5)] == ep["action_counts"], "Action counts mismatch")
    calculated = metrics(data)
    require(data.get("level_completions") == calculated["clears"], "Completion aggregate mismatch")
    require(same_number(data.get("completion_rate"), calculated["clears"] / len(episodes)), "Completion rate mismatch")
    for key in ("mean_game_score", "mean_score_gain", "mean_completed_score", "mean_score_on_clears"):
        require(same_number(data.get(key), calculated[key]), "Score aggregate mismatch: " + key)
    return data


def number(value):
    return "—" if value is None else f"{value:,.1f}"


def build_report(repo, manifest_path):
    repo, manifest_path = repo.resolve(), manifest_path.resolve()
    manifest = load(manifest_path)
    run = manifest_path.parent
    document = run / "README.md"
    plan_path = within(repo, manifest["experiment_plan_path"])
    require(digest(plan_path) == manifest["experiment_plan_sha256"], "Plan changed")
    plan = load(plan_path)
    require(digest(within(repo, plan["initial_checkpoint"])) == plan["initial_checkpoint_sha256"], "Baseline checkpoint changed")
    require(len(plan["validation_seeds"]) == 20 and len(plan["holdout_seeds"]) == 100 and not set(plan["validation_seeds"]) & set(plan["holdout_seeds"]), "Invalid seed split")
    stages = []
    for stage in manifest["stages"]:
        require(digest(within(repo, stage["checkpoint_path"])) == stage["checkpoint_sha256"], "Saved stage checkpoint changed")
        data = checked_evaluation(within(repo, stage["evaluation_path"]), plan["validation_seeds"], stage["checkpoint_sha256"], plan["validation_video_seeds"], True)
        stages.append((stage, data, metrics(data)))
    content = ["# Can Mario finish with more points?", "", f"**Status: {manifest['status']}.** Training budget: {manifest['planned_training_seconds'] / 60:.0f} minutes, saved every 15 minutes.", "",
               "[Permanent classroom gallery](../../docs/aula/README.md) · [Predeclared plan](experiment_plan.json) · [Stage clips and native-reward diagnostics](INFORME.md)", "",
               "## What changed", "",
               "The preserved starting model learned to finish World 1-1. This experiment changes its learning objective to game points while retaining a finish bonus and a failure penalty. The prior model and every new checkpoint remain available.", "",
               "**Training reward per decision:** HUD score increase ÷ 1,000, plus 5 once for reaching the flag, or minus 5 when an attempt ends without the flag. There is no added progress reward, native reward, or separate coin bonus. Coins, enemies and items matter when they change the HUD score. PPO hyperparameters remain unchanged.", "",
               "**Measured points:** the HUD score at the flag or episode end. The emulator stops the attempt there, so subsequent time-bonus conversion is excluded. The five RIGHT_ONLY actions cannot backtrack. This experiment searches for a higher score within these limits; it does not establish the maximum possible game score.", "",
               "## Live training window", "",
               f"Current phase: **{manifest.get('active_evaluation') or manifest.get('active_stage') or manifest['status']}**. The window shows frames from one of four actual training environments. It is an observer: closing it leaves training running. During evaluation it shows the last training frame with the phase; after completion it becomes an archived view.", "",
               f"Open it locally with `.venv/bin/python watch_training.py {manifest['session_dir']}`. A GitHub page contains recordings, not the live desktop window.", "",
               "## Every 15-minute stage", "",
               "Twenty fixed validation action seeds are reused at every stage. They measure the same level and starting state with different sampled actions, not different levels. These results select the candidate and are kept separate from the final test. Failed attempts contribute zero to **mean completed score** (earned points = final HUD minus starting HUD); ordinary mean points includes failures and uses raw HUD values. Mean on clears also uses earned points.", "",
               "| Stage | Training | Clears | Mean HUD points | Mean earned on clears | Mean completed score | Median / maximum HUD | Change from previous |",
               "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    previous = None
    for stage, data, score in stages:
        change = "Preserved baseline" if previous is None else f"{score['clears'] - previous['clears']:+d} clears; {score['mean_completed_score'] - previous['mean_completed_score']:+,.1f} completed points"
        content.append(f"| {stage['id']} | {stage['elapsed_training_seconds'] / 60:.1f} min | {score['clears']}/20 | {number(score['mean_game_score'])} | {number(score['mean_score_on_clears'])} | {number(score['mean_completed_score'])} | {number(score['median_game_score'])} / {number(score['max_game_score'])} | {change} |")
        previous = score
    if not stages:
        content.append("| Baseline evaluation pending | 0 | Pending | Pending | Pending | Pending | Pending | No complete results yet |")
    if manifest.get("pending_stage"):
        content += ["", f"Stage {manifest['pending_stage']['id']} has a saved checkpoint, but its validation is pending. It is excluded from the comparison."]
    content += ["", "Lower completion or completed points is a regression in this validation sample. Higher ordinary points with fewer finishes can indicate a tradeoff. Videos show behavior; numerical changes alone do not identify a particular trick or failure cause.", "",
                "### Evidence from each stage", "", "Three full clips were preselected before training. Review the same seeds across stages, including regressions.", "", "| Stage | Seed | Flag | Points | Evidence |", "| --- | ---: | --- | ---: | --- |"]
    for stage, data, score in stages:
        evaluation_path = within(repo, stage["evaluation_path"])
        for ep in data["episodes"]:
            if ep["seed"] in plan["validation_video_seeds"]:
                clip = evaluation_path.parent / ep["media"]["beginning"]["path"]
                trace = evaluation_path.parent / ep["trace_csv"]
                content.append(f"| {stage['id']} | {ep['seed']} | {'Yes' if ep['completed'] else 'No'} | {ep['game_score']:,} | {link('Full clip', clip, document)} · {link('Decision trace', trace, document)} |")
    content += [""]
    for stage, data, score in stages:
        if stage.get("training_summary_path"):
            summary = within(repo, stage["training_summary_path"])
            content += ["", link(stage["id"] + " verified learning updates", summary, document) + " · " + link("Learning metrics", summary.parent / "learning_metrics.csv", document), ""]
    content += ["", "## Selecting the candidate before the final test", "", SELECTION_RULE, ""]
    selection = None
    if manifest.get("selection_path"):
        selection_path = within(repo, manifest["selection_path"])
        require(digest(selection_path) == manifest["selection_sha256"], "Selection changed")
        selection = load(selection_path)
        require(selection["holdouts_evaluated_at_selection"] is False and selection["holdout_seeds"] == plan["holdout_seeds"], "Holdout selection protocol changed")
        require(selection["selected_checkpoint"] == manifest["selected_checkpoint"] and selection["selected_checkpoint_sha256"] == manifest["selected_checkpoint_sha256"], "Selected checkpoint mismatch")
        qualifier = "qualified on validation" if selection["qualified"] else "diagnostic only; no new stage met 19/20 clears"
        content += [f"Selected **{selection['selected_stage_id']}**: {qualifier}. [Frozen choice and ranking](selection.json).", ""]
    else:
        content += ["Pending. No final test has been used to choose a checkpoint.", ""]
    final = []
    for label, key, hash_value in (("Preserved baseline", "baseline_audit_path", plan["initial_checkpoint_sha256"]),
                                   ("Selected score candidate", "candidate_audit_path", manifest.get("selected_checkpoint_sha256"))):
        if manifest.get(key):
            data = checked_evaluation(within(repo, manifest[key]), plan["holdout_seeds"], hash_value, plan["holdout_video_seeds"], True)
            require(selection is not None and datetime.fromisoformat(selection["selected_at"]) < datetime.fromisoformat(data["started_at"]), "Holdouts began before selection was frozen")
            final.append((label, data, metrics(data), within(repo, manifest[key])))
    content += ["## Paired final test", ""]
    if len(final) != 2:
        content += ["Pending. Both models must complete all 100 reserved attempts before any final comparison or replacement recommendation is published. Missing or partial results are not zeros.", ""]
    else:
        baseline, candidate = final
        require(baseline[1]["protocol"] == candidate[1]["protocol"], "Final protocols differ")
        require(digest(within(repo, manifest["selected_checkpoint"])) == manifest["selected_checkpoint_sha256"], "Selected model changed")
        promote = selection["qualified"] and candidate[2]["clears"] >= 95 and candidate[2]["mean_completed_score"] > baseline[2]["mean_completed_score"]
        content += ["The two frozen checkpoints received the same 100 new stochastic action seeds, reserved until after selection. These are attempts on the same World 1-1 start, not new levels. No learning occurs during this test.", "",
                    "| Model | Clears | Mean HUD points | Mean earned points on clears | Mean completed score | Median HUD points | Maximum HUD points |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for label, data, score, path in final:
            content.append(f"| {label} | {score['clears']}/100 | {number(score['mean_game_score'])} | {number(score['mean_score_on_clears'])} | {number(score['mean_completed_score'])} | {number(score['median_game_score'])} | {number(score['max_game_score'])} |")
        recommendation = "The score candidate meets the predeclared observed criteria and is preferred for score-focused demonstrations; keep the original baseline available." if promote else "Keep the preserved baseline as the preferred model. This candidate did not meet every predeclared validation, completion and score criterion; retain it as a documented experiment."
        content += ["", recommendation, "", "The threshold requires a validation-qualified candidate, at least 95/100 final clears and higher mean completed score. Meeting it in one sample does not guarantee a 95% underlying success rate or establish a causal benefit across independent training runs. Scores may also reflect stochastic action differences.", "",
                    "### Matched full gameplay", "", "Four seeds were selected in the plan, before any results.", "", "| Seed | Preserved baseline | Score candidate |", "| ---: | --- | --- |"]
        for seed in plan["holdout_video_seeds"]:
            clips = []
            for label, data, score, path in final:
                ep = next(ep for ep in data["episodes"] if ep["seed"] == seed)
                clips.append(link(f"{ep['game_score']:,} points; {'flag' if ep['completed'] else 'no flag'}", path.parent / ep["media"]["beginning"]["path"], document))
            content.append(f"| {seed} | {clips[0]} | {clips[1]} |")
        content += ["", "### Every final-test attempt", "", "| Seed | Baseline points | Baseline flag | Candidate points | Candidate flag | Traces |", "| ---: | ---: | --- | ---: | --- | --- |"]
        for first, second in zip(baseline[1]["episodes"], candidate[1]["episodes"]):
            traces = link("Baseline", baseline[3].parent / first["trace_csv"], document) + " · " + link("Candidate", candidate[3].parent / second["trace_csv"], document)
            content.append(f"| {first['seed']} | {first['game_score']:,} | {'Yes' if first['completed'] else 'No'} | {second['game_score']:,} | {'Yes' if second['completed'] else 'No'} | {traces} |")
        save(run / "verification.json", {"verified_at": utc(), "learning_updates_during_evaluation": 0,
                                         "complete_validation_stages": len(stages), "score_and_native_reward_traces_verified": True,
                                         "baseline_unchanged": True, "selection_frozen_before_holdouts": True,
                                         "baseline": baseline[2], "candidate": candidate[2], "candidate_meets_predeclared_criteria": promote})
        content += ["", "[Verified results](verification.json)", ""]
    content += ["## Classroom questions", "", "- Can Mario collect more points while becoming less reliable at finishing?",
                "- Which behavior changes can we actually see in the matched clips?",
                "- Did each additional 15 minutes improve the same metric?",
                "- Why keep failed attempts in the denominator and reserve a final test?",
                "- How would backtracking, later time bonuses, or another level change the experiment?", ""]
    if manifest.get("model_release_url"):
        content += [f"[Download every saved model]({manifest['model_release_url']})", ""]
    temporary = document.with_suffix(".md.tmp")
    temporary.write_text("\n".join(content))
    temporary.replace(document)
    return {"verified_stages": len(stages), "complete_final_comparison": len(final) == 2}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent
    path = within(repo, args.manifest)
    require(path.is_relative_to(repo / "results"), "Manifest must be under results")
    print(build_report(repo, path))


if __name__ == "__main__":
    main()
