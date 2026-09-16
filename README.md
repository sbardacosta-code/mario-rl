# Mario RL

Train a Super Mario Bros. World 1-1 agent with [gym-super-mario-bros](https://github.com/Kautenja/gym-super-mario-bros), Gymnasium, and Stable Baselines3.

## Proyecto para el aula

[**Abrir la galería de aprendizaje de Mario**](docs/aula/README.md) · [Guía para el profe](docs/aula/GUIA_DOCENTE.md) · [Plan de entrenamiento y enseñanza](docs/aula/PLAN.md)

El laboratorio conserva muestras de cada etapa, métricas comparables y trazas de acciones para discutir cómo aprende una política, dónde falla y cuándo retrocede. El enlace del aula permanece estable al publicar nuevas sesiones. El acceso depende de los permisos del repositorio.

La sesión docente usa bloques de aproximadamente 15 minutos y cinco evaluaciones fijas por etapa. Sus parámetros son una configuración candidata, no un óptimo demostrado. Al finalizar se evalúa el modelo con diez semillas nuevas y se respaldan los checkpoints de la sesión en GitHub Releases cuando la publicación está habilitada.

Para preparar y ejecutar una nueva sesión local (hasta tres horas, reservando tiempo para evaluar y guardar):

```sh
.venv/bin/python lesson_session.py --run-dir results/mi_clase --initial-model results/reward_scaled/checkpoints/final.zip --prepare-only
.venv/bin/python lesson_session.py --run-dir results/mi_clase --start-prepared --publish
```

El primer comando requiere un checkpoint local existente. Se conserva una carpeta distinta por sesión; no se sobrescriben resultados anteriores. `--publish` confirma y sube únicamente los resultados de esa sesión y los documentos del aula a `main`. Para detenerla con guardado, crear un archivo `STOP` en su carpeta de resultados.

## Reward scaling pilot

The second experiment changed **only the training reward multiplier to 0.01**, restarting the exact original untrained checkpoint. It trained for **10.0 minutes**, using **102,400 decisions and 1,600 optimizer steps**. The comparison uses the original run's approximately 10-minute checkpoint, which has the same number of completed learning updates.

**The scaled agent traveled farther than the unscaled agent at the same update budget. It still fell short of the untrained network on these three trials. The scaled model cleared the level in 0 of 3 trials.**

| Three-trial evaluation | Untrained | Native rewards | Rewards × 0.01 |
| --- | ---: | ---: | ---: |
| Mean furthest position | 1,584.7 px | 296.0 px | 434.0 px |
| Mean native reward | 1,396.3 | 231.0 | 369.0 |
| Level completions | 0 / 3 | 0 / 3 | 0 / 3 |

The trained columns each represent 100 complete PPO rollouts and 400 epochs. The original archive has 102,796 collected decisions, including 396 not yet used in learning; its policy reflects 102,400 optimized decisions. The final scaled checkpoint was selected by the predefined budget. The original 25-minute final is retained below as a separate result, with a larger training budget.

![Reward scaling comparison](results/reward_scaled/reward_scale_comparison.png)

[Experiment plan](results/reward_scaled/experiment_plan.json) · [Comparison data](results/reward_scaled/ab_comparison.json) · [Checkpoint verification](results/reward_scaled/verification.json) · [Scaled gameplay clip](results/reward_scaled/final/first-seed.gif)

The initial policy hash and first rollout match the original run. Saved weights are finite, changed during learning, and reload with the recorded policy hash and optimizer step count. Evaluation still uses native rewards and the same three stochastic seeds. This is a short pilot with one training seed, so the result does not establish reliable performance.

Reward scaling uses a [Gymnasium reward wrapper](https://gymnasium.farama.org/api/wrappers/reward_wrappers/) outside native episode accounting. `episodes.csv` and evaluation retain native rewards; SB3's `rollout/ep_rew_mean` logs scaled learning rewards. The [early diagnostics](results/reward_scaled/early_diagnostics.json) show smaller policy changes and retained action diversity at the early steps where the original run collapsed. That observation supports improved early stability; it does not prove the cause of the original failure. Value losses use different reward units and are not directly comparable quality scores.

Reproduce this pilot on the configured Mac in a new results directory:

```sh
.venv/bin/python scripts/check_reward_scaling.py
.venv/bin/python train.py --run-dir results/reward_scaled_repeat --resume results/first_training/checkpoints/initial.zip --reward-scale 0.01 --device cpu --threads 1 --n-envs 4 --seed 123 --max-timesteps 102400 --max-seconds 660
.venv/bin/python evaluate.py --model results/reward_scaled_repeat/checkpoints/final.zip --output-dir results/reward_scaled_repeat/final --seeds 101 202 303
```

The initial checkpoint is local. On a fresh checkout, create one in a new directory with `.venv/bin/python train.py --run-dir results/recreated_initial --initialize-only --threads 1`, then change the pilot command to use `--resume results/recreated_initial/checkpoints/initial.zip`. Regenerate the recorded comparison with `.venv/bin/python compare_reward_scaling.py --repo .`.

## First experiment: native rewards

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

PPO uses `CnnPolicy`, four World 1-1 environments, training seed 123, and one CPU thread. The five `RIGHT_ONLY` actions are wait, right, right+jump, right+run, and right+run+jump. Each decision repeats for up to four emulator frames, stopping at episode end. Native rewards are summed across those frames. `--reward-scale` then multiplies rewards for learning only; it defaults to `1.0` and was `0.01` in the scaling pilot.

Inputs are four stacked 84 × 84 grayscale images: `uint8`, shape `(4, 84, 84)`. Episodes have a 3,000-decision limit. The current objective is increasing distance and eventually finishing World 1-1.

This is one training seed and three stochastic evaluation trials, using matched seeds 101, 202, and 303. Seeds vary sampled actions; they do not create new levels. These results cannot establish reliable completion or generalization. Each reported model is the final checkpoint chosen by its predefined training budget.

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

Continue the scaled model, keeping its reward multiplier:

```sh
.venv/bin/python train.py --resume results/reward_scaled/checkpoints/final.zip --run-dir results/continued_training --reward-scale 0.01 --max-seconds 1500 --threads 1
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

The scaling pilot improved distance against the matched unscaled checkpoint. A useful next test is a longer run with the same scaled configuration, followed by more evaluation trials and additional training seeds. This session stopped after the short pilot; no longer run has been started.
