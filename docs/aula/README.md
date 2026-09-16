# Mario Learns: A Classroom Lab

Compare how a reinforcement learning policy changes across saved stages. This dashboard brings together measurements, observable errors, and clips from the same level; results may improve or worsen.

**Session:** `teaching_20260916` · **Status:** completed · **Updated:** 2026-09-16 14:57 UTC.

[Teacher guide: a 35–45 minute lesson](GUIA_DOCENTE.md) · [Session data and configuration](../../results/teaching_20260916/manifest.json) · [Project and previous experiments](../../README.md)

This dashboard keeps the same path, `docs/aula/README.md`, when new sessions are published. Previous reports remain in their results folders. GitHub shows the most recently uploaded version; it does not stream local training live. Access depends on repository permissions.

## Using this in class

1. Watch the first stage and write down a prediction.
2. Compare the same seed at another stage: first the beginning, then the ending.
3. Check your visual impression against all five trials, the maximum position, and whether the flag was reached.
4. Describe an observable error and a hypothesis; look for evidence that distinguishes observation from explanation.

## What has happened so far

Between the first and last comparable stages, the mean maximum position **increased: 649.6 → 3,161.0 pixels**. The last stage reached the flag in **5 of 5 trials**. This describes these trials on the same level; it does not establish general performance or consistent improvement.

![Progress chart for all comparable stages](../../results/teaching_20260916/progress.png)

The horizontal axis measures **additional training during this session**. The decisions in the table are cumulative and may include earlier training. The band shows the minimum and maximum across trials; it is not a confidence interval. The x position is a coordinate within the level, not a completion percentage.

| Stage | Additional minutes | Cumulative decisions | Mean x | Median x | Min.–max. x | Flag |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Start: model with 102,400 prior decisions | 0.0 | 102,400 | 649.6 | 688.0 | 300–1,127 | 0/5 |
| Stage 1: 15 additional min | 15.0 | 262,500 | 893.4 | 686.0 | 310–1,663 | 0/5 |
| Stage 2: 30 additional min | 30.0 | 414,928 | 1,372.2 | 1,149.0 | 1,126–2,021 | 0/5 |
| Stage 3: 45 additional min | 45.0 | 570,580 | 996.6 | 1,129.0 | 314–1,429 | 0/5 |
| Stage 4: 60 additional min | 60.0 | 731,768 | 1,558.4 | 1,527.0 | 1,128–2,028 | 0/5 |
| Stage 5: 75 additional min | 75.0 | 897,056 | 1,034.2 | 699.0 | 314–1,801 | 0/5 |
| Stage 6: 90 additional min | 90.0 | 1,060,900 | 1,663.8 | 1,526.0 | 680–3,161 | 1/5 |
| Stage 7: 105 additional min | 105.0 | 1,226,324 | 2,210.6 | 2,473.0 | 1,129–3,161 | 1/5 |
| Stage 8: 120 additional min | 120.0 | 1,387,392 | 2,806.4 | 2,762.0 | 2,473–3,161 | 2/5 |
| Stage 9: 135 additional min | 135.0 | 1,547,240 | 3,081.2 | 3,161.0 | 2,762–3,161 | 4/5 |
| Stage 10: 150 additional min | 150.0 | 1,708,772 | 3,161.0 | 3,161.0 | 3,161–3,161 | 5/5 |
| Stage 11: 163 additional min | 162.8 | 1,846,520 | 3,161.0 | 3,161.0 | 3,161–3,161 | 5/5 |

| Stage | Mean native reward | Runs without progress | Trials with a run |
| --- | ---: | ---: | ---: |
| Start: model with 102,400 prior decisions | 575.8 | 0 | 0/5 |
| Stage 1: 15 additional min | 812.0 | 0 | 0/5 |
| Stage 2: 30 additional min | 1,290.4 | 0 | 0/5 |
| Stage 3: 45 additional min | 916.0 | 0 | 0/5 |
| Stage 4: 60 additional min | 1,469.2 | 0 | 0/5 |
| Stage 5: 75 additional min | 956.8 | 0 | 0/5 |
| Stage 6: 90 additional min | 1,583.0 | 0 | 0/5 |
| Stage 7: 105 additional min | 2,109.6 | 1 | 1/5 |
| Stage 8: 120 additional min | 2,714.6 | 0 | 0/5 |
| Stage 9: 135 additional min | 2,999.6 | 0 | 0/5 |
| Stage 10: 150 additional min | 3,086.6 | 0 | 0/5 |
| Stage 11: 163 additional min | 3,088.0 | 0 | 0/5 |

## How performance was measured

Planned seeds: **101, 202, 303, 404, 505**. Sampling is reset for each trial; the seeds change the sampled actions in World 1-1, not the level layout. Evaluation uses frozen weights and native reward. The recorded training configuration is:

| Parameter | Value |
| --- | --- |
| Training reward multiplier | `0.01` |
| Learning rate | `0.0001` |
| Target KL threshold | `0.02` |
| Entropy coefficient | `0.01` |
| Training seed | `123` |
| Planned seconds per stage | `900` |

