"""Final H.264/AAC composition, audio ducking, and subtitle burn-in."""

from __future__ import annotations

from pathlib import Path
import subprocess


class RenderingError(RuntimeError):
    pass


def _subtitle_filter(path: Path) -> str:
    escaped = path.name.replace("'", r"\'")
    style = "FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00111A24,BorderStyle=1,Outline=2,Shadow=1,MarginV=34,Alignment=2"
    return f"scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,subtitles='{escaped}':force_style='{style}'"


def render_video(
    screen_video: Path,
    voice: Path,
    music: Path,
    subtitles: Path,
    output: Path,
    ffmpeg: str,
    duration: float,
    video_offset: float = 0.0,
) -> Path:
    screen_video = screen_video.resolve()
    voice = voice.resolve()
    music = music.resolve()
    subtitles = subtitles.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg, "-y",
        "-ss", f"{max(0.0, video_offset):.3f}", "-i", str(screen_video),
        "-i", str(voice),
        "-stream_loop", "-1", "-i", str(music),
        "-filter_complex",
        "[2:a]volume=0.16[music];"
        "[music][1:a]sidechaincompress=threshold=0.018:ratio=10:attack=25:release=650[ducked];"
        "[1:a][ducked]amix=inputs=2:duration=first:dropout_transition=1,"
        "loudnorm=I=-16:LRA=9:TP=-1.5[audio]",
        "-map", "0:v:0", "-map", "[audio]",
        "-t", f"{duration:.3f}",
        "-vf", _subtitle_filter(subtitles),
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        str(output),
    ]
    completed = subprocess.run(command, cwd=str(subtitles.parent), capture_output=True, text=True)
    if completed.returncode:
        raise RenderingError(completed.stderr[-5000:])
    if not output.is_file() or output.stat().st_size < 1_024:
        raise RenderingError("The video renderer did not produce a valid MP4 file.")
    return output
