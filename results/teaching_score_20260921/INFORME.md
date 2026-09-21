# Mario Learns: A Classroom Lab

Compare how a reinforcement learning policy changes across saved stages. This dashboard brings together measurements, observable errors, and clips from the same level; results may improve or worsen.

**Session:** `teaching_score_20260921` · **Status:** in progress · **Updated:** 2026-09-21 07:57 UTC.

[Teacher guide: a 35–45 minute lesson](../../docs/aula/GUIA_DOCENTE.md) · [Session data and configuration](manifest.json) · [Project and previous experiments](../../README.md) · [Baseline and trained-model comparison](README.md)

This dashboard keeps the same path, `docs/aula/README.md`, when new sessions are published. Previous reports remain in their results folders. GitHub shows the most recently uploaded version; it does not stream local training live. Access depends on repository permissions.

## Using this in class

1. Watch the first stage and write down a prediction.
2. Compare the same seed at another stage: first the beginning, then the ending.
3. Check your visual impression against all 20 trials, the maximum position, and whether the flag was reached.
4. Describe an observable error and a hypothesis; look for evidence that distinguishes observation from explanation.

## What has happened so far

The starting point has been evaluated. Another comparable stage is needed to measure change during this session.

## Current objective: more game points while still finishing

This session rewards actual score increases, with a separate bonus for finishing and a penalty for a non-clearing episode end. Native reward is retained only as a diagnostic. The score is measured at flag touch; the emulator stops before the later flag animation and remaining-time bonuses.

| Stage | Mean points, all attempts | Mean points with failures counted as zero | Flag reached |
| --- | ---: | ---: | ---: |
| Preserved completion baseline | 770.0 | 770.0 | 20/20 |

[Score experiment, selection rule, and final comparison](README.md)

![Progress chart for all comparable stages](progress.png)

The horizontal axis measures **additional training during this session**. The decisions in the table are cumulative and may include earlier training. The band shows the minimum and maximum across trials; it is not a confidence interval. The x position is a coordinate within the level, not a completion percentage.

| Stage | Additional minutes | Cumulative decisions | Mean x | Median x | Min.–max. x | Flag |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Preserved completion baseline | 0.0 | 2,119,660 | 3,161.0 | 3,161.0 | 3,161–3,161 | 20/20 |

| Stage | Mean native reward | Runs without progress | Trials with a run |
| --- | ---: | ---: | ---: |
| Preserved completion baseline | 3,093.1 | 0 | 0/20 |

## How performance was measured

Planned seeds: **7101, 7102, 7103, 7104, 7105, 7106, 7107, 7108, 7109, 7110, 7111, 7112, 7113, 7114, 7115, 7116, 7117, 7118, 7119, 7120**. Sampling is reset for each trial; the seeds change the sampled actions in World 1-1, not the level layout. Evaluation uses frozen weights and native reward. The recorded training configuration is:

| Parameter | Value |
| --- | --- |
| Training reward multiplier | `1.0` |
| Learning rate | `0.0001` |
| Target KL threshold | `0.02` |
| Entropy coefficient | `0.01` |
| Training seed | `123` |
| Planned seconds per stage | `900` |

Evaluation mode: **stochastic (sampled actions)**. Limit per attempt: **3,000 decisions**. A run without progress is recorded after **120 decisions without increasing the previous maximum x**, as defined by the protocol. This can include jumps or movement within an area already traversed; it does not automatically detect walls or the cause of a death.

All recorded stages are shown, including regressions. Averages exclude evaluations that are incomplete or use a different protocol. Any partial attempt is documented in its JSON file. If a stage was selected for demonstration, that selection is labeled and does not replace the latest stage.

Clips can cover an entire trial or an excerpt from its beginning or ending. The capture boundaries and full-episode marker are recorded in `evaluation.json`. Not every seed needs video: each row retains its trace and metrics.

## Stages and evidence

### Preserved completion baseline

Stage `00_baseline` · 0.0 additional minutes · 2,119,660 cumulative decisions.

[Full evaluation JSON](stages/00_baseline/evaluation.json)