Evaluation mode: **stochastic (sampled actions)**. Limit per attempt: **3,000 decisions**. A run without progress is recorded after **120 decisions without increasing the previous maximum x**, as defined by the protocol. This can include jumps or movement within an area already traversed; it does not automatically detect walls or the cause of a death.

All recorded stages are shown, including regressions. Averages exclude evaluations that are incomplete or use a different protocol. Any partial attempt is documented in its JSON file. If a stage was selected for demonstration, that selection is labeled and does not replace the latest stage.

Clips are excerpts from the beginning and ending of each recorded trial; they may overlap in short episodes. Not every seed needs to have video: each row retains its trace and metrics. Exact durations and capture boundaries are recorded in `evaluation.json`.

## Stages and evidence

### Start: model with 102,400 prior decisions

Stage `00_baseline` · 0.0 additional minutes · 102,400 cumulative decisions.

[Full evaluation JSON](../../results/teaching_20260916/stages/00_baseline/evaluation.json)

| Seed | Max. x | Last x | Native reward | How the attempt ended | Runs without progress | Longest run (decisions) | Evidence |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 101 | 300 | 300 | 236.0 | ended without reaching the flag; cause unknown | 0 | 1 | [beginning](../../results/teaching_20260916/stages/00_baseline/seed-101/beginning.gif) · [ending](../../results/teaching_20260916/stages/00_baseline/seed-101/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/00_baseline/seed-101/trace.csv) · [last frame](../../results/teaching_20260916/stages/00_baseline/seed-101/last-frame.png) |
| 202 | 688 | 688 | 620.0 | ended without reaching the flag; cause unknown | 0 | 10 | [beginning](../../results/teaching_20260916/stages/00_baseline/seed-202/beginning.gif) · [ending](../../results/teaching_20260916/stages/00_baseline/seed-202/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/00_baseline/seed-202/trace.csv) · [last frame](../../results/teaching_20260916/stages/00_baseline/seed-202/last-frame.png) |
| 303 | 314 | 314 | 251.0 | ended without reaching the flag; cause unknown | 0 | 1 | [beginning](../../results/teaching_20260916/stages/00_baseline/seed-303/beginning.gif) · [ending](../../results/teaching_20260916/stages/00_baseline/seed-303/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/00_baseline/seed-303/trace.csv) · [last frame](../../results/teaching_20260916/stages/00_baseline/seed-303/last-frame.png) |
| 404 | 819 | 819 | 730.0 | ended without reaching the flag; cause unknown | 0 | 78 | [CSV trace](../../results/teaching_20260916/stages/00_baseline/seed-404/trace.csv) |
| 505 | 1,127 | 1,127 | 1,042.0 | ended without reaching the flag; cause unknown | 0 | 31 | [CSV trace](../../results/teaching_20260916/stages/00_baseline/seed-505/trace.csv) |

| Beginning, seed 101, decisions 1–36 | Ending, seed 101, decisions 1–36 |
| --- | --- |
| ![Beginning, seed 101, decisions 1–36](../../results/teaching_20260916/stages/00_baseline/seed-101/beginning.gif) | ![Ending, seed 101, decisions 1–36](../../results/teaching_20260916/stages/00_baseline/seed-101/ending.gif) |

**Discuss:** What can you observe at the end of this attempt? What evidence distinguishes a late jump, repeated actions, or a decision limit? Identifying the specific cause requires reviewing the clips; position alone does not reveal it.

### Stage 1: 15 additional min

Stage `01_stage` · 15.0 additional minutes · 262,500 cumulative decisions.

[Full evaluation JSON](../../results/teaching_20260916/stages/01_stage/evaluation.json) · [Training summary](../../results/teaching_20260916/training/01_stage/training_summary.json)

| Seed | Max. x | Last x | Native reward | How the attempt ended | Runs without progress | Longest run (decisions) | Evidence |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 101 | 682 | 682 | 606.0 | ended without reaching the flag; cause unknown | 0 | 22 | [beginning](../../results/teaching_20260916/stages/01_stage/seed-101/beginning.gif) · [ending](../../results/teaching_20260916/stages/01_stage/seed-101/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/01_stage/seed-101/trace.csv) · [last frame](../../results/teaching_20260916/stages/01_stage/seed-101/last-frame.png) |
| 202 | 310 | 310 | 254.0 | ended without reaching the flag; cause unknown | 0 | 1 | [beginning](../../results/teaching_20260916/stages/01_stage/seed-202/beginning.gif) · [ending](../../results/teaching_20260916/stages/01_stage/seed-202/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/01_stage/seed-202/trace.csv) · [last frame](../../results/teaching_20260916/stages/01_stage/seed-202/last-frame.png) |
| 303 | 1,663 | 1,663 | 1,556.0 | ended without reaching the flag; cause unknown | 0 | 49 | [beginning](../../results/teaching_20260916/stages/01_stage/seed-303/beginning.gif) · [ending](../../results/teaching_20260916/stages/01_stage/seed-303/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/01_stage/seed-303/trace.csv) · [last frame](../../results/teaching_20260916/stages/01_stage/seed-303/last-frame.png) |
| 404 | 686 | 686 | 613.0 | ended without reaching the flag; cause unknown | 0 | 16 | [CSV trace](../../results/teaching_20260916/stages/01_stage/seed-404/trace.csv) |
| 505 | 1,126 | 1,126 | 1,031.0 | ended without reaching the flag; cause unknown | 0 | 40 | [CSV trace](../../results/teaching_20260916/stages/01_stage/seed-505/trace.csv) |

