"""One-click orchestration for the DQIP AI storytelling video generator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from sample_script import DEMO_SCENES
from scene_manager import clamp_demo_duration
from screen_recorder import record_application
from subtitle_generator import generate_srt
from video_renderer import render_video
from voice_generator import generate_corporate_music, generate_voice


@dataclass(frozen=True)
class DemoArtifacts:
    video: Path
    subtitles: Path
    voice: Path


def _find_binary(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    try:
        import imageio_ffmpeg
        ffmpeg = Path(imageio_ffmpeg.get_ffmpeg_exe())
        if name == "ffmpeg":
            return str(ffmpeg)
        candidate = ffmpeg.with_name("ffprobe" + ffmpeg.suffix)
        if candidate.is_file():
            return str(candidate)
    except Exception:
        pass
    raise RuntimeError(f"{name} is required. Install FFmpeg and ensure {name} is on PATH.")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_app(url: str, process: subprocess.Popen, timeout: float = 90.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("The recording Streamlit process stopped before becoming ready.")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except Exception:
            time.sleep(0.75)
    raise TimeoutError("Timed out while starting the local recording application.")


def _start_streamlit(project: Path, port: int) -> subprocess.Popen:
    environment = os.environ.copy()
    environment["DQIP_STORYTELLING_CHILD"] = "1"
    environment["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    environment["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    command = [
        sys.executable, "-m", "streamlit", "run", str(project / "app.py"),
        "--server.address=127.0.0.1", f"--server.port={port}",
        "--server.headless=true", "--server.enableCORS=false", "--server.enableXsrfProtection=false",
        "--global.developmentMode=false",
    ]
    return subprocess.Popen(command, cwd=str(project), env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def generate_demo_video(project_dir: str | Path | None = None, output_dir: str | Path | None = None) -> DemoArtifacts:
    project = Path(project_dir or Path(__file__).resolve().parent).resolve()
    destination = Path(output_dir or project / "generated_demo").resolve()
    destination.mkdir(parents=True, exist_ok=True)
    ffmpeg = _find_binary("ffmpeg")

    with tempfile.TemporaryDirectory(prefix="dqip_storytelling_") as temporary:
        workdir = Path(temporary)
        timed_scenes, voice = generate_voice(DEMO_SCENES, workdir, ffmpeg)
        duration = clamp_demo_duration(timed_scenes)
        subtitles = generate_srt(timed_scenes, workdir / "demo_storytelling_video.srt")
        music = generate_corporate_music(workdir / "corporate_music.wav", duration)

        port = _free_port()
        process = _start_streamlit(project, port)
        try:
            url = f"http://127.0.0.1:{port}"
            _wait_for_app(url, process)
            recording, recording_offset = record_application(url, timed_scenes, project / "SQC Data.xls", workdir)
        finally:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()

        video_output = destination / "demo_storytelling_video.mp4"
        srt_output = destination / "demo_storytelling_video.srt"
        voice_output = destination / "voice.wav"
        shutil.copy2(subtitles, srt_output)
        shutil.copy2(voice, voice_output)
        render_video(recording, voice, music, subtitles, video_output, ffmpeg, duration, recording_offset)
    return DemoArtifacts(video=video_output, subtitles=srt_output, voice=voice_output)
