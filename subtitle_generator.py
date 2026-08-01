"""SRT generation for the automated storytelling video."""

from __future__ import annotations

from pathlib import Path
import re

from scene_manager import Scene


def _stamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def _chunks(text: str, maximum: int = 82) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    result: list[str] = []
    for sentence in sentences:
        words, current = sentence.split(), ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) <= maximum:
                current = candidate
            else:
                if current:
                    result.append(current)
                current = word
        if current:
            result.append(current)
    return result or [text]


def generate_srt(scenes: list[Scene], output: Path) -> Path:
    rows, index = [], 1
    for scene in scenes:
        chunks = _chunks(scene.narration)
        spoken_duration = scene.speech_end - scene.start if scene.speech_end > scene.start else scene.duration
        usable = max(1.0, spoken_duration - 0.12)
        weights = [max(1, len(chunk.split())) for chunk in chunks]
        total = sum(weights)
        cursor = scene.start
        for chunk, weight in zip(chunks, weights):
            duration = usable * weight / total
            rows += [str(index), f"{_stamp(cursor)} --> {_stamp(cursor + duration)}", chunk, ""]
            cursor += duration
            index += 1
    output.write_text("\n".join(rows), encoding="utf-8")
    return output