| Beginning, seed 101, decisions 1–93 | Ending, seed 101, decisions 19–93 |
| --- | --- |
| ![Beginning, seed 101, decisions 1–93](../../results/teaching_20260916/stages/01_stage/seed-101/beginning.gif) | ![Ending, seed 101, decisions 19–93](../../results/teaching_20260916/stages/01_stage/seed-101/ending.gif) |

**Discuss:** What can you observe at the end of this attempt? What evidence distinguishes a late jump, repeated actions, or a decision limit? Identifying the specific cause requires reviewing the clips; position alone does not reveal it.

### Stage 2: 30 additional min

Stage `02_stage` · 30.0 additional minutes · 414,928 cumulative decisions.

[Full evaluation JSON](../../results/teaching_20260916/stages/02_stage/evaluation.json) · [Training summary](../../results/teaching_20260916/training/02_stage/training_summary.json)

| Seed | Max. x | Last x | Native reward | How the attempt ended | Runs without progress | Longest run (decisions) | Evidence |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 101 | 1,126 | 1,126 | 1,051.0 | ended without reaching the flag; cause unknown | 0 | 5 | [beginning](../../results/teaching_20260916/stages/02_stage/seed-101/beginning.gif) · [ending](../../results/teaching_20260916/stages/02_stage/seed-101/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/02_stage/seed-101/trace.csv) · [last frame](../../results/teaching_20260916/stages/02_stage/seed-101/last-frame.png) |
| 202 | 1,149 | 1,149 | 1,065.0 | ended without reaching the flag; cause unknown | 0 | 13 | [beginning](../../results/teaching_20260916/stages/02_stage/seed-202/beginning.gif) · [ending](../../results/teaching_20260916/stages/02_stage/seed-202/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/02_stage/seed-202/trace.csv) · [last frame](../../results/teaching_20260916/stages/02_stage/seed-202/last-frame.png) |
| 303 | 1,129 | 1,129 | 1,051.0 | ended without reaching the flag; cause unknown | 0 | 16 | [beginning](../../results/teaching_20260916/stages/02_stage/seed-303/beginning.gif) · [ending](../../results/teaching_20260916/stages/02_stage/seed-303/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/02_stage/seed-303/trace.csv) · [last frame](../../results/teaching_20260916/stages/02_stage/seed-303/last-frame.png) |
| 404 | 2,021 | 2,021 | 1,943.0 | ended without reaching the flag; cause unknown | 0 | 5 | [CSV trace](../../results/teaching_20260916/stages/02_stage/seed-404/trace.csv) |
| 505 | 1,436 | 1,436 | 1,342.0 | ended without reaching the flag; cause unknown | 0 | 20 | [CSV trace](../../results/teaching_20260916/stages/02_stage/seed-505/trace.csv) |

| Beginning, seed 101, decisions 1–148 | Ending, seed 101, decisions 74–148 |
| --- | --- |
| ![Beginning, seed 101, decisions 1–148](../../results/teaching_20260916/stages/02_stage/seed-101/beginning.gif) | ![Ending, seed 101, decisions 74–148](../../results/teaching_20260916/stages/02_stage/seed-101/ending.gif) |

**Discuss:** What can you observe at the end of this attempt? What evidence distinguishes a late jump, repeated actions, or a decision limit? Identifying the specific cause requires reviewing the clips; position alone does not reveal it.

### Stage 3: 45 additional min

Stage `03_stage` · 45.0 additional minutes · 570,580 cumulative decisions.

[Full evaluation JSON](../../results/teaching_20260916/stages/03_stage/evaluation.json) · [Training summary](../../results/teaching_20260916/training/03_stage/training_summary.json)

| Seed | Max. x | Last x | Native reward | How the attempt ended | Runs without progress | Longest run (decisions) | Evidence |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 101 | 702 | 702 | 628.0 | ended without reaching the flag; cause unknown | 0 | 4 | [beginning](../../results/teaching_20260916/stages/03_stage/seed-101/beginning.gif) · [ending](../../results/teaching_20260916/stages/03_stage/seed-101/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/03_stage/seed-101/trace.csv) · [last frame](../../results/teaching_20260916/stages/03_stage/seed-101/last-frame.png) |
| 202 | 1,129 | 1,129 | 1,041.0 | ended without reaching the flag; cause unknown | 0 | 31 | [beginning](../../results/teaching_20260916/stages/03_stage/seed-202/beginning.gif) · [ending](../../results/teaching_20260916/stages/03_stage/seed-202/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/03_stage/seed-202/trace.csv) · [last frame](../../results/teaching_20260916/stages/03_stage/seed-202/last-frame.png) |
| 303 | 1,429 | 1,429 | 1,339.0 | ended without reaching the flag; cause unknown | 0 | 17 | [beginning](../../results/teaching_20260916/stages/03_stage/seed-303/beginning.gif) · [ending](../../results/teaching_20260916/stages/03_stage/seed-303/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/03_stage/seed-303/trace.csv) · [last frame](../../results/teaching_20260916/stages/03_stage/seed-303/last-frame.png) |
| 404 | 1,409 | 1,409 | 1,322.0 | ended without reaching the flag; cause unknown | 0 | 18 | [CSV trace](../../results/teaching_20260916/stages/03_stage/seed-404/trace.csv) |
| 505 | 314 | 314 | 250.0 | ended without reaching the flag; cause unknown | 0 | 1 | [CSV trace](../../results/teaching_20260916/stages/03_stage/seed-505/trace.csv) |

