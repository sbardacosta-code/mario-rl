#!/usr/bin/env python3
"""Validate and explain the bounded overnight Mario experiment."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime
import math
import json
from pathlib import Path
import statistics
from continue_lesson import digest, load, same_number, save, utc, within
from lesson_report import link


def require(ok, message):
    if not ok:
        raise ValueError(message)


def metrics(data):
    episodes = data["episodes"]
    require(bool(episodes), "No completed episodes")
    mean = lambda field: statistics.mean(float(ep[field]) for ep in episodes)
    weighted = lambda field: sum(float(ep[field]) if ep["completed"] else 0 for ep in episodes) / len(episodes)
    clears = sum(ep["completed"] for ep in episodes)
    return {"trials": len(episodes), "clears": clears, "mean_game_score": mean("game_score"),
            "mean_score_gain": mean("score_gain"), "mean_completed_score": weighted("score_gain"),
            "mean_augmented_score_gain": mean("augmented_score_gain"),
            "mean_completed_augmented_score": weighted("augmented_score_gain"),
            "mean_one_ups": mean("one_ups"), "mean_custom_one_up_bonus": mean("custom_one_up_bonus"),
            "mean_flag_height_bonus": mean("flag_height_bonus"),
            "mean_score_on_clears": sum(ep["score_gain"] for ep in episodes if ep["completed"]) / clears if clears else None,
            "median_game_score": statistics.median(ep["game_score"] for ep in episodes),
            "max_game_score": max(ep["game_score"] for ep in episodes)}


def ranking_key(row):
    return (row["mean_completed_augmented_score"], row["mean_completed_score"], row["clears"], -row.get("index", 0))


def qualified(row):
    return row["trials"] == 20 and row["clears"] >= 19


def best_stage(rows):
    # The preserved baseline always remains eligible, even if its sampled clear count is lower.
    eligible = [row for row in rows if row["index"] == 0 or qualified(row)]
    require(bool(eligible), "Baseline missing from selection")
    return max(eligible, key=ranking_key)


def checked_evaluation(path, seeds, expected_hash, videos=(), reward_config=None, traces=True):
    path = path.resolve()
    data = load(path)
    episodes = data.get("episodes", [])
    require(data.get("status") == "complete" and data.get("partial_episode") is None, "Incomplete evaluation")
    require(data.get("learning_updates") == 0 and data.get("model_sha256") == expected_hash, "Model changed or evaluation learned")
    require(data.get("model_sha256_after") == expected_hash and data.get("model_file_unchanged") is True, "Frozen file verification failed")
    require(data.get("policy_unchanged") is True and data.get("policy_sha256_before") and data.get("policy_sha256_before") == data.get("policy_sha256_after"), "Frozen policy verification failed")
    protocol = data["protocol"]
    require(seeds and len(set(seeds)) == len(seeds) and protocol.get("seeds") == seeds and [ep["seed"] for ep in episodes] == seeds, "Incomplete or mismatched seeds")
    require(protocol.get("deterministic") is False and protocol.get("max_decisions") == 3000 and protocol.get("action_space") == "RIGHT_ONLY", "Unexpected evaluation protocol")
    require(protocol.get("objective") == "score_events" and protocol.get("score_weight") == 1.0, "Evaluation objective differs")
    if reward_config is not None:
        require(protocol.get("event_reward_config") == reward_config, "Event reward definition differs")
    for ep in episodes:
        for key in ("game_score", "initial_score", "score_gain", "one_ups", "custom_one_up_bonus", "augmented_score_gain", "flag_height_bonus"):
            require(math.isfinite(float(ep[key])), "Nonfinite event metric: " + key)
        require(not ep.get("score_anomalies"), "Score anomaly requires review")
        require(ep["game_score"] - ep["initial_score"] == ep["score_gain"], "HUD score accounting mismatch")
        require(ep["one_ups"] >= 0 and ep["one_ups"] == int(ep["one_ups"]), "Invalid 1UP count")
        require(same_number(ep["custom_one_up_bonus"], ep["one_ups"] * 1000), "Custom 1UP bonus accounting mismatch")
        require(same_number(ep["augmented_score_gain"], ep["score_gain"] + ep["custom_one_up_bonus"]), "Augmented score double-counted or incomplete")
        require(1 <= ep["decisions"] <= 3000 and (ep["terminated"] or ep["truncated"]), "Incomplete trial boundary")
        for media in ep.get("media", {}).values():
            require(within(path.parent, media if isinstance(media, str) else media["path"]).is_file(), "Missing recorded media")
        if ep["seed"] in videos:
            clip = ep.get("media", {}).get("beginning", {})
            require(clip.get("is_full_episode") and clip.get("first_decision") == 1 and clip.get("last_decision") == ep["decisions"], "Missing full preselected clip")
        trace_path = within(path.parent, ep["trace_csv"])
        require(trace_path.is_file(), "Missing trace")
        if traces:
            with trace_path.open() as stream:
                rows = list(csv.DictReader(stream))
            require(len(rows) == ep["decisions"] == ep["trace_rows"] and [int(row["decision"]) for row in rows] == list(range(1, len(rows) + 1)), "Trace rows mismatch")
            for key in ("game_score", "score_gain", "one_ups", "custom_one_up_bonus", "augmented_score_gain", "flag_height_bonus"):
                require(same_number(float(rows[-1][key]), ep[key]), "Final event trace mismatch: " + key)
            require(math.isclose(sum(float(row["native_reward"]) for row in rows), ep["native_reward"], abs_tol=1e-7), "Native reward trace total differs")
            require(math.isclose(sum(float(row["objective_reward"]) for row in rows), ep["objective_reward_sum"], abs_tol=1e-7), "Objective reward trace total differs")
            event_path = within(path.parent, ep["event_trace_jsonl"])
            events = [json.loads(line) for line in event_path.read_text().splitlines()]
            require(len(events) == ep["decisions"] == ep["event_trace_rows"], "Event trace count differs")
            require([event["decision"] for event in events] == list(range(1, len(events) + 1)), "Event trace order differs")
            for event, row in zip(events, rows):
                score = event["score_metrics"]
                for key in ("score_gain", "one_ups", "custom_one_up_bonus", "augmented_score_gain", "flag_height_bonus", "objective_reward_sum", "native_reward_sum"):
                    require(same_number(score[key], float(row[key])), "Event JSONL and CSV differ: " + key)
    result = metrics(data)
    require(result["clears"] == data["level_completions"], "Completion aggregate mismatch")
    for key in ("mean_game_score", "mean_score_gain", "mean_completed_score", "mean_augmented_score_gain", "mean_completed_augmented_score", "mean_one_ups", "mean_custom_one_up_bonus", "mean_flag_height_bonus"):
        require(same_number(result[key], data.get(key)), "Aggregate mismatch: " + key)
    return data


def build_report(repo, manifest_path):
    repo, manifest_path = repo.resolve(), manifest_path.resolve()
    manifest = load(manifest_path)
    run, document = manifest_path.parent, manifest_path.parent / "README.md"
    plan_path = within(repo, manifest["experiment_plan_path"])
    require(digest(plan_path) == manifest["experiment_plan_sha256"], "Plan changed")
    plan = load(plan_path)
    require(digest(within(repo, plan["initial_checkpoint"])) == plan["initial_checkpoint_sha256"], "Baseline changed")
    rows, datasets = [], {}
    content = ["# Mario's overnight score experiment", "", f"**Status: {manifest['status']}.** Overall deadline: **{plan['deadline_utc']}**. This is a maximum wall-clock budget, including setup, evaluation and publication—not six hours of optimizer updates.", "",
               "[Permanent classroom page](../../docs/aula/README.md) · [Frozen plan](experiment_plan.json) · [All saved stage clips](INFORME.md)", "",
               "## What Mario is trying to learn", "",
               "Game points and finishing remain separate measurements. The event-aware environment records the actual HUD increase, waits for the real flagpole award before stopping, and excludes later timer conversion. A separate teaching bonus of **1,000 custom points per verified extra life** makes 1UPs valuable even when the HUD does not change. Custom points are not Nintendo game points.", "",
               "**Augmented points = actual HUD points earned + custom 1UP points.** The real flagpole award is already inside actual HUD points and is never added again. Flag height and the observed flag award are also recorded separately. Extra-life count alone does not establish which object caused it; see the event evidence.", "",
               "Two initial 15-minute trials start independently from the same preserved completion model: sparse event reward and a gentle bridge from the existing reward. Both use learning rate 0.000025, target KL 0.01 and entropy 0.003. Later decisions follow the plan's validation and rollback rules. Different objectives and settings change together, so this is not a controlled attribution to one parameter.", "",
               "The bridge mixes 0.01 × native reward and event reward with the declared weight. Its weight starts at 0.25 and rises only after two qualifying improvements at that weight. A confirmed regression returns to the best checkpoint, then permits one conservative retry at learning rate 0.00001. Repeated failure ends that path or uses a previously successful configuration. Training can stop early; spending the entire allowance is not itself a goal.", "",
               "The current working checkpoint and protected best checkpoint are separate. Qualified stages without confirmed regressions continue learning even when validation ties the previous best. An unqualified or partial stage rolls back to the protected best. This avoids restarting the same 15 minutes of learning on every plateau.", "",
               "## Every stage, including regressions", "",
               "The same 20 validation action seeds are reused for model selection. A new stage needs at least 19/20 clears to qualify. Completed-score means keep all attempts in the denominator and assign failed attempts zero. Seeds vary stochastic moves on World 1-1, not terrain.", "",
               "| Stage | Minutes learned | Objective / weight / LR | Clears | Mean HUD gain | Completed HUD | Custom 1UP mean | Completed augmented points | Decision |",
               "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for stage in manifest["stages"]:
        path = within(repo, stage["evaluation_path"])
        if not path.is_file() or load(path).get("status") != "complete" or load(path).get("partial_episode") is not None:
            content.append(f"| {stage['id']} | {stage['elapsed_training_seconds'] / 60:.1f} | Pending | Pending | Pending | Pending | Pending | Pending | Incomplete; excluded |")
            continue
        require(digest(within(repo, stage["checkpoint_path"])) == stage["checkpoint_sha256"], "Stage checkpoint changed")
        data = checked_evaluation(path, plan["validation_seeds"], stage["checkpoint_sha256"], plan["validation_video_seeds"], plan["event_reward_config"])
        value = {**metrics(data), **stage, "index": stage["index"]}
        rows.append(value); datasets[stage["id"]] = data
        config = stage.get("training_configuration", {})
        settings = "Preserved baseline" if stage["index"] == 0 else f"{config['objective']} / {config['score_weight']} / {config['learning_rate']}"
        content.append(f"| {stage['id']} | {stage['elapsed_training_seconds'] / 60:.1f} | {settings} | {value['clears']}/20 | {value['mean_score_gain']:,.1f} | {value['mean_completed_score']:,.1f} | {value['mean_custom_one_up_bonus']:,.1f} | {value['mean_completed_augmented_score']:,.1f} | {stage.get('decision', 'Baseline')} |")
    if not rows:
        content.append("| Baseline pending | 0 | Preserved baseline | Pending | Pending | Pending | Pending | Pending | No complete results |")
    for failure in manifest.get("failed_attempts", []):
        content += ["", f"**{failure['stage_id']} interrupted:** {failure['error']}. Artifacts are retained; no unverified score is treated as a completed result."]
    content += ["", "### Preselected full gameplay", "", "| Stage | Seed | HUD gain | Custom bonus | Flag award | Extra lives | Full clip |", "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for stage in rows:
        path = within(repo, stage["evaluation_path"])
        for ep in datasets[stage["id"]]["episodes"]:
            if ep["seed"] in plan["validation_video_seeds"]:
                content.append(f"| {stage['id']} | {ep['seed']} | {ep['score_gain']:,} | {ep['custom_one_up_bonus']:,} | {ep['flag_height_bonus']:,} | {ep['one_ups']} | {link('Watch full attempt', path.parent / ep['media']['beginning']['path'], document)} |")
    content += ["", "### Confirmation checks and rollbacks", ""]
    if not manifest.get("confirmation_checks"):
        content += ["No completed confirmation checks yet.", ""]
    for check in manifest.get("confirmation_checks", []):
        content += [f"- {check['stage_id']}: {check['decision']}. Candidate {check['candidate']['clears']}/20 and {check['candidate']['mean_completed_augmented_score']:,.1f} completed augmented points; reference {check['reference']['clears']}/20 and {check['reference']['mean_completed_augmented_score']:,.1f}. {link('Recorded check', within(repo, check['record_path']), document)}"]
    content += ["", "Confirmation pairs use additional validation seeds declared before launch. They diagnose an apparent regression; they do not replace the original selection set or count as the final test.", "", "## Final held-out comparison", ""]
    final = []
    selection = None
    if manifest.get("selection_path"):
        selection_path = within(repo, manifest["selection_path"])
        require(digest(selection_path) == manifest["selection_sha256"], "Selection changed")
        selection = load(selection_path)
        require(selection["holdouts_evaluated_at_selection"] is False, "Selection used holdouts")
        content += [f"Frozen choice: **{selection['selected_stage_id']}**. [Selection and ranking](selection.json). The preserved baseline was always eligible.", ""]
    for label, field, hash_value in (("Preserved baseline", "baseline_audit_path", plan["initial_checkpoint_sha256"]), ("Selected checkpoint", "candidate_audit_path", manifest.get("selected_checkpoint_sha256"))):
        if manifest.get(field):
            path = within(repo, manifest[field])
            data = checked_evaluation(path, plan["holdout_seeds"], hash_value, plan["holdout_video_seeds"], plan["event_reward_config"])
            require(selection and datetime.fromisoformat(selection["selected_at"]) < datetime.fromisoformat(data["started_at"]), "Selection was not frozen before final test")
            final.append((label, data, metrics(data), path))
    if len(final) != 2:
        content += ["Pending or incomplete. A final comparison requires all 100 planned attempts for both frozen models; no partial result is reported as final.", ""]
    else:
        require(final[0][1]["protocol"] == final[1][1]["protocol"], "Final protocols differ")
        a, b = final[0][2], final[1][2]
        preferred = selection["selected_stage_id"] != "00_baseline" and b["clears"] >= 95 and b["mean_completed_augmented_score"] > a["mean_completed_augmented_score"]
        content += ["Both frozen models received the same 100 reserved action seeds under the new event-aware environment. Prior experiments stopped earlier at the flag, so their scores are not pooled with this test.", "",
                    "| Model | Clears | Mean HUD score | Mean HUD gain | Completed HUD | Mean custom 1UP points | Completed augmented score | Median / maximum HUD |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for label, data, value, path in final:
            content.append(f"| {label} | {value['clears']}/100 | {value['mean_game_score']:,.1f} | {value['mean_score_gain']:,.1f} | {value['mean_completed_score']:,.1f} | {value['mean_custom_one_up_bonus']:,.1f} | {value['mean_completed_augmented_score']:,.1f} | {value['median_game_score']:,.1f} / {value['max_game_score']:,.1f} |")
        content += ["", "The new checkpoint meets the observed demonstration criteria; keep the baseline available." if preferred else "Keep the preserved baseline as the preferred demonstration model. This run did not establish a qualifying score gain.", "",
                    "The criteria require at least 95/100 final clears and improved completed augmented points. This sample does not guarantee a 95% population success rate, a maximum possible score, or generalization to other levels. Inspect actual HUD points separately: a custom-bonus improvement can occur without a game-score improvement.", "",
                    "| Seed | Baseline HUD / custom / cleared | Candidate HUD / custom / cleared | Evidence |", "| ---: | --- | --- | --- |"]
        for first, second in zip(final[0][1]["episodes"], final[1][1]["episodes"]):
            evidence = []
            for ep, entry in ((first, final[0]), (second, final[1])):
                evidence.append(link(entry[0] + " trace", entry[3].parent / ep["trace_csv"], document))
                if ep["seed"] in plan["holdout_video_seeds"]:
                    evidence.append(link(entry[0] + " full clip", entry[3].parent / ep["media"]["beginning"]["path"], document))
            content.append(f"| {first['seed']} | {first['score_gain']:,} / {first['custom_one_up_bonus']:,} / {'Yes' if first['completed'] else 'No'} | {second['score_gain']:,} / {second['custom_one_up_bonus']:,} / {'Yes' if second['completed'] else 'No'} | {' · '.join(evidence)} |")
        save(run / "verification.json", {"verified_at": utc(), "complete_stages": len(rows), "baseline": a, "candidate": b,
                                         "selection_preceded_holdouts": True, "all_final_event_traces_checked": True, "recommend_candidate": preferred})
    content += ["", "## Classroom discussion", "", "- Which changes are visible in the clips, and which explanations are still guesses?",
                "- Did the custom 1UP bonus improve actual HUD points, or a different teaching objective?",
                "- Why can sparse rewards damage a policy that already finishes reliably?",
                "- Did increasing the score weight help every time? Why retain regressions and rollbacks?",
                "- Why freeze selection before the final test? What would another level test?", "",
                "The live desktop window observes one of four training environments. Closing it does not stop training. Saved clips are uploaded to GitHub when publication succeeds; retained local files can be published again without training.", ""]
    if manifest.get("model_release_url"):
        content += [f"[Download verified model snapshots]({manifest['model_release_url']})", ""]
    temporary = document.with_suffix(".md.tmp"); temporary.write_text("\n".join(content)); temporary.replace(document)
    return {"complete_stages": len(rows), "final_comparison_complete": len(final) == 2}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(); root = Path(__file__).resolve().parent
    print(build_report(root, within(root, args.manifest)))
