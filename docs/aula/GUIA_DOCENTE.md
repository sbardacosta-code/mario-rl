# Mario learns: a guide for a 35–45-minute class

Open the [classroom dashboard](README.md). It contains the saved stages, their metrics, and gameplay samples. You can teach the class using the recorded results, without waiting for a live training run to finish.

**Learning objective:** by the end of the class, students should be able to describe what the agent receives, which actions it can take, which signal it tries to optimize, and what evidence would justify saying it plays better. One impressive gameplay clip is not enough.

## Before class

1. Check that the instructor's account can open the repository and the GIFs. If the repository is private, the link requires authorized access.
2. Open the dashboard, this guide, and two stages from different points in training. Use the same seed in both stages for the first comparison.
3. Load the animations before projecting them. To work offline, download or clone the repository with its files and open the GIFs in a local viewer. Relative links and images also work in a local Markdown viewer.
4. Check the session status: a report marked “in progress” contains only the evaluations completed so far. A pending or incomplete stage is not a zero result.
5. Read the experiment's limitations: World 1-1, one training seed, and several trials on the same level. Downloading the repository's code does not include the `.zip` model weights. If the dashboard links to a published model release, download the weights separately from that link; otherwise, they remain local.

## 0–5 minutes: make a prediction

Show the beginning of the initial stage without revealing the final figures. Ask: “What do you expect to improve first: walking, jumping at the right time, or finishing the level? How would you measure it?” Write down two testable predictions.

A session's initial stage may use a previously trained model. Check its label and accumulated decisions before calling it “untrained.” The historical experiment does preserve the initial untrained network, which already made progress by chance when sampling actions.

## 5–12 minutes: explain the learning loop

| Concept | In this project | Question for the class |
| --- | --- | --- |
| Observation | Four consecutive grayscale images, each 84 × 84 pixels | Why might one image fail to show which way Mario is moving? |
| Action | Wait, right, right + jump, right + run, right + run + jump | Which strategies are unavailable if the agent cannot move left? |
| Reward | A numerical signal from the environment, summed across the frames of an action | Is this the same as touching the flag? |
| Policy | A network converts the images into probabilities for these actions | Can it choose different actions in similar situations? |
| Episode | One attempt until it ends or reaches the decision limit | Is reaching a time limit the same as dying? |
| Update | PPO uses recent experience to adjust the weights | Does watching a recording change the model? |

One decision holds the buttons for up to four emulator frames. A decision, a frame, and a network update are therefore different units. In this project, the network receives images; the coordinates in the reports are used to measure and explain the result.