| Seed | Max. x | Last x | Native reward | How the attempt ended | Runs without progress | Longest run (decisions) | Evidence |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 7101 | 3,161 | 3,161 | 3,096.0 | flag reached | 0 | 1 | [beginning](stages/00_baseline/seed-7101/beginning.gif) · [ending](stages/00_baseline/seed-7101/ending.gif) · [CSV trace](stages/00_baseline/seed-7101/trace.csv) · [last frame](stages/00_baseline/seed-7101/last-frame.png) |
| 7102 | 3,161 | 3,161 | 3,093.0 | flag reached | 0 | 18 | [CSV trace](stages/00_baseline/seed-7102/trace.csv) |
| 7103 | 3,161 | 3,161 | 3,096.0 | flag reached | 0 | 1 | [CSV trace](stages/00_baseline/seed-7103/trace.csv) |
| 7104 | 3,161 | 3,161 | 3,096.0 | flag reached | 0 | 1 | [CSV trace](stages/00_baseline/seed-7104/trace.csv) |
| 7105 | 3,161 | 3,161 | 3,096.0 | flag reached | 0 | 1 | [CSV trace](stages/00_baseline/seed-7105/trace.csv) |
| 7106 | 3,161 | 3,161 | 3,095.0 | flag reached | 0 | 1 | [CSV trace](stages/00_baseline/seed-7106/trace.csv) |
| 7107 | 3,161 | 3,161 | 3,093.0 | flag reached | 0 | 2 | [CSV trace](stages/00_baseline/seed-7107/trace.csv) |
| 7108 | 3,161 | 3,161 | 3,089.0 | flag reached | 0 | 6 | [CSV trace](stages/00_baseline/seed-7108/trace.csv) |
| 7109 | 3,161 | 3,161 | 3,088.0 | flag reached | 0 | 3 | [CSV trace](stages/00_baseline/seed-7109/trace.csv) |
| 7110 | 3,161 | 3,161 | 3,088.0 | flag reached | 0 | 9 | [beginning](stages/00_baseline/seed-7110/beginning.gif) · [ending](stages/00_baseline/seed-7110/ending.gif) · [CSV trace](stages/00_baseline/seed-7110/trace.csv) · [last frame](stages/00_baseline/seed-7110/last-frame.png) |
| 7111 | 3,161 | 3,161 | 3,087.0 | flag reached | 0 | 8 | [CSV trace](stages/00_baseline/seed-7111/trace.csv) |
| 7112 | 3,161 | 3,161 | 3,089.0 | flag reached | 0 | 7 | [CSV trace](stages/00_baseline/seed-7112/trace.csv) |
| 7113 | 3,161 | 3,161 | 3,093.0 | flag reached | 0 | 18 | [CSV trace](stages/00_baseline/seed-7113/trace.csv) |
| 7114 | 3,161 | 3,161 | 3,095.0 | flag reached | 0 | 1 | [CSV trace](stages/00_baseline/seed-7114/trace.csv) |
| 7115 | 3,161 | 3,161 | 3,090.0 | flag reached | 0 | 9 | [CSV trace](stages/00_baseline/seed-7115/trace.csv) |
| 7116 | 3,161 | 3,161 | 3,096.0 | flag reached | 0 | 1 | [CSV trace](stages/00_baseline/seed-7116/trace.csv) |
| 7117 | 3,161 | 3,161 | 3,095.0 | flag reached | 0 | 1 | [CSV trace](stages/00_baseline/seed-7117/trace.csv) |
| 7118 | 3,161 | 3,161 | 3,096.0 | flag reached | 0 | 1 | [CSV trace](stages/00_baseline/seed-7118/trace.csv) |
| 7119 | 3,161 | 3,161 | 3,096.0 | flag reached | 0 | 1 | [CSV trace](stages/00_baseline/seed-7119/trace.csv) |
| 7120 | 3,161 | 3,161 | 3,095.0 | flag reached | 0 | 1 | [beginning](stages/00_baseline/seed-7120/beginning.gif) · [ending](stages/00_baseline/seed-7120/ending.gif) · [CSV trace](stages/00_baseline/seed-7120/trace.csv) · [last frame](stages/00_baseline/seed-7120/last-frame.png) |

| Beginning, seed 7101, decisions 1–268 | Ending, seed 7101, decisions 194–268 |
| --- | --- |
| ![Beginning, seed 7101, decisions 1–268](stages/00_baseline/seed-7101/beginning.gif) | ![Ending, seed 7101, decisions 194–268](stages/00_baseline/seed-7101/ending.gif) |

**Discuss:** What can you observe at the end of this attempt? What evidence distinguishes a late jump, repeated actions, or a decision limit? Identifying the specific cause requires reviewing the clips; position alone does not reveal it.

## Saved materials and future sessions

Checkpoint `.zip` files are stored locally; this manifest does not yet confirm a published release of model weights. Downloading the code from GitHub does not include those models. The manifest records their paths for anyone with that local copy.

The repository retains the reports, metrics, and published samples. Detailed logs remain local.

Latest recorded local checkpoint: `results/teaching_20260920/training/03_stage/checkpoints/final.zip`.

[Session report](INFORME.md) · [Teacher guide](../../docs/aula/GUIA_DOCENTE.md)

Archived sessions:

- [teaching_20260916](../teaching_20260916/INFORME.md)
- [teaching_20260920](../teaching_20260920/INFORME.md)
- [teaching_score_20260921](INFORME.md)

To update this dashboard after generating new evaluations:

```sh
.venv/bin/python lesson_report.py --manifest results/teaching_score_20260921/manifest.json --repo-root .
```

The dashboard update remains local until it is committed and uploaded to GitHub. It does not run training or modify model weights.
