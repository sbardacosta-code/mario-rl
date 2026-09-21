# Learning to earn points without forgetting how to finish

The overnight experiment starts from the preserved World 1-1 model. It has an absolute stop time, saves separate checkpoints about every 15 minutes of learning, and checks each model with learning disabled. The live window samples one of four training environments; the saved clips replay frozen checkpoints under documented seeds.

## What counts as a point?

| Event | Actual game score | Learning treatment |
| --- | --- | --- |
| Collect a coin, defeat an enemy, or collect a scoring item | Read the actual change in the game's HUD | Include the HUD increase once; no guessed extra coin or enemy score |
| Touch the flagpole | The game awards points after the slide; higher tiers award more | Allow a bounded, automatic no-button animation and read the actual award |
| Gain an extra life, including a collected hidden 1-UP | A life increase need not increase HUD points | Add **1,000 teaching points** per observed extra life, recorded separately |
| Reveal a hidden block without gaining a life | No assumed score | No invented hidden-block detection or reward |
| Finish the attempt | Reaching the flag is recorded separately from points | Add a completion reward of 5 |
| End without reaching the flag | Actual points remain recorded | Apply a failure reward of −5; count the attempt as zero in the main completed-score metric |

The five flagpole awards are **100, 400, 800, 2,000, and 5,000 actual points**. The integration checks the game's selected tier against the observed HUD increase; it never writes a guessed award into the game. Smaller recorded contact-y values mean a higher contact on screen. The final timer conversion and fireworks occur later and are excluded from this experiment.

An extra life is detected by an increase in the life counter within an attempt. A coin-counter rollover can identify a coin-related extra life; other increases are labeled **other or unknown**. These measurements do not prove which hidden block or mushroom caused the life. A matched clip is needed to explain the visible behavior.

The score objective is:

`HUD increase / 1,000 + newly gained extra lives + completion bonus − failure penalty`

The transition objective blends that score objective with the previous native reward, scaled by 0.01. Its score share is recorded in every stage. Native reward includes movement guidance and other components, so rewards from different shares must not be compared as if they were game points. The frozen evaluations always use the same score measurement and starting level.

## Why keep the old model?

The earlier score-only pilot showed a severe drop in recent training completions. Its results are preserved. Changing the reward changes what the value estimator is trying to predict, and removing movement guidance may make transfer harder. Those are explanations to test, not a proven diagnosis.

The overnight experiment tests smaller policy updates from the successful baseline. It retains every attempted stage, including rejected ones. A checkpoint must clear at least 19 of the 20 validation attempts to qualify. Higher ordinary points from unsuccessful attempts cannot replace reliable finishing in the main ranking.

Apparent regressions trigger a paired confirmation before returning to a prior checkpoint. A limited conservative retry is allowed. Repeated failure stops that path; the job may end early if no validated approach remains. Six hours is an upper bound, not a promise of continuous improvement.

## How to teach from the report

For each stage, compare the same recorded seeds. Look at HUD points, actual flag award, extra lives, completion, and the last location together. Ask:

1. Did Mario gain more real points, more custom extra-life credit, or both?
2. Does a higher flag award appear in the corresponding clip?
3. Did the attempt actually finish, or did a promising score end in failure?
4. What changed after returning to an earlier checkpoint?
5. Are we observing a repeatable difference, or a single interesting attempt?

Validation results are reused to choose checkpoints. The final candidate is selected before two frozen 100-attempt tests use the same reserved action seeds. Those seeds change sampled actions on World 1-1; they are not new levels. A single overnight run does not prove a global maximum or general Mario skill.

The current policy retains its original five controls: wait, right, right+jump, right+run, and right+run+jump. It cannot backtrack. It can receive extra-life credit if it learns to collect one, but this run does not guarantee discovery of every secret.

## Leaving the computer overnight

Keep the computer plugged in with its lid open and ventilation clear. The bounded runner prevents idle system sleep while it is active and records its absolute deadline. Closing the viewer does not stop learning. Creating a `STOP` file in the session folder asks the runner to save and stop. Network failures leave publication marked pending; they do not justify retraining an already completed experiment.

Code, reports, seeds, traces, and recordings are stored in GitHub. Model files are saved locally and uploaded as verified release assets when finalization succeeds. The classroom index retains links to earlier experiments.
