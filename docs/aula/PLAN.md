# Mario learns: teaching project plan

Objective: enable students to observe and measure how a policy changes as it learns to play World 1-1. The project does not assume that the agent will finish the level or that every stage will improve.

## A session of up to three hours

- Starting point: the model from the reward ×0.01 pilot, with 102,400 prior decisions. The initial stage is evaluated before further training.
- Continue in blocks of approximately 15 minutes, preserving one checkpoint per block and a record of every stage.
- Five fixed trials per stage: 101, 202, 303, 404, 505. For 101, 202, and 303, save clips of the first 150 and last 75 decisions, the final frame, and the full trace. Clips may overlap in short episodes.
- Separate final audit: 10 new seeds, 1001–1010, applied to the final model selected by the budget. The best result is not selected retrospectively and presented as the final model.
- The process reserves time for evaluations and closing the session; it does not spend the entire three hours training. The absolute deadline is recorded in the manifest. If an upload remains pending, finish it afterward without further training.

## Candidate configuration

| Parameter | Value | Reason |
| --- | ---: | --- |
| Algorithm | PPO with a CNN | Keep the method and observations already tested |
| Learning reward | Native ×0.01 | The previous pilot showed greater early stability |
| Learning rate | 0.0001 | Test smaller adjustments than with 0.00025 |
| KL limit | 0.02 | Stop an update if the policy changes excessively |
| Entropy coefficient | 0.01 | Maintain the incentive to explore |
| Environments / CPU threads | 4 / 1 | Configuration measured on this Mac |
| Steps per environment / batch size / epochs | 256 / 256 / 4 | Keep the rest of the PPO configuration |
| Observation / action repeat | 4 images at 84 × 84 / 4 frames | Preserve the existing representation |

These are candidate parameters, not a demonstrated optimum. The learning rate and KL limit change together, and training continues from an existing checkpoint: this session cannot isolate the effect of each change. A later causal experiment should vary one parameter at a time and repeat training seeds.

## What students see in class

The [gallery](README.md) presents the mean, median, distance range, and completed levels for each stage. It also shows where each attempt ended and periods of 120 decisions without exceeding the previous maximum position. This measures a lack of progress: it does not prove that Mario is motionless or identify an enemy or a pit by itself.

The [teaching guide](GUIA_DOCENTE.md) proposes a 35–45-minute class: predict actions, compare clips, distinguish reward from success, formulate hypotheses, and test them. Regressions and failures are preserved as part of the material.

## Saving results and continuing

The repository link and the link to docs/aula remain stable. Each session has its own folder containing a manifest, parameters, metrics, clips, and traces. Earlier stages are not overwritten. The main dashboard points to the latest session, and individual session reports remain archived.

Checkpoints are saved locally and, when a published session is complete, backed up as GitHub Release assets. Their link appears in the gallery only after the upload finishes. The repository's access settings remain in effect; a private repository requires authorized collaborators.

Resuming from a checkpoint restores the weights and optimizer. Each block resets the emulator and its seed; it does not exactly reproduce the simulator's previous state or its random generator state. The reward scale must explicitly remain at 0.01.

The program generates results without relying on a game window. The gallery updates when each stage closes, not frame by frame. To stop and save, create a `STOP` file in the session folder. Keeping the Mac awake and the app open allows local training and monitoring to continue.

## References

- [PPO and its parameters](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html)
- [Evaluation, variability, and good RL practices](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html)
- [Super Mario Bros. environment](https://github.com/Kautenja/gym-super-mario-bros)
