# Does another hour help Mario?

**Status: completed.** This experiment continues the saved model that completed 42/50 stochastic attempts in the earlier reliability check.

[Permanent classroom gallery](../../docs/aula/README.md) · [Playback and failure diagnosis](diagnostics/README.md) · [Predeclared plan](experiment_plan.json) · [All stages and clips](INFORME.md)

[Original training history](../teaching_20260916/INFORME.md) · [Earlier 50-attempt evaluation](../reliability_20260920/README.md)

## The question

Does up to one additional hour of the same training improve completion on World 1-1? The original model stays available as a baseline. The reward, learning rate, entropy coefficient, observation format, and action set are preserved.

Four 15-minute training stages are planned. Evaluation, recording, and upload time are additional. Every stage is retained, including regressions. Loading each stage resumes weights and optimizer state but does not exactly restore simulator state, partial rollouts, or random-number-generator state.

## What each stage shows

These 20 fixed validation seeds are reused to compare stages and select one candidate. They are not the final test. Full gameplay is preselected for three seeds at every stage.

| Stage | Added training | Flag reached | Mean furthest x | Change from previous stage |
| --- | ---: | ---: | ---: | --- |
| 00_baseline | 0.0 min | 17/20 | 2,956.3 | Baseline |
| 01_stage | 15.0 min | 18/20 | 3,039.9 | +1 completions on the same 20 seeds |
| 02_stage | 30.0 min | 18/20 | 3,025.4 | +0 completions on the same 20 seeds |
| 03_stage | 45.0 min | 19/20 | 3,059.3 | +1 completions on the same 20 seeds |
| 04_stage | 60.1 min | 18/20 | 3,039.1 | -1 completions on the same 20 seeds |

Small differences on reused validation seeds can be noisy or specific to those seeds. They are not independent proof of improvement.

## Selecting the candidate before the final test

The candidate is chosen from the four new stages by validation completion count, then mean furthest x, then mean native reward. Exact ties prefer the earlier stage. The original baseline is always retained. The selection and checkpoint hash are saved before either final test is run.

[Recorded candidate selection](selection.json)

Selected checkpoint: `results/teaching_20260920/training/03_stage/checkpoints/final.zip`.

## Final comparison: 100 fresh attempts per model

Both frozen models use the same 100 new action-sampling seeds and the same evaluation settings. These seeds were reserved until after selection. These are still attempts on the same level and start state, not 100 different levels. The earlier 42/50 batch is not pooled into this comparison.

| Model | Completions | Approximate 95% Wilson interval | Mean furthest x |
| --- | ---: | ---: | ---: |
| Original baseline | 84/100 | 75.6%–89.9% | 2,918.6 |
| Selected continuation | 100/100 | 96.3%–100.0% | 3,161.0 |

Observed change: **+16 percentage points**. On the paired seeds, the candidate alone completed 16 times, the baseline alone completed 0, both completed 84, and neither completed 0.

Exact two-sided McNemar test on discordant seed pairs: **p = 0.0000**. This is a within-level comparison of these two checkpoints under action sampling; it does not establish generalization or the average effect across independent training runs.

The selected continuation completed more attempts, with evidence of a difference in this paired within-level test. Keep both models and demonstrate the remaining failures; performance on other levels has not been established.

[Verification and paired statistics](verification.json)

## Matched gameplay samples

These four seeds were chosen before the final test. Each link opens a full recorded episode; the same seeds are shown for both models.

| Seed | Baseline | Selected continuation |
| ---: | --- | --- |
| 4001 | [Flag not reached: full clip](baseline_audit/seed-4001/beginning.gif) | [Completed: full clip](candidate_audit/seed-4001/beginning.gif) |
| 4026 | [Flag not reached: full clip](baseline_audit/seed-4026/beginning.gif) | [Completed: full clip](candidate_audit/seed-4026/beginning.gif) |
| 4051 | [Completed: full clip](baseline_audit/seed-4051/beginning.gif) | [Completed: full clip](candidate_audit/seed-4051/beginning.gif) |
| 4076 | [Completed: full clip](baseline_audit/seed-4076/beginning.gif) | [Completed: full clip](candidate_audit/seed-4076/beginning.gif) |

## All paired final-test outcomes

