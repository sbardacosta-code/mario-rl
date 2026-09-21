# Mario's overnight score experiment

**Status: running.** Overall deadline: **2026-09-21T14:08:00+00:00**. This is a maximum wall-clock budget, including setup, evaluation and publication—not six hours of optimizer updates.

[Permanent classroom page](../../docs/aula/README.md) · [Frozen plan](experiment_plan.json) · [All saved stage clips](INFORME.md)

## What Mario is trying to learn

Game points and finishing remain separate measurements. The event-aware environment records the actual HUD increase, waits for the real flagpole award before stopping, and excludes later timer conversion. A separate teaching bonus of **1,000 custom points per verified extra life** makes 1UPs valuable even when the HUD does not change. Custom points are not Nintendo game points.

**Augmented points = actual HUD points earned + custom 1UP points.** The real flagpole award is already inside actual HUD points and is never added again. Flag height and the observed flag award are also recorded separately. Extra-life count alone does not establish which object caused it; see the event evidence.

Two initial 15-minute trials start independently from the same preserved completion model: sparse event reward and a gentle bridge from the existing reward. Both use learning rate 0.000025, target KL 0.01 and entropy 0.003. Later decisions follow the plan's validation and rollback rules. Different objectives and settings change together, so this is not a controlled attribution to one parameter.

The bridge mixes 0.01 × native reward and event reward with the declared weight. Its weight starts at 0.25 and rises only after two qualifying improvements at that weight. A confirmed regression returns to the best checkpoint, then permits one conservative retry at learning rate 0.00001. Repeated failure ends that path or uses a previously successful configuration. Training can stop early; spending the entire allowance is not itself a goal.

The current working checkpoint and protected best checkpoint are separate. Qualified stages without confirmed regressions continue learning even when validation ties the previous best. An unqualified or partial stage rolls back to the protected best. This avoids restarting the same 15 minutes of learning on every plateau.

## Every stage, including regressions

The same 20 validation action seeds are reused for model selection. A new stage needs at least 19/20 clears to qualify. Completed-score means keep all attempts in the denominator and assign failed attempts zero. Seeds vary stochastic moves on World 1-1, not terrain.

| Stage | Minutes learned | Objective / weight / LR | Clears | Mean HUD gain | Completed HUD | Custom 1UP mean | Completed augmented points | Decision |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 00_baseline | 0.0 | Preserved baseline | 20/20 | 1,125.0 | 1,125.0 | 0.0 | 1,125.0 | Baseline |
| 01_stage | 5.0 | score_events / 1.0 / 2.5e-05 | 0/20 | 130.0 | 0.0 | 0.0 | 0.0 | Confirmed regression; resume best checkpoint |
| 02_stage | 20.0 | score_bridge / 0.25 / 2.5e-05 | 20/20 | 5,275.0 | 5,275.0 | 0.0 | 5,275.0 | Qualified improvement |
| 03_stage | 35.0 | score_bridge / 0.25 / 2.5e-05 | 20/20 | 5,580.0 | 5,580.0 | 0.0 | 5,580.0 | Qualified improvement |
| 04_stage | 50.0 | score_bridge / 0.5 / 2.5e-05 | 19/20 | 4,840.0 | 4,830.0 | 0.0 | 4,830.0 | Confirmed regression; resume best checkpoint |
| 05_stage | 65.0 | score_bridge / 0.5 / 1e-05 | 19/20 | 5,280.0 | 5,270.0 | 0.0 | 5,270.0 | Confirmed regression; resume best checkpoint |

### Preselected full gameplay

