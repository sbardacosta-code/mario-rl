# Mario RL

Train a Super Mario Bros. World 1-1 agent with [gym-super-mario-bros](https://github.com/Kautenja/gym-super-mario-bros), Gymnasium, and Stable Baselines3.

The first experiment trained PPO for **25 minutes**, collecting **262,556 agent decisions** and completing **4,096 optimizer steps**. The final checkpoint was evaluated against its untrained initial network. **All three evaluation trials regressed; this run did not produce a better-playing agent.**

| Three-trial evaluation | Before | After |
| --- | ---: | ---: |
| Mean furthest horizontal position | 1,584.7 px | 575.7 px |
| Mean native episode reward | 1,396.3 | 501.7 |
| Level completions | 0 / 3 | 0 / 3 |


| Evaluation seed | Before: furthest position | After: furthest position |
| --- | ---: | ---: |
| 101 | 1,435 | 308 |
| 202 | 1,647 | 295 |
| 303 | 1,672 | 1,124 |

The timed run stopped automatically. 28 parameter tensors changed, all saved parameters are finite, and the checkpoint reloads with matching weights and optimizer step count. See [verification](results/first_training/verification.json). Of the collected decisions, 262,144 belonged to complete PPO rollouts; the final 412 were discarded when the time limit stopped collection.

See [comparison](results/first_training/comparison.json), [training summary](results/first_training/training_summary.json), and [configuration](results/first_training/config.json).

![Training progress](results/first_training/progress.png)

## Checkpoint evaluations

| Approximate training time | Decisions | Mean furthest position | Level clears |
| --- | ---: | ---: | ---: |
| 5 min | 52,228 | 296.0 | 0 / 3 |
| 10 min | 102,796 | 296.0 | 0 / 3 |
| 15 min | 156,392 | 683.3 | 0 / 3 |
| 20 min | 209,924 | 1,040.3 | 0 / 3 |
| 25 min (reported final) | 262,556 | 575.7 | 0 / 3 |

The earlier checkpoints show an initial collapse and partial recovery. We report the final time-budget checkpoint; no model was selected after looking at the final scores. All intermediate metrics and clips are retained in [intermediate](results/first_training/intermediate).

## Watch the result

| Untrained network | Final checkpoint |
| --- | --- |
| ![Before training](results/first_training/baseline/first-seed.gif) | ![After training](results/first_training/final/first-seed.gif) |

These looping GIFs show the first 300 decisions, or the earlier episode end, of evaluation seed 101. One native RGB frame is recorded after each repeated action, played at an approximate rate because GIF frame timings are quantized. They are short excerpts; the JSON metrics cover complete trials. The baseline samples actions from an untrained PPO network.

## What learns

PPO uses `CnnPolicy`, four World 1-1 environments, training seed 123, and one CPU thread. The five `RIGHT_ONLY` actions are wait, right, right+jump, right+run, and right+run+jump. Each decision repeats for up to four emulator frames, stopping at episode end. Rewards are the native rewards summed across those frames.

Inputs are four stacked 84 × 84 grayscale images: `uint8`, shape `(4, 84, 84)`. Episodes have a 3,000-decision limit. The current objective is increasing distance and eventually finishing World 1-1.

This is one training seed and three stochastic evaluation trials, using matched seeds 101, 202, and 303. Seeds vary sampled actions; they do not create new levels. These results cannot establish reliable completion or generalization. The reported model is the final checkpoint, chosen by the time budget.

## Run locally

The configured Mac can use its existing `.venv` immediately. For a fresh checkout, first install native Python 3.13, then run:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip check
.venv/bin/python mario_env.py
```

Start a fresh 25-minute experiment in a new directory:

```sh
.venv/bin/python train.py --run-dir results/next_training --max-seconds 1500 --device cpu --threads 1 --n-envs 4
```

Continue the saved model:

```sh
.venv/bin/python train.py --resume results/first_training/checkpoints/final.zip --run-dir results/continued_training --max-seconds 1500 --threads 1
```

Resume restores parameters and optimizer state; simulator state, partial rollouts, and random-number state are not restored exactly. Checkpoint ZIPs and detailed logs stay local and are Git-ignored. Cloning this repository does not download model weights.

Evaluate without learning and generate a replay GIF:

```sh
.venv/bin/python evaluate.py --model results/first_training/checkpoints/final.zip --output-dir results/replay --seeds 101 202 303
open results/replay/first-seed.gif
.venv/bin/python summarize.py --run-dir results/first_training
```

## Play manually

Double-click `play.command` in Finder or run `./play.command`. Focus the game window: **A/D** move, **O** jumps, **D+P** runs right, **Escape** quits. The launcher uses this repository's `.venv`.

## Next experiment

The [learning log](results/first_training/learning_metrics.csv) shows very large early policy changes and a rapid loss of action diversity. The [diagnostics](results/first_training/early_diagnostics.json) record that evidence. Unscaled value targets affecting the shared visual network are a possible cause; this has not been proven.

For the next controlled run, start from the same untrained model and scale rewards used for learning by `0.01`, keeping native rewards for evaluation and all other settings fixed. This tests reward scale as one change. A limit on policy changes (`target_kl`) is a separate later experiment if instability persists. Neither change was applied during this run.