| Beginning, seed 101, decisions 1–86 | Ending, seed 101, decisions 12–86 |
| --- | --- |
| ![Beginning, seed 101, decisions 1–86](../../results/teaching_20260916/stages/03_stage/seed-101/beginning.gif) | ![Ending, seed 101, decisions 12–86](../../results/teaching_20260916/stages/03_stage/seed-101/ending.gif) |

**Discuss:** What can you observe at the end of this attempt? What evidence distinguishes a late jump, repeated actions, or a decision limit? Identifying the specific cause requires reviewing the clips; position alone does not reveal it.

### Stage 4: 60 additional min

Stage `04_stage` · 60.0 additional minutes · 731,768 cumulative decisions.

[Full evaluation JSON](../../results/teaching_20260916/stages/04_stage/evaluation.json) · [Training summary](../../results/teaching_20260916/training/04_stage/training_summary.json)

| Seed | Max. x | Last x | Native reward | How the attempt ended | Runs without progress | Longest run (decisions) | Evidence |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 101 | 1,128 | 1,128 | 1,049.0 | ended without reaching the flag; cause unknown | 0 | 28 | [beginning](../../results/teaching_20260916/stages/04_stage/seed-101/beginning.gif) · [ending](../../results/teaching_20260916/stages/04_stage/seed-101/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/04_stage/seed-101/trace.csv) · [last frame](../../results/teaching_20260916/stages/04_stage/seed-101/last-frame.png) |
| 202 | 1,674 | 1,674 | 1,573.0 | ended without reaching the flag; cause unknown | 0 | 31 | [beginning](../../results/teaching_20260916/stages/04_stage/seed-202/beginning.gif) · [ending](../../results/teaching_20260916/stages/04_stage/seed-202/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/04_stage/seed-202/trace.csv) · [last frame](../../results/teaching_20260916/stages/04_stage/seed-202/last-frame.png) |
| 303 | 2,028 | 2,028 | 1,930.0 | ended without reaching the flag; cause unknown | 0 | 16 | [beginning](../../results/teaching_20260916/stages/04_stage/seed-303/beginning.gif) · [ending](../../results/teaching_20260916/stages/04_stage/seed-303/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/04_stage/seed-303/trace.csv) · [last frame](../../results/teaching_20260916/stages/04_stage/seed-303/last-frame.png) |
| 404 | 1,435 | 1,435 | 1,354.0 | ended without reaching the flag; cause unknown | 0 | 23 | [CSV trace](../../results/teaching_20260916/stages/04_stage/seed-404/trace.csv) |
| 505 | 1,527 | 1,527 | 1,440.0 | ended without reaching the flag; cause unknown | 0 | 33 | [CSV trace](../../results/teaching_20260916/stages/04_stage/seed-505/trace.csv) |

| Beginning, seed 101, decisions 1–150 | Ending, seed 101, decisions 87–161 |
| --- | --- |
| ![Beginning, seed 101, decisions 1–150](../../results/teaching_20260916/stages/04_stage/seed-101/beginning.gif) | ![Ending, seed 101, decisions 87–161](../../results/teaching_20260916/stages/04_stage/seed-101/ending.gif) |

**Discuss:** What can you observe at the end of this attempt? What evidence distinguishes a late jump, repeated actions, or a decision limit? Identifying the specific cause requires reviewing the clips; position alone does not reveal it.

### Stage 5: 75 additional min

Stage `05_stage` · 75.0 additional minutes · 897,056 cumulative decisions.

[Full evaluation JSON](../../results/teaching_20260916/stages/05_stage/evaluation.json) · [Training summary](../../results/teaching_20260916/training/05_stage/training_summary.json)

