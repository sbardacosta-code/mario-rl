# Can Mario finish with more points?

**Status: interrupted.** Training budget: 15 minutes, saved every 15 minutes.

[Permanent classroom gallery](../../docs/aula/README.md) · [Predeclared plan](experiment_plan.json) · [Stage clips and native-reward diagnostics](INFORME.md)

## What changed

The preserved starting model learned to finish World 1-1. This experiment changes its learning objective to game points while retaining a finish bonus and a failure penalty. The prior model and every new checkpoint remain available.

**Training reward per decision:** HUD score increase ÷ 1,000, plus 5 once for reaching the flag, or minus 5 when an attempt ends without the flag. There is no added progress reward, native reward, or separate coin bonus. Coins, enemies and items matter when they change the HUD score. PPO hyperparameters remain unchanged.

**Measured points:** the HUD score at the flag or episode end. The emulator stops the attempt there, so subsequent time-bonus conversion is excluded. The five RIGHT_ONLY actions cannot backtrack. This experiment searches for a higher score within these limits; it does not establish the maximum possible game score.

## Live training window

Current phase: **interrupted**. The window shows frames from one of four actual training environments. It is an observer: closing it leaves training running. During evaluation it shows the last training frame with the phase; after completion it becomes an archived view.

Open it locally with `.venv/bin/python watch_training.py results/teaching_score_20260921`. A GitHub page contains recordings, not the live desktop window.

## Every 15-minute stage

Twenty fixed validation action seeds are reused at every stage. They measure the same level and starting state with different sampled actions, not different levels. These results select the candidate and are kept separate from the final test. Failed attempts contribute zero to **mean completed score** (earned points = final HUD minus starting HUD); ordinary mean points includes failures and uses raw HUD values. Mean on clears also uses earned points.

| Stage | Training | Clears | Mean HUD points | Mean earned on clears | Mean completed score | Median / maximum HUD | Change from previous |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 00_baseline | 0.0 min | 20/20 | 770.0 | 770.0 | 770.0 | 800.0 / 800.0 | Preserved baseline |
| 01_stage | 15.0 min | 0/20 | 175.0 | — | 0.0 | 200.0 / 700.0 | -20 clears; -770.0 completed points |

Lower completion or completed points is a regression in this validation sample. Higher ordinary points with fewer finishes can indicate a tradeoff. Videos show behavior; numerical changes alone do not identify a particular trick or failure cause.

### Evidence from each stage

Three full clips were preselected before training. Review the same seeds across stages, including regressions.

| Stage | Seed | Flag | Points | Evidence |
| --- | ---: | --- | ---: | --- |
| 00_baseline | 7101 | Yes | 800 | [Full clip](stages/00_baseline/seed-7101/beginning.gif) · [Decision trace](stages/00_baseline/seed-7101/trace.csv) |
| 00_baseline | 7110 | Yes | 700 | [Full clip](stages/00_baseline/seed-7110/beginning.gif) · [Decision trace](stages/00_baseline/seed-7110/trace.csv) |
| 00_baseline | 7120 | Yes | 700 | [Full clip](stages/00_baseline/seed-7120/beginning.gif) · [Decision trace](stages/00_baseline/seed-7120/trace.csv) |
| 01_stage | 7101 | No | 200 | [Full clip](stages/01_stage/seed-7101/beginning.gif) · [Decision trace](stages/01_stage/seed-7101/trace.csv) |
| 01_stage | 7110 | No | 200 | [Full clip](stages/01_stage/seed-7110/beginning.gif) · [Decision trace](stages/01_stage/seed-7110/trace.csv) |
| 01_stage | 7120 | No | 100 | [Full clip](stages/01_stage/seed-7120/beginning.gif) · [Decision trace](stages/01_stage/seed-7120/trace.csv) |


[01_stage verified learning updates](training/01_stage/training_summary.json) · [Learning metrics](training/01_stage/learning_metrics.csv)


## Selecting the candidate before the final test

Among new stages with at least 19/20 validation clears, choose greatest mean completed score (failed attempts count zero), then clear count, then mean score gain, then earliest stage. If none qualifies, choose most clears, then mean completed score, then mean score gain, then earliest stage as a diagnostic candidate only. Save this choice before either final test; preserve the baseline.

Selected **01_stage**: diagnostic only; no new stage met 19/20 clears. [Frozen choice and ranking](selection.json).

## Paired final test

Pending. Both models must complete all 100 reserved attempts before any final comparison or replacement recommendation is published. Missing or partial results are not zeros.

## Classroom questions

- Can Mario collect more points while becoming less reliable at finishing?
- Which behavior changes can we actually see in the matched clips?
- Did each additional 15 minutes improve the same metric?
- Why keep failed attempts in the denominator and reserve a final test?
- How would backtracking, later time bonuses, or another level change the experiment?

[Download every saved model](https://github.com/sbardacosta-code/mario-rl/releases/tag/teaching_score_20260921)
