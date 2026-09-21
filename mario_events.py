"""Opt-in SMB1 events and bounded, action-free flag-award resolution.

This wrapper belongs directly outside the raw Gym environment, before joypad
mapping and action repetition. It does not modify ordinary native rewards. At a
flag terminal it advances only the automatic pole animation with NOOP until the
game posts its real flag-height award, then stops before the castle/time bonus.
The extra emulator frames are reported separately from agent decisions.

RAM semantics were checked against the installed gym-super-mario-bros 9.1.0 and
the SMB1 disassembly: FlagpoleCollision, FlagpoleRoutine, GiveOneCoin,
HandlePowerUpCollision, and FloateyNumbersRoutine.
https://github.com/pgattic/smb1-disasm/blob/master/main.asm
https://github.com/pgattic/smb1-disasm/blob/master/constants/constants.asm
"""

from __future__ import annotations

import copy
from numbers import Integral

import gymnasium as gym


EVENT_CONFIG = {
    "version": "smb1_flag_award_and_life_gain_v1",
    "flag_resolution": "NOOP frames until engine mode 4 becomes 5 and the real score award is verified, then two score/time-invariant presentation frames",
    "max_post_flag_frames": 300,
    "presentation_frames": 2,
    "score_definition": "actual HUD points including resolved flag-height award; later time and castle bonuses excluded",
    "native_reward_definition": "original native rewards through flag contact; automatic resolution adds no native reward",
    "one_up_definition": "positive observed life-counter changes within an episode, excluding the 255 game-over sentinel",
    "one_up_source_limit": "coin rollover is identified; other life gains are not claimed to originate from hidden blocks",
    "flag_tier_points": [5000, 2000, 800, 400, 100],
    "source_urls": [
        "https://github.com/pgattic/smb1-disasm/blob/master/main.asm",
        "https://github.com/pgattic/smb1-disasm/blob/master/constants/constants.asm",
    ],
}


