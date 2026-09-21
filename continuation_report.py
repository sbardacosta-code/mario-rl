#!/usr/bin/env python3
"""Explain a bounded continuation experiment without changing its models."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def wilson(k, n):
    z = 1.959963984540054
    p = k / n
    den = 1 + z*z/n
    mid = (p + z*z/(2*n)) / den
    rad = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return [mid-rad, mid+rad]


def verify_evaluation(repo, path, expected_seeds, expected_hash):
    data = read(path)
    episodes = data['episodes']
    assert data['status'] == 'complete' and data.get('partial_episode') is None
    assert data['learning_updates'] == 0
    assert data['model_sha256'] == expected_hash
    assert data['protocol']['seeds'] == expected_seeds
    assert [e['seed'] for e in episodes] == expected_seeds
    assert not data['protocol']['deterministic']
    rows_verified = 0
    for episode in episodes:
        with (path.parent/episode['trace_csv']).open() as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == episode['decisions'] == episode['trace_rows']
        assert [int(r['decision']) for r in rows] == list(range(1,len(rows)+1))
        assert math.isclose(sum(float(r['native_reward']) for r in rows), episode['native_reward'], abs_tol=1e-8)
        assert int(rows[-1]['max_x']) == episode['max_x']
        assert int(rows[-1]['raw_frames']) == episode['raw_frames']
        assert bool(int(rows[-1]['flag_get'])) == episode['completed']
        assert bool(int(rows[-1]['terminated'])) == episode['terminated']
        assert bool(int(rows[-1]['truncated'])) == episode['truncated']
        counts = Counter(int(r['action']) for r in rows)
        assert [counts[i] for i in range(5)] == episode['action_counts']
        for media in episode['media'].values():
            assert (path.parent/(media if isinstance(media,str) else media['path'])).is_file()
        rows_verified += len(rows)
    assert sum(e['completed'] for e in episodes) == data['level_completions']
    assert math.isclose(data['completion_rate'], data['level_completions']/len(episodes))
    assert math.isclose(data['mean_max_x'],sum(e['max_x'] for e in episodes)/len(episodes))
    assert math.isclose(data['mean_native_reward'],sum(e['native_reward'] for e in episodes)/len(episodes))
    return data, rows_verified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent
    manifest_path = (repo/args.manifest).resolve()
    assert manifest_path.is_relative_to(repo/'results')
    manifest = read(manifest_path)
    run = manifest_path.parent
    plan = read(run/'experiment_plan.json')
    baseline = repo/plan['initial_checkpoint']
    assert digest(baseline) == plan['initial_checkpoint_sha256']
    validation = plan['validation_seeds']
    holdout = plan['holdout_seeds']
    assert len(validation) == len(set(validation)) == 20
    assert len(holdout) == len(set(holdout)) == 100
    assert not set(validation)&set(holdout)
    stage_data = []
    total_rows = 0
    for stage in manifest['stages']:
        model_hash = digest(repo/stage['checkpoint_path'])
        expected = stage.get('checkpoint_sha256',manifest['initial_checkpoint_sha256'])
        assert model_hash == expected
        data, rows = verify_evaluation(repo,repo/stage['evaluation_path'],validation,expected)
        total_rows += rows
        stage_data.append((stage,data))
    content = ['# Does another hour help Mario?', '',
        f'**Status: {manifest["status"]}.** This experiment continues the saved model that completed 42/50 stochastic attempts in the earlier reliability check.', '',
        '[Permanent classroom gallery](../../docs/aula/README.md) · [Playback and failure diagnosis](diagnostics/README.md) · [Predeclared plan](experiment_plan.json) · [All stages and clips](INFORME.md)', '',
        '[Original training history](../teaching_20260916/INFORME.md) · [Earlier 50-attempt evaluation](../reliability_20260920/README.md)', '',
        '## The question', '',
        'Does up to one additional hour of the same training improve completion on World 1-1? The original model stays available as a baseline. The reward, learning rate, entropy coefficient, observation format, and action set are preserved.', '',
        'Four 15-minute training stages are planned. Evaluation, recording, and upload time are additional. Every stage is retained, including regressions. Loading each stage resumes weights and optimizer state but does not exactly restore simulator state, partial rollouts, or random-number-generator state.', '',
        '## What each stage shows', '',
        'These 20 fixed validation seeds are reused to compare stages and select one candidate. They are not the final test. Full gameplay is preselected for three seeds at every stage.', '',
        '| Stage | Added training | Flag reached | Mean furthest x | Change from previous stage |',
        '| --- | ---: | ---: | ---: | --- |']
    previous = None
    for stage,data in stage_data:
        count = data['level_completions']
        change = 'Baseline' if previous is None else f'{count-previous:+d} completions on the same 20 seeds'
        content.append(f'| {stage["id"]} | {stage["elapsed_training_seconds"]/60:.1f} min | {count}/20 | {data["mean_max_x"]:,.1f} | {change} |')
        previous = count
    if not stage_data:
        content.append('| Baseline evaluation pending | 0 | Pending | Pending | Pending |')
    content += ['', 'Small differences on reused validation seeds can be noisy or specific to those seeds. They are not independent proof of improvement.', '',
        '## Selecting the candidate before the final test', '',
        'The candidate is chosen from the four new stages by validation completion count, then mean furthest x, then mean native reward. Exact ties prefer the earlier stage. The original baseline is always retained. The selection and checkpoint hash are saved before either final test is run.', '']
    selection_path = run/'selection.json'
    if selection_path.exists():
        content += ['[Recorded candidate selection](selection.json)', '']
        selected = manifest.get('selected_checkpoint')
        if selected:
            content += [f'Selected checkpoint: `{selected}`.', '']
    else:
        content += ['Candidate selection is pending; final test results have not been used to choose a model.', '']
    paths = [manifest.get('baseline_audit_path'),manifest.get('candidate_audit_path')]
    if all(paths):
        selected = repo/manifest['selected_checkpoint']
        selected_hash = digest(selected)
        assert selected_hash == manifest['selected_checkpoint_sha256']
        base, rows = verify_evaluation(repo,repo/paths[0],holdout,plan['initial_checkpoint_sha256'])
        total_rows += rows
        candidate, rows = verify_evaluation(repo,repo/paths[1],holdout,selected_hash)
        total_rows += rows
        assert base['protocol'] == candidate['protocol']
        selection = read(selection_path)
        assert digest(selection_path) == manifest['selection_sha256']
        assert selection['selected_checkpoint'] == manifest['selected_checkpoint']
        assert selection['selected_checkpoint_sha256'] == selected_hash
        assert selection['selected_stage_id'] == manifest['selected_stage_id']
        assert selection['validation_seeds'] == validation
        assert selection['holdout_seeds'] == holdout
        assert selection['holdouts_evaluated_at_selection'] is False
        # The file itself is written before running either held-out evaluation.
        selected_at = selection.get('selected_at') or selection.get('created_at')
        assert selected_at is not None
        assert datetime.fromisoformat(selected_at) < datetime.fromisoformat(base['started_at'])
        assert datetime.fromisoformat(selected_at) < datetime.fromisoformat(candidate['started_at'])
        counts = {'both_completed':0,'baseline_only':0,'candidate_only':0,'neither_completed':0}
        for a,b in zip(base['episodes'],candidate['episodes']):
            key = 'both_completed' if a['completed'] and b['completed'] else 'baseline_only' if a['completed'] else 'candidate_only' if b['completed'] else 'neither_completed'
            counts[key] += 1
        discordant = counts['baseline_only'] + counts['candidate_only']
        tail = min(counts['baseline_only'],counts['candidate_only'])
        pvalue = min(1.0, 2*sum(math.comb(discordant,i) for i in range(tail+1))/2**discordant) if discordant else 1.0
        difference = candidate['level_completions']-base['level_completions']
        verification = {'verified_at':datetime.now(timezone.utc).isoformat(),'validation_csv_rows_plus_final_test_rows_verified':total_rows,'baseline_checkpoint_unchanged':True,'learning_updates_during_evaluation':0,'final_test_seeds':holdout,'candidate_selected_before_holdouts':True,'matched_protocols':True,'baseline_completed':base['level_completions'],'candidate_completed':candidate['level_completions'],'observed_difference_percentage_points':difference,'paired_outcomes':counts,'exact_two_sided_mcnemar_p':pvalue,'baseline_wilson95':wilson(base['level_completions'],100),'candidate_wilson95':wilson(candidate['level_completions'],100)}
        save(run/'verification.json',verification)
        content += ['## Final comparison: 100 fresh attempts per model', '',
            'Both frozen models use the same 100 new action-sampling seeds and the same evaluation settings. These seeds were reserved until after selection. These are still attempts on the same level and start state, not 100 different levels. The earlier 42/50 batch is not pooled into this comparison.', '',
            '| Model | Completions | Approximate 95% Wilson interval | Mean furthest x |', '| --- | ---: | ---: | ---: |']
        for label,data in [('Original baseline',base),('Selected continuation',candidate)]:
            low,high = wilson(data['level_completions'],100)
            content.append(f'| {label} | {data["level_completions"]}/100 | {low:.1%}–{high:.1%} | {data["mean_max_x"]:,.1f} |')
        content += ['', f'Observed change: **{difference:+d} percentage points**. On the paired seeds, the candidate alone completed {counts["candidate_only"]} times, the baseline alone completed {counts["baseline_only"]}, both completed {counts["both_completed"]}, and neither completed {counts["neither_completed"]}.', '',
            f'Exact two-sided McNemar test on discordant seed pairs: **p = {pvalue:.4f}**. This is a within-level comparison of these two checkpoints under action sampling; it does not establish generalization or the average effect across independent training runs.', '']
        if difference > 0 and pvalue < .05:
            interpretation = 'The selected continuation completed more attempts, with evidence of a difference in this paired within-level test. Keep both models and demonstrate the remaining failures; performance on other levels has not been established.'
        elif difference > 0:
            interpretation = 'The selected continuation completed more attempts in this sample, but this test does not give strong evidence of a difference. Retain the original baseline and describe the observed gain cautiously.'
        elif difference == 0:
            interpretation = 'The two models completed the same number of attempts. This experiment does not show a completion-rate gain from the additional training. The failure patterns may still differ.'
        elif pvalue < .05:
            interpretation = 'The selected continuation completed fewer attempts, with evidence of a decline in this paired within-level test. Preserve the original baseline as the preferred classroom model; more training did not guarantee a better result.'
        else:
            interpretation = 'The selected continuation completed fewer attempts in this sample, but the paired test does not give strong evidence of an underlying decline. Retain the original baseline and describe this as an observed lower score, not a proven regression.'
        content += [interpretation, '', '[Verification and paired statistics](verification.json)', '',
            '## Matched gameplay samples', '',
            'These four seeds were chosen before the final test. Each link opens a full recorded episode; the same seeds are shown for both models.', '',
            '| Seed | Baseline | Selected continuation |', '| ---: | --- | --- |']
        for seed in plan['holdout_video_seeds']:
            row=[]
            for data,path in [(base,paths[0]),(candidate,paths[1])]:
                ep=next(e for e in data['episodes'] if e['seed']==seed)
                media=ep['media']['beginning']
                assert media['is_full_episode'] and media['last_decision']==ep['decisions']
                rel=(repo/path).parent.relative_to(run)/media['path']
                label='Completed' if ep['completed'] else 'Flag not reached'
                row.append(f'[{label}: full clip]({rel.as_posix()})')
            content.append(f'| {seed} | {row[0]} | {row[1]} |')
        content += ['', '## All paired final-test outcomes', '', '| Seed | Baseline flag | Candidate flag | Baseline x | Candidate x |', '| ---: | --- | --- | ---: | ---: |']
        for a,b in zip(base['episodes'],candidate['episodes']):
            content.append(f'| {a["seed"]} | {"Yes" if a["completed"] else "No"} | {"Yes" if b["completed"] else "No"} | {a["max_x"]} | {b["max_x"]} |')
        for label,path in [('Baseline final-test data',paths[0]),('Candidate final-test data',paths[1])]:
            rel=(repo/path).relative_to(run)
            content += ['',f'[{label}]({rel.as_posix()})']
    else:
        content += ['## Final comparison', '', 'Pending. The final comparison requires all 100 planned attempts for each model. Partial or missing outcomes are not presented as a completed result.', '']
    content += ['', '## Questions for the class', '',
        '- Did the highest-probability playback setting solve the problem? Why might sampling sometimes help?',
        '- Which mistakes recur, and which explanations are supported by the video?',
        '- Did every 15-minute stage improve? What does a regression teach us?',
        '- Why are validation attempts separate from the final test?',
        '- What would we need to test before claiming Mario can handle other levels?', '']
    if manifest.get('model_release_url'):
        content += [f'[Download the saved checkpoints]({manifest["model_release_url"]})', '']
    temporary=run/'README.md.tmp'; temporary.write_text('\n'.join(content)); temporary.replace(run/'README.md')
    print(json.dumps({'report':str(run/'README.md'),'verified_stages':len(stage_data),'final_comparison_complete':bool(all(paths))}))


if __name__=='__main__':
    main()