| Seed | Max. x | Last x | Native reward | How the attempt ended | Runs without progress | Longest run (decisions) | Evidence |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 101 | 699 | 699 | 636.0 | ended without reaching the flag; cause unknown | 0 | 2 | [beginning](../../results/teaching_20260916/stages/05_stage/seed-101/beginning.gif) · [ending](../../results/teaching_20260916/stages/05_stage/seed-101/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/05_stage/seed-101/trace.csv) · [last frame](../../results/teaching_20260916/stages/05_stage/seed-101/last-frame.png) |
| 202 | 1,801 | 1,801 | 1,707.0 | ended without reaching the flag; cause unknown | 0 | 15 | [beginning](../../results/teaching_20260916/stages/05_stage/seed-202/beginning.gif) · [ending](../../results/teaching_20260916/stages/05_stage/seed-202/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/05_stage/seed-202/trace.csv) · [last frame](../../results/teaching_20260916/stages/05_stage/seed-202/last-frame.png) |
| 303 | 1,669 | 1,669 | 1,572.0 | ended without reaching the flag; cause unknown | 0 | 18 | [beginning](../../results/teaching_20260916/stages/05_stage/seed-303/beginning.gif) · [ending](../../results/teaching_20260916/stages/05_stage/seed-303/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/05_stage/seed-303/trace.csv) · [last frame](../../results/teaching_20260916/stages/05_stage/seed-303/last-frame.png) |
| 404 | 688 | 688 | 618.0 | ended without reaching the flag; cause unknown | 0 | 13 | [CSV trace](../../results/teaching_20260916/stages/05_stage/seed-404/trace.csv) |
| 505 | 314 | 314 | 251.0 | ended without reaching the flag; cause unknown | 0 | 1 | [CSV trace](../../results/teaching_20260916/stages/05_stage/seed-505/trace.csv) |

| Beginning, seed 101, decisions 1–73 | Ending, seed 101, decisions 1–73 |
| --- | --- |
| ![Beginning, seed 101, decisions 1–73](../../results/teaching_20260916/stages/05_stage/seed-101/beginning.gif) | ![Ending, seed 101, decisions 1–73](../../results/teaching_20260916/stages/05_stage/seed-101/ending.gif) |

**Discuss:** What can you observe at the end of this attempt? What evidence distinguishes a late jump, repeated actions, or a decision limit? Identifying the specific cause requires reviewing the clips; position alone does not reveal it.

### Stage 6: 90 additional min

Stage `06_stage` · 90.0 additional minutes · 1,060,900 cumulative decisions.

[Full evaluation JSON](../../results/teaching_20260916/stages/06_stage/evaluation.json) · [Training summary](../../results/teaching_20260916/training/06_stage/training_summary.json)

| Seed | Max. x | Last x | Native reward | How the attempt ended | Runs without progress | Longest run (decisions) | Evidence |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 101 | 1,534 | 1,534 | 1,453.0 | ended without reaching the flag; cause unknown | 0 | 9 | [beginning](../../results/teaching_20260916/stages/06_stage/seed-101/beginning.gif) · [ending](../../results/teaching_20260916/stages/06_stage/seed-101/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/06_stage/seed-101/trace.csv) · [last frame](../../results/teaching_20260916/stages/06_stage/seed-101/last-frame.png) |
| 202 | 1,526 | 1,526 | 1,441.0 | ended without reaching the flag; cause unknown | 0 | 18 | [beginning](../../results/teaching_20260916/stages/06_stage/seed-202/beginning.gif) · [ending](../../results/teaching_20260916/stages/06_stage/seed-202/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/06_stage/seed-202/trace.csv) · [last frame](../../results/teaching_20260916/stages/06_stage/seed-202/last-frame.png) |
| 303 | 3,161 | 3,161 | 3,075.0 | flag reached | 0 | 14 | [beginning](../../results/teaching_20260916/stages/06_stage/seed-303/beginning.gif) · [ending](../../results/teaching_20260916/stages/06_stage/seed-303/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/06_stage/seed-303/trace.csv) · [last frame](../../results/teaching_20260916/stages/06_stage/seed-303/last-frame.png) |
| 404 | 680 | 680 | 610.0 | ended without reaching the flag; cause unknown | 0 | 1 | [CSV trace](../../results/teaching_20260916/stages/06_stage/seed-404/trace.csv) |
| 505 | 1,418 | 1,418 | 1,336.0 | ended without reaching the flag; cause unknown | 0 | 11 | [CSV trace](../../results/teaching_20260916/stages/06_stage/seed-505/trace.csv) |

| Beginning, seed 101, decisions 1–150 | Ending, seed 101, decisions 88–162 |
| --- | --- |
| ![Beginning, seed 101, decisions 1–150](../../results/teaching_20260916/stages/06_stage/seed-101/beginning.gif) | ![Ending, seed 101, decisions 88–162](../../results/teaching_20260916/stages/06_stage/seed-101/ending.gif) |

**Discuss:** What can you observe at the end of this attempt? What evidence distinguishes a late jump, repeated actions, or a decision limit? Identifying the specific cause requires reviewing the clips; position alone does not reveal it.

### Stage 7: 105 additional min

Stage `07_stage` · 105.0 additional minutes · 1,226,324 cumulative decisions.

[Full evaluation JSON](../../results/teaching_20260916/stages/07_stage/evaluation.json) · [Training summary](../../results/teaching_20260916/training/07_stage/training_summary.json)