| Seed | Baseline flag | Candidate flag | Baseline x | Candidate x |
| ---: | --- | --- | ---: | ---: |
| 4001 | No | Yes | 1790 | 3161 |
| 4002 | Yes | Yes | 3161 | 3161 |
| 4003 | Yes | Yes | 3161 | 3161 |
| 4004 | Yes | Yes | 3161 | 3161 |
| 4005 | Yes | Yes | 3161 | 3161 |
| 4006 | Yes | Yes | 3161 | 3161 |
| 4007 | Yes | Yes | 3161 | 3161 |
| 4008 | Yes | Yes | 3161 | 3161 |
| 4009 | Yes | Yes | 3161 | 3161 |
| 4010 | No | Yes | 1791 | 3161 |
| 4011 | Yes | Yes | 3161 | 3161 |
| 4012 | No | Yes | 1795 | 3161 |
| 4013 | No | Yes | 662 | 3161 |
| 4014 | Yes | Yes | 3161 | 3161 |
| 4015 | Yes | Yes | 3161 | 3161 |
| 4016 | Yes | Yes | 3161 | 3161 |
| 4017 | Yes | Yes | 3161 | 3161 |
| 4018 | Yes | Yes | 3161 | 3161 |
| 4019 | Yes | Yes | 3161 | 3161 |
| 4020 | Yes | Yes | 3161 | 3161 |
| 4021 | Yes | Yes | 3161 | 3161 |
| 4022 | Yes | Yes | 3161 | 3161 |
| 4023 | Yes | Yes | 3161 | 3161 |
| 4024 | No | Yes | 2763 | 3161 |
| 4025 | Yes | Yes | 3161 | 3161 |
| 4026 | No | Yes | 1794 | 3161 |
| 4027 | Yes | Yes | 3161 | 3161 |
| 4028 | Yes | Yes | 3161 | 3161 |
| 4029 | Yes | Yes | 3161 | 3161 |
| 4030 | Yes | Yes | 3161 | 3161 |
| 4031 | Yes | Yes | 3161 | 3161 |
| 4032 | Yes | Yes | 3161 | 3161 |
| 4033 | Yes | Yes | 3161 | 3161 |
| 4034 | Yes | Yes | 3161 | 3161 |
| 4035 | Yes | Yes | 3161 | 3161 |
| 4036 | Yes | Yes | 3161 | 3161 |
| 4037 | Yes | Yes | 3161 | 3161 |
| 4038 | No | Yes | 2763 | 3161 |
| 4039 | No | Yes | 2757 | 3161 |
| 4040 | No | Yes | 1128 | 3161 |
| 4041 | No | Yes | 1785 | 3161 |
| 4042 | Yes | Yes | 3161 | 3161 |
| 4043 | Yes | Yes | 3161 | 3161 |
| 4044 | Yes | Yes | 3161 | 3161 |
| 4045 | Yes | Yes | 3161 | 3161 |
| 4046 | Yes | Yes | 3161 | 3161 |
| 4047 | Yes | Yes | 3161 | 3161 |
| 4048 | Yes | Yes | 3161 | 3161 |
| 4049 | Yes | Yes | 3161 | 3161 |
| 4050 | Yes | Yes | 3161 | 3161 |
| 4051 | Yes | Yes | 3161 | 3161 |
| 4052 | Yes | Yes | 3161 | 3161 |
| 4053 | Yes | Yes | 3161 | 3161 |
| 4054 | Yes | Yes | 3161 | 3161 |
| 4055 | Yes | Yes | 3161 | 3161 |
| 4056 | Yes | Yes | 3161 | 3161 |
| 4057 | Yes | Yes | 3161 | 3161 |
| 4058 | No | Yes | 315 | 3161 |
| 4059 | Yes | Yes | 3161 | 3161 |
| 4060 | Yes | Yes | 3161 | 3161 |
| 4061 | Yes | Yes | 3161 | 3161 |
| 4062 | Yes | Yes | 3161 | 3161 |
| 4063 | Yes | Yes | 3161 | 3161 |
| 4064 | Yes | Yes | 3161 | 3161 |
| 4065 | Yes | Yes | 3161 | 3161 |
| 4066 | No | Yes | 315 | 3161 |
| 4067 | Yes | Yes | 3161 | 3161 |
| 4068 | Yes | Yes | 3161 | 3161 |
| 4069 | No | Yes | 1796 | 3161 |
| 4070 | No | Yes | 2763 | 3161 |
| 4071 | Yes | Yes | 3161 | 3161 |
| 4072 | Yes | Yes | 3161 | 3161 |
| 4073 | Yes | Yes | 3161 | 3161 |
| 4074 | Yes | Yes | 3161 | 3161 |
| 4075 | Yes | Yes | 3161 | 3161 |
| 4076 | Yes | Yes | 3161 | 3161 |
| 4077 | Yes | Yes | 3161 | 3161 |
| 4078 | Yes | Yes | 3161 | 3161 |
| 4079 | Yes | Yes | 3161 | 3161 |
| 4080 | Yes | Yes | 3161 | 3161 |
| 4081 | Yes | Yes | 3161 | 3161 |
| 4082 | Yes | Yes | 3161 | 3161 |
| 4083 | Yes | Yes | 3161 | 3161 |
| 4084 | Yes | Yes | 3161 | 3161 |
| 4085 | Yes | Yes | 3161 | 3161 |
| 4086 | Yes | Yes | 3161 | 3161 |
| 4087 | Yes | Yes | 3161 | 3161 |
| 4088 | Yes | Yes | 3161 | 3161 |
| 4089 | Yes | Yes | 3161 | 3161 |
| 4090 | Yes | Yes | 3161 | 3161 |
| 4091 | Yes | Yes | 3161 | 3161 |
| 4092 | Yes | Yes | 3161 | 3161 |
| 4093 | Yes | Yes | 3161 | 3161 |
| 4094 | Yes | Yes | 3161 | 3161 |
| 4095 | Yes | Yes | 3161 | 3161 |
| 4096 | No | Yes | 315 | 3161 |
| 4097 | No | Yes | 1804 | 3161 |
| 4098 | Yes | Yes | 3161 | 3161 |
| 4099 | Yes | Yes | 3161 | 3161 |
| 4100 | Yes | Yes | 3161 | 3161 |

[Baseline final-test data](baseline_audit/evaluation.json)

[Candidate final-test data](candidate_audit/evaluation.json)

## Questions for the class

- Did the highest-probability playback setting solve the problem? Why might sampling sometimes help?
- Which mistakes recur, and which explanations are supported by the video?
- Did every 15-minute stage improve? What does a regression teach us?
- Why are validation attempts separate from the final test?
- What would we need to test before claiming Mario can handle other levels?
