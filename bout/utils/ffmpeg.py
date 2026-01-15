"""
FFmpeg detection and validation utilities.
"""
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from ..core.exceptions import FFmpegNotFoundError


# Common FFmpeg installation paths on Windows
FFMPEG_PATHS = [
    "ffmpeg",  # System PATH
    "C:/ffmpeg/ffmpeg.exe",
    "C:/ffmpeg/bin/ffmpeg.exe",
    "C:/Program Files/ffmpeg/bin/ffmpeg.exe",
]

FFPROBE_PATHS = [
    "ffprobe",
    "C:/ffmpeg/ffprobe.exe",
    "C:/ffmpeg/bin/ffprobe.exe",
    "C:/Program Files/ffmpeg/bin/ffprobe.exe",
]


def find_ffmpeg() -> Tuple[Optional[str], Optional[str]]:
    """
    Find FFmpeg and FFprobe executables.

    Returns:
        Tuple of (ffmpeg_path, ffprobe_path) or (None, None) if not found
    """
    ffmpeg_path = None
    ffprobe_path = None

    # Check system PATH first
    ffmpeg_in_path = shutil.which("ffmpeg")
    if ffmpeg_in_path:
        ffmpeg_path = ffmpeg_in_path

    ffprobe_in_path = shutil.which("ffprobe")
    if ffprobe_in_path:
        ffprobe_path = ffprobe_in_path

    # If not in PATH, check common locations
    if not ffmpeg_path:
        for path in FFMPEG_PATHS[1:]:  # Skip "ffmpeg" (already checked)
            if Path(path).exists():
                ffmpeg_path = path
                break

    if not ffprobe_path:
        for path in FFPROBE_PATHS[1:]:
            if Path(path).exists():
                ffprobe_path = path
                break

    return ffmpeg_path, ffprobe_path


def check_ffmpeg() -> bool:
    """
    Check if FFmpeg is available and working.

    Returns:
        True if FFmpeg is available
    """
    ffmpeg_path, _ = find_ffmpeg()
    if not ffmpeg_path:
        return False

    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def get_ffmpeg_version() -> Optional[str]:
    """
    Get FFmpeg version string.

    Returns:
        Version string or None if not available
    """
    ffmpeg_path, _ = find_ffmpeg()
    if not ffmpeg_path:
        return None

    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # First line contains version
            first_line = result.stdout.split("\n")[0]
            return first_line
    except (subprocess.SubprocessError, OSError):
        pass

    return None


def require_ffmpeg() -> Tuple[str, str]:
    """
    Get FFmpeg paths or raise an error if not found.

    Returns:
        Tuple of (ffmpeg_path, ffprobe_path)

    Raises:
        FFmpegNotFoundError: If FFmpeg is not installed
    """
    ffmpeg_path, ffprobe_path = find_ffmpeg()

    if not ffmpeg_path:
        raise FFmpegNotFoundError()

    # FFprobe is usually installed with FFmpeg
    if not ffprobe_path:
        # Try to derive from ffmpeg path
        ffmpeg_dir = Path(ffmpeg_path).parent
        possible_ffprobe = ffmpeg_dir / "ffprobe.exe"
        if possible_ffprobe.exists():
            ffprobe_path = str(possible_ffprobe)
        else:
            possible_ffprobe = ffmpeg_dir / "ffprobe"
            if possible_ffprobe.exists():
                ffprobe_path = str(possible_ffprobe)

    return ffmpeg_path, ffprobe_path