| Seed | Max. x | Last x | Native reward | How the attempt ended | Runs without progress | Longest run (decisions) | Evidence |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 101 | 1,814 | 1,814 | 1,724.0 | ended without reaching the flag; cause unknown | 0 | 26 | [beginning](../../results/teaching_20260916/stages/07_stage/seed-101/beginning.gif) · [ending](../../results/teaching_20260916/stages/07_stage/seed-101/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/07_stage/seed-101/trace.csv) · [last frame](../../results/teaching_20260916/stages/07_stage/seed-101/last-frame.png) |
| 202 | 2,476 | 2,476 | 2,366.0 | ended without reaching the flag; cause unknown | 0 | 16 | [beginning](../../results/teaching_20260916/stages/07_stage/seed-202/beginning.gif) · [ending](../../results/teaching_20260916/stages/07_stage/seed-202/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/07_stage/seed-202/trace.csv) · [last frame](../../results/teaching_20260916/stages/07_stage/seed-202/last-frame.png) |
| 303 | 1,129 | 1,129 | 1,015.0 | ended without reaching the flag; cause unknown | 1 | 173 | [beginning](../../results/teaching_20260916/stages/07_stage/seed-303/beginning.gif) · [ending](../../results/teaching_20260916/stages/07_stage/seed-303/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/07_stage/seed-303/trace.csv) · [last frame](../../results/teaching_20260916/stages/07_stage/seed-303/last-frame.png) |
| 404 | 3,161 | 3,161 | 3,054.0 | flag reached | 0 | 19 | [CSV trace](../../results/teaching_20260916/stages/07_stage/seed-404/trace.csv) |
| 505 | 2,473 | 2,473 | 2,389.0 | ended without reaching the flag; cause unknown | 0 | 5 | [CSV trace](../../results/teaching_20260916/stages/07_stage/seed-505/trace.csv) |

| Beginning, seed 101, decisions 1–150 | Ending, seed 101, decisions 130–204 |
| --- | --- |
| ![Beginning, seed 101, decisions 1–150](../../results/teaching_20260916/stages/07_stage/seed-101/beginning.gif) | ![Ending, seed 101, decisions 130–204](../../results/teaching_20260916/stages/07_stage/seed-101/ending.gif) |

**Discuss:** What can you observe at the end of this attempt? What evidence distinguishes a late jump, repeated actions, or a decision limit? Identifying the specific cause requires reviewing the clips; position alone does not reveal it.

### Stage 8: 120 additional min

Stage `08_stage` · 120.0 additional minutes · 1,387,392 cumulative decisions.

[Full evaluation JSON](../../results/teaching_20260916/stages/08_stage/evaluation.json) · [Training summary](../../results/teaching_20260916/training/08_stage/training_summary.json)

| Seed | Max. x | Last x | Native reward | How the attempt ended | Runs without progress | Longest run (decisions) | Evidence |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 101 | 2,473 | 2,473 | 2,379.0 | ended without reaching the flag; cause unknown | 0 | 6 | [beginning](../../results/teaching_20260916/stages/08_stage/seed-101/beginning.gif) · [ending](../../results/teaching_20260916/stages/08_stage/seed-101/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/08_stage/seed-101/trace.csv) · [last frame](../../results/teaching_20260916/stages/08_stage/seed-101/last-frame.png) |
| 202 | 2,762 | 2,762 | 2,659.0 | ended without reaching the flag; cause unknown | 0 | 22 | [beginning](../../results/teaching_20260916/stages/08_stage/seed-202/beginning.gif) · [ending](../../results/teaching_20260916/stages/08_stage/seed-202/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/08_stage/seed-202/trace.csv) · [last frame](../../results/teaching_20260916/stages/08_stage/seed-202/last-frame.png) |
| 303 | 2,475 | 2,475 | 2,380.0 | ended without reaching the flag; cause unknown | 0 | 7 | [beginning](../../results/teaching_20260916/stages/08_stage/seed-303/beginning.gif) · [ending](../../results/teaching_20260916/stages/08_stage/seed-303/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/08_stage/seed-303/trace.csv) · [last frame](../../results/teaching_20260916/stages/08_stage/seed-303/last-frame.png) |
| 404 | 3,161 | 3,161 | 3,076.0 | flag reached | 0 | 10 | [CSV trace](../../results/teaching_20260916/stages/08_stage/seed-404/trace.csv) |
| 505 | 3,161 | 3,161 | 3,079.0 | flag reached | 0 | 5 | [CSV trace](../../results/teaching_20260916/stages/08_stage/seed-505/trace.csv) |

| Beginning, seed 101, decisions 1–150 | Ending, seed 101, decisions 168–242 |
| --- | --- |
| ![Beginning, seed 101, decisions 1–150](../../results/teaching_20260916/stages/08_stage/seed-101/beginning.gif) | ![Ending, seed 101, decisions 168–242](../../results/teaching_20260916/stages/08_stage/seed-101/ending.gif) |

**Discuss:** What can you observe at the end of this attempt? What evidence distinguishes a late jump, repeated actions, or a decision limit? Identifying the specific cause requires reviewing the clips; position alone does not reveal it.

### Stage 9: 135 additional min

Stage `09_stage` · 135.0 additional minutes · 1,547,240 cumulative decisions.

[Full evaluation JSON](../../results/teaching_20260916/stages/09_stage/evaluation.json) · [Training summary](../../results/teaching_20260916/training/09_stage/training_summary.json)