| Stage | Seed | HUD gain | Custom bonus | Flag award | Extra lives | Full clip |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 00_baseline | 20101 | 900 | 0.0 | 100 | 0 | [Watch full attempt](stages/00_baseline/seed-20101/beginning.gif) |
| 00_baseline | 20110 | 900 | 0.0 | 100 | 0 | [Watch full attempt](stages/00_baseline/seed-20110/beginning.gif) |
| 00_baseline | 20120 | 1,200 | 0.0 | 400 | 0 | [Watch full attempt](stages/00_baseline/seed-20120/beginning.gif) |
| 01_stage | 20101 | 200 | 0.0 | 0 | 0 | [Watch full attempt](stages/01_stage/seed-20101/beginning.gif) |
| 01_stage | 20110 | 200 | 0.0 | 0 | 0 | [Watch full attempt](stages/01_stage/seed-20110/beginning.gif) |
| 01_stage | 20120 | 0 | 0.0 | 0 | 0 | [Watch full attempt](stages/01_stage/seed-20120/beginning.gif) |
| 02_stage | 20101 | 5,800 | 0.0 | 5,000 | 0 | [Watch full attempt](stages/02_stage/seed-20101/beginning.gif) |
| 02_stage | 20110 | 5,800 | 0.0 | 5,000 | 0 | [Watch full attempt](stages/02_stage/seed-20110/beginning.gif) |
| 02_stage | 20120 | 2,800 | 0.0 | 2,000 | 0 | [Watch full attempt](stages/02_stage/seed-20120/beginning.gif) |
| 03_stage | 20101 | 5,800 | 0.0 | 5,000 | 0 | [Watch full attempt](stages/03_stage/seed-20101/beginning.gif) |
| 03_stage | 20110 | 5,800 | 0.0 | 5,000 | 0 | [Watch full attempt](stages/03_stage/seed-20110/beginning.gif) |
| 03_stage | 20120 | 5,800 | 0.0 | 5,000 | 0 | [Watch full attempt](stages/03_stage/seed-20120/beginning.gif) |
| 04_stage | 20101 | 5,800 | 0.0 | 5,000 | 0 | [Watch full attempt](stages/04_stage/seed-20101/beginning.gif) |
| 04_stage | 20110 | 1,200 | 0.0 | 400 | 0 | [Watch full attempt](stages/04_stage/seed-20110/beginning.gif) |
| 04_stage | 20120 | 5,800 | 0.0 | 5,000 | 0 | [Watch full attempt](stages/04_stage/seed-20120/beginning.gif) |
| 05_stage | 20101 | 5,800 | 0.0 | 5,000 | 0 | [Watch full attempt](stages/05_stage/seed-20101/beginning.gif) |
| 05_stage | 20110 | 5,800 | 0.0 | 5,000 | 0 | [Watch full attempt](stages/05_stage/seed-20110/beginning.gif) |
| 05_stage | 20120 | 5,800 | 0.0 | 5,000 | 0 | [Watch full attempt](stages/05_stage/seed-20120/beginning.gif) |

### Confirmation checks and rollbacks

- 01_stage: Confirmed regression; roll back to best. Candidate 0/20 and 0.0 completed augmented points; reference 20/20 and 1,090.0. [Recorded check](confirmations/01_stage/comparison.json)
- 04_stage: Confirmed regression; roll back to best. Candidate 19/20 and 5,105.0 completed augmented points; reference 20/20 and 5,795.0. [Recorded check](confirmations/04_stage/comparison.json)
- 05_stage: Confirmed regression; roll back to best. Candidate 18/20 and 4,525.0 completed augmented points; reference 17/20 and 4,930.0. [Recorded check](confirmations/05_stage/comparison.json)

Confirmation pairs use additional validation seeds declared before launch. They diagnose an apparent regression; they do not replace the original selection set or count as the final test.

## Final held-out comparison

Pending or incomplete. A final comparison requires all 100 planned attempts for both frozen models; no partial result is reported as final.


## Classroom discussion

- Which changes are visible in the clips, and which explanations are still guesses?
- Did the custom 1UP bonus improve actual HUD points, or a different teaching objective?
- Why can sparse rewards damage a policy that already finishes reliably?
- Did increasing the score weight help every time? Why retain regressions and rollbacks?
- Why freeze selection before the final test? What would another level test?

The live desktop window observes one of four training environments. Closing it does not stop training. Saved clips are uploaded to GitHub when publication succeeds; retained local files can be published again without training.
