# Mario RL

Learn reinforcement learning by training an agent to play Super Mario Bros. with [gym-super-mario-bros](https://github.com/Kautenja/gym-super-mario-bros).

**Status: planning only.** This repository contains the starting plan. No environment has been installed, no training code has been implemented, and no training has been started.

First goal: teach an agent to finish **World 1-1** consistently, then measure how well it handles other levels.

## 1. Clone the repository when ready

```sh
git clone https://github.com/sbardacosta-code/mario-rl.git
cd mario-rl
```

All commands below are instructions for a future setup session; they have not been run for this project.

## 2. Create a separate Python environment

Use native ARM64 **Python 3.13** on an Apple Silicon Mac. If that interpreter is not installed, install it before running:

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

The current Mario release requires Python 3.13 or newer. The NES emulator publishes a Python 3.13 macOS ARM64 wheel. See [Mario requirements](https://pypi.org/project/gym-super-mario-bros/) and [NES emulator downloads](https://pypi.org/project/nes-py/#files).

## 3. Install and verify the learning tools

Proposed starting versions, checked against published packages on September 15, 2026:

```sh
python -m pip install "gym-super-mario-bros==9.1.0" "nes-py==9.0.1" "stable-baselines3[extra]==2.9.0"
python -m pip check
```

[Stable Baselines3](https://pypi.org/project/stable-baselines3/) provides the learning algorithm and uses PyTorch; its extras include TensorBoard for training charts. These versions are a documented starting point, not an installation tested on this machine. After the environment checks below pass, save the resolved versions for reproducibility.

Use the modern Gymnasium API in future code: `reset()` returns observation and info; `step()` returns observation, reward, terminated, truncated, and info. End an episode when either termination flag is true.

## 4. Check the game before training

First open World 1-1 and play with the keyboard:

```sh
python -m gym_super_mario_bros --env SuperMarioBros-1-1-v0 --mode human --actionspace simple
```

Then run a short random-action check:

```sh
python -m gym_super_mario_bros --env SuperMarioBros-1-1-v0 --mode random --actionspace right --steps 1000 --no-render --seed 123
```

Verify that the game opens, actions advance it, observations and rewards arrive, and episodes reset correctly. Random play is a functionality check, not learning. [Environment and CLI documentation](https://github.com/Kautenja/gym-super-mario-bros#usage)

## 5. Prepare what the agent sees and controls

Implement preprocessing: resize screenshots, convert them to grayscale, repeat each action for a few game frames, and stack four observations so the model can infer motion. Start with the `RIGHT_ONLY` action set, which includes jumping. Validate the final observation shape, action space, and reset/step behavior before training.

## 6. Add the first training experiment

Implement PPO with Stable Baselines3's `CnnPolicy`, which learns from images. Begin with one environment and a short CPU run to check the training loop, model saving, and logs. Only then increase the training budget. Benchmark hardware options before choosing them. [PPO documentation](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html)

Planned files to add during implementation:

- `src/mario_rl/env.py`: environment creation and preprocessing.
- `train.py`: PPO training, checkpoint saving, and logging.
- `evaluate.py`: load a checkpoint and watch or record the agent.
- `requirements.txt`: verified dependency versions.
- `.gitignore`: exclude the virtual environment, checkpoints, recordings, and logs.

## 7. Measure progress and watch saved models

Train without continuously drawing the game window. Evaluate saved checkpoints separately using the same preprocessing and action mapping. Record distance reached, level completion rate, episode reward, and evaluation seeds. Compare with random play; retain the best model and a short video of its behavior.

## 8. Expand after World 1-1 works

Aim for reliable completion across repeated evaluation episodes. Then add other levels and evaluate on levels the agent did not train on. Change one major setting at a time and record what changed and what happened.

The next milestone is a verified World 1-1 environment. Training time and success will depend on the implementation, hardware, and learning settings.