| Seed | Max. x | Last x | Native reward | How the attempt ended | Runs without progress | Longest run (decisions) | Evidence |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 101 | 3,161 | 3,161 | 3,077.0 | flag reached | 0 | 12 | [beginning](../../results/teaching_20260916/stages/09_stage/seed-101/beginning.gif) · [ending](../../results/teaching_20260916/stages/09_stage/seed-101/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/09_stage/seed-101/trace.csv) · [last frame](../../results/teaching_20260916/stages/09_stage/seed-101/last-frame.png) |
| 202 | 3,161 | 3,161 | 3,077.0 | flag reached | 0 | 19 | [beginning](../../results/teaching_20260916/stages/09_stage/seed-202/beginning.gif) · [ending](../../results/teaching_20260916/stages/09_stage/seed-202/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/09_stage/seed-202/trace.csv) · [last frame](../../results/teaching_20260916/stages/09_stage/seed-202/last-frame.png) |
| 303 | 2,762 | 2,762 | 2,675.0 | ended without reaching the flag; cause unknown | 0 | 1 | [beginning](../../results/teaching_20260916/stages/09_stage/seed-303/beginning.gif) · [ending](../../results/teaching_20260916/stages/09_stage/seed-303/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/09_stage/seed-303/trace.csv) · [last frame](../../results/teaching_20260916/stages/09_stage/seed-303/last-frame.png) |
| 404 | 3,161 | 3,161 | 3,086.0 | flag reached | 0 | 10 | [CSV trace](../../results/teaching_20260916/stages/09_stage/seed-404/trace.csv) |
| 505 | 3,161 | 3,161 | 3,083.0 | flag reached | 0 | 5 | [CSV trace](../../results/teaching_20260916/stages/09_stage/seed-505/trace.csv) |

| Beginning, seed 101, decisions 1–150 | Ending, seed 101, decisions 259–333 |
| --- | --- |
| ![Beginning, seed 101, decisions 1–150](../../results/teaching_20260916/stages/09_stage/seed-101/beginning.gif) | ![Ending, seed 101, decisions 259–333](../../results/teaching_20260916/stages/09_stage/seed-101/ending.gif) |

**Discuss:** What can you observe at the end of this attempt? What evidence distinguishes a late jump, repeated actions, or a decision limit? Identifying the specific cause requires reviewing the clips; position alone does not reveal it.

### Stage 10: 150 additional min

Stage `10_stage` · 150.0 additional minutes · 1,708,772 cumulative decisions.

[Full evaluation JSON](../../results/teaching_20260916/stages/10_stage/evaluation.json) · [Training summary](../../results/teaching_20260916/training/10_stage/training_summary.json)

| Seed | Max. x | Last x | Native reward | How the attempt ended | Runs without progress | Longest run (decisions) | Evidence |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 101 | 3,161 | 3,161 | 3,089.0 | flag reached | 0 | 10 | [beginning](../../results/teaching_20260916/stages/10_stage/seed-101/beginning.gif) · [ending](../../results/teaching_20260916/stages/10_stage/seed-101/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/10_stage/seed-101/trace.csv) · [last frame](../../results/teaching_20260916/stages/10_stage/seed-101/last-frame.png) |
| 202 | 3,161 | 3,161 | 3,089.0 | flag reached | 0 | 12 | [beginning](../../results/teaching_20260916/stages/10_stage/seed-202/beginning.gif) · [ending](../../results/teaching_20260916/stages/10_stage/seed-202/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/10_stage/seed-202/trace.csv) · [last frame](../../results/teaching_20260916/stages/10_stage/seed-202/last-frame.png) |
| 303 | 3,161 | 3,161 | 3,086.0 | flag reached | 0 | 7 | [beginning](../../results/teaching_20260916/stages/10_stage/seed-303/beginning.gif) · [ending](../../results/teaching_20260916/stages/10_stage/seed-303/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/10_stage/seed-303/trace.csv) · [last frame](../../results/teaching_20260916/stages/10_stage/seed-303/last-frame.png) |
| 404 | 3,161 | 3,161 | 3,078.0 | flag reached | 0 | 10 | [CSV trace](../../results/teaching_20260916/stages/10_stage/seed-404/trace.csv) |
| 505 | 3,161 | 3,161 | 3,091.0 | flag reached | 0 | 6 | [CSV trace](../../results/teaching_20260916/stages/10_stage/seed-505/trace.csv) |

| Beginning, seed 101, decisions 1–150 | Ending, seed 101, decisions 235–309 |
| --- | --- |
| ![Beginning, seed 101, decisions 1–150](../../results/teaching_20260916/stages/10_stage/seed-101/beginning.gif) | ![Ending, seed 101, decisions 235–309](../../results/teaching_20260916/stages/10_stage/seed-101/ending.gif) |

**Discuss:** What can you observe at the end of this attempt? What evidence distinguishes a late jump, repeated actions, or a decision limit? Identifying the specific cause requires reviewing the clips; position alone does not reveal it.

### Stage 11: 163 additional min

Stage `11_stage` · 162.8 additional minutes · 1,846,520 cumulative decisions.

[Full evaluation JSON](../../results/teaching_20260916/stages/11_stage/evaluation.json) · [Training summary](../../results/teaching_20260916/training/11_stage/training_summary.json)