The loop is **observe → choose an action → receive a new observation and reward → gather experience → adjust the weights → repeat**. PPO alternates interaction with the environment and optimization using small batches of experience. The policy does not receive a human explanation of its mistakes or understand Mario as a person would. [Original PPO paper](https://arxiv.org/abs/1707.06347).

## 12–22 minutes: observe the stages and mistakes

Compare the opening and ending clips for the same seed across two stages. The ending clip shows what happens near the end of the attempt; if the attempt was short, the two clips may overlap. The clips are excerpts, and their labels identify the stage and decisions; the CSV preserves the measured trajectory.

Use one row for each observation:

| Stage and seed | Observable evidence | Hypothesis | What to check |
| --- | --- | --- | --- |
| Fill in while watching the clip | “It repeats the jump and stops increasing its position.” | “Perhaps the action became too repetitive.” | Action frequencies in the CSV and other seeds |
| Fill in while watching another stage | “In this trial, it passes the position where the earlier attempt ended.” | “Its jump timing may have improved.” | Repeat with more attempts and review the other clips |

Distinguish “the attempt ended near x = …” from “this enemy killed it.” The first statement can come from the measurements. The second requires inspecting the video and may remain uncertain: a position value does not identify a cause. Here, “stalled” means a prolonged stretch without increasing the furthest position reached, according to the protocol's threshold; it does not mean the system automatically detects a wall.

Ask: “Did it improve on every seed or only one? Which mistake appears less often? Did another mistake appear?” If performance does not improve, keep that result: it is an opportunity to explain that training adjusts parameters but does not guarantee useful behavior within the available time.

## 22–30 minutes: read the chart as experimental evidence

The maximum position is the furthest horizontal coordinate reached in the level; it is not a percentage of the level completed or a distance measured from zero. Use the mean alongside the median and range: an exceptional attempt can raise the mean. Reaching the flag is counted separately.

Evaluation seeds control action sampling on the same level; they do not generate five new worlds. During these evaluations, the policy keeps its weights fixed. In stochastic mode, it samples actions according to their probabilities; in deterministic mode, it chooses the preferred action. Keep the same mode and protocol when comparing results. Periodic evaluation in a separate environment and repeated attempts help distinguish learning from variability, although a small number of trials still provides limited evidence. [Stable Baselines3 evaluation guide](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html#how-to-evaluate-an-rl-algorithm).

The curve can rise and fall. Showing every stage avoids telling a story made up only of the best moments. If you highlight a stage for demonstration because it achieved the greatest progress, explain that it was selected using those results: this is not independent evidence of superiority.

This session's parameters are a configuration to test, not universally “the best.” A lower learning rate reduces the size of the adjustments; the KL threshold allows an update to stop early if the policy changes too much according to that measure. The entropy coefficient encourages the policy to retain a variety of actions. None guarantees level completion. If several parameters change at once, the comparison describes their combined effect and does not identify which change caused the result.

## 30–35 minutes: the first failure is also instructive

The historical experiments are in the [project README](../../README.md). Across three trials with an equivalent learning budget, the model using native rewards reached a mean position of **296**, while the model using rewards multiplied by **0.01** reached **434**. The initial untrained network reached approximately **1,585**. All three completed **0 of 3 levels**.

Reward scaling improved that pilot relative to the original configuration, but its performance remained below the initial network's. It did not demonstrate that Mario had learned to finish the level. The comparison data is in [ab_comparison.json](../../results/reward_scaled/ab_comparison.json).

Multiplying rewards by 0.01 changes the magnitudes used during learning. To make the results interpretable, this project retains native rewards in its evaluations. Scaling does not add a teacher who tells the agent when to jump. Training rewards at different scales and the resulting value losses are not directly comparable quality scores.

## 35–45 minutes: optional activity and discussion

In groups, choose two predefined stages and record one observation per seed. Ask for a two-sentence conclusion: one sentence about the evidence and one about what cannot yet be established.

Closing questions:

- What would justify saying “it learned to get past this obstacle,” and what would we require before saying “it plays well”?
- What would you change in the next experiment, and what would you keep fixed so you could interpret the result?
- Does receiving a higher reward always mean traveling farther or finishing the level?
- What would happen on another level? Do we have evidence that the agent could complete it?
- If a configuration changes several parameters at once and improves, can we tell which one was responsible?

A good answer cites specific trials, acknowledges regressions, and avoids attributing human intention, understanding, or memories to the network's weights.

## How to continue without losing the history

Save each session in a new folder and preserve its checkpoints and evaluations. Updating the dashboard with `lesson_report.py` and uploading the report files to GitHub keeps the classroom link unchanged. Each session also retains its own report in its results folder, so later sessions do not overwrite its evidence.

Training can resume from a checkpoint. This preserves the weights and optimizer state but does not exactly reconstruct the emulator state, an incomplete batch, or the entire previous random sequence. Keeping the budget and configuration in the manifest makes it possible to explain what was actually compared.

## References for preparing the lesson

- [gym-super-mario-bros environment](https://github.com/Kautenja/gym-super-mario-bros): the game and API used.
- [PPO paper](https://arxiv.org/abs/1707.06347): the learning algorithm.
- [Stable Baselines3 tips](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html): evaluation and practical limitations.
