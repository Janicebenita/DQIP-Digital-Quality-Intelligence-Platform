"""Indian-English female narration and procedural corporate music."""

from __future__ import annotations

import asyncio
from pathlib import Path
import subprocess
import wave

import numpy as np

from scene_manager import Scene, apply_audio_timings


class VoiceGenerationError(RuntimeError):
    pass


def _run(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode:
        raise VoiceGenerationError(completed.stderr.strip() or "Media command failed.")


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as stream:
        return stream.getnframes() / float(stream.getframerate())


async def _synthesise(scenes: list[Scene], directory: Path) -> list[Path]:
    try:
        import edge_tts
    except ModuleNotFoundError as exc:
        raise VoiceGenerationError("edge-tts is not installed. Install the project requirements.") from exc
    paths: list[Path] = []
    for index, scene in enumerate(scenes, 1):
        path = directory / f"voice_scene_{index:02d}.mp3"
        communicator = edge_tts.Communicate(
            scene.narration,
            voice="en-IN-NeerjaNeural",
            rate="-5%",
            pitch="-1Hz",
            volume="+0%",
        )
        await communicator.save(str(path))
        paths.append(path)
    return paths


def generate_voice(scenes: list[Scene], workdir: Path, ffmpeg: str) -> tuple[list[Scene], Path]:
    workdir.mkdir(parents=True, exist_ok=True)
    parts = asyncio.run(_synthesise(scenes, workdir))
    spoken_wavs: list[Path] = []
    for index, part in enumerate(parts, 1):
        spoken_wav = workdir / f"voice_scene_{index:02d}.wav"
        _run([ffmpeg, "-y", "-i", str(part), "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(spoken_wav)])
        spoken_wavs.append(spoken_wav)
    durations = [_wav_duration(part) for part in spoken_wavs]
    timed = apply_audio_timings(scenes, durations)

    concat_file = workdir / "voice_concat.txt"
    intro = workdir / "intro_pause.wav"
    _run([ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "0.75", str(intro)])
    lines: list[str] = [f"file '{intro.as_posix()}'"]
    for index, (spoken_wav, scene, spoken_duration) in enumerate(zip(spoken_wavs, timed, durations), 1):
        gap = workdir / f"scene_gap_{index:02d}.wav"
        gap_duration = max(0.25, scene.duration - spoken_duration)
        _run([ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", f"{gap_duration:.3f}", str(gap)])
        lines.extend([f"file '{spoken_wav.as_posix()}'", f"file '{gap.as_posix()}'"])
    concat_file.write_text("\n".join(lines), encoding="utf-8")
    output = workdir / "voice.wav"
    _run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(output)])
    return timed, output


def generate_corporate_music(output: Path, duration: float, sample_rate: int = 48000) -> Path:
    """Generate an original, unobtrusive ambient corporate bed without external assets."""
    count = int(duration * sample_rate)
    t = np.arange(count, dtype=np.float64) / sample_rate
    music = np.zeros(count, dtype=np.float64)
    progression = [(130.81, 164.81, 196.00), (110.00, 146.83, 174.61), (87.31, 130.81, 164.81), (98.00, 123.47, 146.83)]
    block = 8.0
    for index, chord in enumerate(progression * (int(duration / (block * 4)) + 2)):
        start = int(index * block * sample_rate)
        if start >= count:
            break
        end = min(count, start + int(block * sample_rate))
        local = t[start:end] - t[start]
        envelope = np.sin(np.pi * np.clip(local / block, 0, 1)) ** 1.5
        pad = sum(np.sin(2 * np.pi * frequency * local) for frequency in chord) / len(chord)
        shimmer = np.sin(2 * np.pi * chord[-1] * 2 * local) * 0.08
        music[start:end] += (pad * 0.15 + shimmer) * envelope
    # Soft rhythmic pulse, deliberately below speech frequencies.
    pulse = (0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * t)) ** 8
    music += 0.025 * pulse * np.sin(2 * np.pi * 65.41 * t)
    fade = min(int(2.5 * sample_rate), count // 2)
    if fade:
        music[:fade] *= np.linspace(0, 1, fade)
        music[-fade:] *= np.linspace(1, 0, fade)
    pcm = np.int16(np.clip(music, -1, 1) * 32767)
    with wave.open(str(output), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(pcm.tobytes())
    return output