| Seed | Max. x | Last x | Native reward | How the attempt ended | Runs without progress | Longest run (decisions) | Evidence |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 101 | 3,161 | 3,161 | 3,087.0 | flag reached | 0 | 7 | [beginning](../../results/teaching_20260916/stages/11_stage/seed-101/beginning.gif) · [ending](../../results/teaching_20260916/stages/11_stage/seed-101/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/11_stage/seed-101/trace.csv) · [last frame](../../results/teaching_20260916/stages/11_stage/seed-101/last-frame.png) |
| 202 | 3,161 | 3,161 | 3,087.0 | flag reached | 0 | 8 | [beginning](../../results/teaching_20260916/stages/11_stage/seed-202/beginning.gif) · [ending](../../results/teaching_20260916/stages/11_stage/seed-202/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/11_stage/seed-202/trace.csv) · [last frame](../../results/teaching_20260916/stages/11_stage/seed-202/last-frame.png) |
| 303 | 3,161 | 3,161 | 3,091.0 | flag reached | 0 | 3 | [beginning](../../results/teaching_20260916/stages/11_stage/seed-303/beginning.gif) · [ending](../../results/teaching_20260916/stages/11_stage/seed-303/ending.gif) · [CSV trace](../../results/teaching_20260916/stages/11_stage/seed-303/trace.csv) · [last frame](../../results/teaching_20260916/stages/11_stage/seed-303/last-frame.png) |
| 404 | 3,161 | 3,161 | 3,088.0 | flag reached | 0 | 9 | [CSV trace](../../results/teaching_20260916/stages/11_stage/seed-404/trace.csv) |
| 505 | 3,161 | 3,161 | 3,087.0 | flag reached | 0 | 5 | [CSV trace](../../results/teaching_20260916/stages/11_stage/seed-505/trace.csv) |

| Beginning, seed 101, decisions 1–150 | Ending, seed 101, decisions 245–319 |
| --- | --- |
| ![Beginning, seed 101, decisions 1–150](../../results/teaching_20260916/stages/11_stage/seed-101/beginning.gif) | ![Ending, seed 101, decisions 245–319](../../results/teaching_20260916/stages/11_stage/seed-101/ending.gif) |

**Discuss:** What can you observe at the end of this attempt? What evidence distinguishes a late jump, repeated actions, or a decision limit? Identifying the specific cause requires reviewing the clips; position alone does not reveal it.

## Final test with new seeds

These seeds were reserved for the final model; they are not included in the curve of five repeated trials or used to select a stage. They are still attempts on the same World 1-1 level.

[Final test data](../../results/teaching_20260916/final_audit/evaluation.json)

Mean maximum position: **2,818.6 px** · Median: **3,161.0 px** · Flag: **7/10 trials**.

| Seed | Max. x | Flag | Evidence |
| ---: | ---: | ---: | --- |
| 1001 | 3,161 | yes | [beginning](../../results/teaching_20260916/final_audit/seed-1001/beginning.gif) · [ending](../../results/teaching_20260916/final_audit/seed-1001/ending.gif) · [CSV trace](../../results/teaching_20260916/final_audit/seed-1001/trace.csv) |
| 1002 | 1,790 | no | [CSV trace](../../results/teaching_20260916/final_audit/seed-1002/trace.csv) |
| 1003 | 3,161 | yes | [CSV trace](../../results/teaching_20260916/final_audit/seed-1003/trace.csv) |
| 1004 | 3,161 | yes | [CSV trace](../../results/teaching_20260916/final_audit/seed-1004/trace.csv) |
| 1005 | 2,470 | no | [CSV trace](../../results/teaching_20260916/final_audit/seed-1005/trace.csv) |
| 1006 | 1,799 | no | [CSV trace](../../results/teaching_20260916/final_audit/seed-1006/trace.csv) |
| 1007 | 3,161 | yes | [CSV trace](../../results/teaching_20260916/final_audit/seed-1007/trace.csv) |
| 1008 | 3,161 | yes | [CSV trace](../../results/teaching_20260916/final_audit/seed-1008/trace.csv) |
| 1009 | 3,161 | yes | [CSV trace](../../results/teaching_20260916/final_audit/seed-1009/trace.csv) |
| 1010 | 3,161 | yes | [CSV trace](../../results/teaching_20260916/final_audit/seed-1010/trace.csv) |

## Saved materials and future sessions

Published checkpoints can be downloaded from the [model release for this session](https://github.com/sbardacosta-code/mario-rl/releases/tag/teaching_20260916). These files are separate from the code history and require repository access. The link is added to the manifest after the upload is confirmed; check the release for the files actually published.

The repository retains the reports, metrics, and published samples. Detailed logs remain local.

Latest recorded local checkpoint: `results/teaching_20260916/training/11_stage/checkpoints/final.zip`.

[Session report](../../results/teaching_20260916/INFORME.md) · [Teacher guide](GUIA_DOCENTE.md)

Archived sessions:

- [teaching_20260916](../../results/teaching_20260916/INFORME.md)

Recorded reason for ending the session: `session_time_budget_reached`.

To update this dashboard after generating new evaluations:

```sh
.venv/bin/python lesson_report.py --manifest results/teaching_20260916/manifest.json --repo-root .
```

The dashboard update remains local until it is committed and uploaded to GitHub. It does not run training or modify model weights.
