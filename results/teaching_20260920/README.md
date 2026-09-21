# Does another hour help Mario?

**Status: running.** This experiment continues the saved model that completed 42/50 stochastic attempts in the earlier reliability check.

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

Candidate selection is pending; final test results have not been used to choose a model.

## Final comparison

Pending. The final comparison requires all 100 planned attempts for each model. Partial or missing outcomes are not presented as a completed result.


## Questions for the class

- Did the highest-probability playback setting solve the problem? Why might sampling sometimes help?
- Which mistakes recur, and which explanations are supported by the video?
- Did every 15-minute stage improve? What does a regression teach us?
- Why are validation attempts separate from the final test?
- What would we need to test before claiming Mario can handle other levels?
