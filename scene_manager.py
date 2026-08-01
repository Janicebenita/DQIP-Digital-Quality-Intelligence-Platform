"""Scene models and narration-aware timing utilities."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Scene:
    title: str
    narration: str
    action: str
    start: float = 0.0
    speech_end: float = 0.0
    end: float = 0.0

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def apply_audio_timings(scenes: list[Scene], durations: list[float], pause: float = 1.0, target: float = 355.0) -> list[Scene]:
    """Assign stable timeline positions from measured audio durations."""
    if len(scenes) != len(durations):
        raise ValueError("A measured duration is required for every scene.")
    base_durations = [max(7.0, float(audio_duration) + pause) for audio_duration in durations]
    extra = max(0.0, target - 0.75 - sum(base_durations)) / max(1, len(scenes))
    cursor = 0.75
    timed: list[Scene] = []
    for scene, base_duration in zip(scenes, base_durations):
        duration = base_duration + extra
        timed.append(replace(scene, start=cursor, speech_end=cursor + float(durations[len(timed)]), end=cursor + duration))
        cursor += duration
    return timed


def clamp_demo_duration(scenes: list[Scene], minimum: float = 330.0, maximum: float = 360.0) -> float:
    """Return a professional target duration while protecting the narration."""
    required = scenes[-1].end + 1.5 if scenes else minimum
    return max(minimum, min(maximum, required))