class MarioEvents(gym.Wrapper):
    """Keep events cumulative so an outer action-repeat cannot lose them."""

    def __init__(self, env, *, max_post_flag_frames=300, record_resolution=False):
        super().__init__(env)
        if isinstance(max_post_flag_frames, bool) or not isinstance(max_post_flag_frames, Integral) or not 1 <= max_post_flag_frames <= 1200:
            raise ValueError("max_post_flag_frames must be an integer between 1 and 1200")
        self.max_post_flag_frames = int(max_post_flag_frames)
        self.record_resolution = bool(record_resolution)
        self.raw = env.unwrapped
        for name in ("ram", "_frame_advance", "_get_info", "screen"):
            if not hasattr(self.raw, name):
                raise TypeError(f"MarioEvents requires the raw NES interface: {name}")
        self.events = None
        self.previous_life = None
        self.previous_coins = None
        self.episode_identity = None

    @staticmethod
    def _integer(info, key):
        value = info.get(key)
        if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
            raise ValueError(f"MarioEvents requires nonnegative integer info[{key!r}]")
        return int(value)

    @staticmethod
    def _identity(info):
        return tuple(info.get(name) for name in ("world", "stage", "area"))

    def _attach(self, info):
        info = dict(info)
        info["event_metrics"] = copy.deepcopy(self.events)
        return info

    def reset(self, *, seed=None, options=None):
        observation, info = self.env.reset(seed=seed, options=options)
        self.previous_life = self._integer(info, "life")
        self.previous_coins = self._integer(info, "coins")
        self._integer(info, "score")
        self.episode_identity = self._identity(info)
        self.events = {
            "one_ups": 0,
            "one_up_source_counts": {"coin_rollover": 0, "other_or_unknown": 0},
            "hidden_1up_source_verified": False,
            "flag_height_bonus": 0,
            "flag_touch_y": None,
            "flag_contact_score": None,
            "flag_score_tier": None,
            "flag_top_tier": False,
            "post_flag_frames": 0,
            "flag_presentation_frames": 0,
            "flag_resolution_complete": False,
            "flag_resolution_status": "not_reached",
        }
        return observation, self._attach(info)

    def _track_lives(self, info):
        life, coins = self._integer(info, "life"), self._integer(info, "coins")
        if self._identity(info) != self.episode_identity:
            raise ValueError("MarioEvents saw a world/stage/area transition inside the single-level episode")
        # Never mistake a game-over sentinel, death, or episode reset for a 1-UP.
        delta = life - self.previous_life
        if self.previous_life != 255 and life != 255 and delta > 0:
            coin_life = int(self.previous_coins - coins > 50)
            self.events["one_ups"] += delta
            self.events["one_up_source_counts"]["coin_rollover"] += coin_life
            self.events["one_up_source_counts"]["other_or_unknown"] += delta - coin_life
        self.previous_life, self.previous_coins = life, coins

    def _resolve_flag(self, observation, info):
        contact = dict(info)
        score_before = self._integer(contact, "score")
        tier = int(self.raw.ram[0x010F])
        touch_y = int(self.raw.ram[0x070F])
        self.events.update(
            flag_contact_score=score_before,
            flag_score_tier=tier,
            flag_touch_y=touch_y,
            flag_top_tier=tier == 0,
            flag_resolution_status="resolving",
        )
        mode = int(self.raw.ram[0x000E])
        if mode != 4 or not 0 <= tier < 5:
            self.events["flag_resolution_status"] = "unexpected_flag_state"
            return observation, contact, [], [], None
        frames, frame_counts = [], []
        contact_frame = observation.copy() if self.record_resolution else None
        pending_frames = 0
        latest = contact
        for frame_number in range(1, self.max_post_flag_frames + 1):
            # Intentional native advance: Gym's terminal remains latched. Never
            # ask the policy for an action or call step() on a done environment.
            self.raw._frame_advance(0)
            self.events["post_flag_frames"] = frame_number
            pending_frames += 1
            latest = self.raw._get_info()
            self._track_lives(latest)
            mode = int(self.raw.ram[0x000E])
            gained = self._integer(latest, "score") - score_before
            if gained < 0:
                raise ValueError("HUD score decreased during flag resolution")
            if latest.get("time") != contact.get("time"):
                self.events["flag_resolution_status"] = "unexpected_timer_change"
                break
            if mode == 5:
                expected = EVENT_CONFIG["flag_tier_points"][tier]
                # The lookup validates what the game did; it never supplies or
                # alters a score. Unexpected observations fail closed in metrics.
                self.events["flag_height_bonus"] = gained
                valid = gained == expected
                self.events["flag_resolution_complete"] = valid
                self.events["flag_resolution_status"] = "complete" if valid else "award_mismatch"
                break
            if mode != 4:
                self.events["flag_resolution_status"] = "unexpected_engine_mode"
                break
            if self.record_resolution and pending_frames == 4:
                frames.append(self.raw.screen.copy())
                frame_counts.append(pending_frames)
                pending_frames = 0
        else:
            self.events["flag_resolution_status"] = "frame_limit"
        if self.events["flag_resolution_complete"]:
            # Score RAM updates before the PPU has drawn the digits. Let the
            # status-bar update become visible without reaching timer conversion.
            # These frames are still automatic and count against the same cap.
            settled_score = self._integer(latest, "score")
            for _ in range(EVENT_CONFIG["presentation_frames"]):
                if self.events["post_flag_frames"] >= self.max_post_flag_frames:
                    self.events["flag_resolution_complete"] = False
                    self.events["flag_resolution_status"] = "presentation_frame_limit"
                    break
                if self.record_resolution and pending_frames == 4:
                    frames.append(self.raw.screen.copy())
                    frame_counts.append(pending_frames)
                    pending_frames = 0
                self.raw._frame_advance(0)
                self.events["post_flag_frames"] += 1
                self.events["flag_presentation_frames"] += 1
                pending_frames += 1
                latest = self.raw._get_info()
                self._track_lives(latest)
                if (self._integer(latest, "score") != settled_score
                        or latest.get("time") != contact.get("time")
                        or int(self.raw.ram[0x000E]) != 5):
                    self.events["flag_resolution_complete"] = False
                    self.events["flag_resolution_status"] = "presentation_state_changed"
                    break
        if self.record_resolution and pending_frames:
            frames.append(self.raw.screen.copy())
            frame_counts.append(pending_frames)
        latest = dict(latest)
        latest["flag_get"] = True  # Preserve the already-observed task boundary.
        latest["clear"] = True
        return self.raw.screen.copy(), latest, frames, frame_counts, contact_frame

    def step(self, action):
        if self.events is None:
            raise RuntimeError("MarioEvents requires reset() before step()")
        observation, native_reward, terminated, truncated, info = self.env.step(action)
        self._track_lives(info)
        frames, frame_counts, contact_frame = [], [], None
        if info.get("flag_get", False) and self.events["flag_contact_score"] is None:
            if not terminated:
                raise ValueError("MarioEvents requires single-stage flag termination")
            observation, info, frames, frame_counts, contact_frame = self._resolve_flag(observation, info)
        info = self._attach(info)
        if self.record_resolution and contact_frame is not None:
            info["flag_contact_frame"] = contact_frame
            info["resolution_frames"] = frames
            info["resolution_frame_counts"] = frame_counts
        return observation, native_reward, terminated, truncated, info
