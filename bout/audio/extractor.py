"""
Audio extraction from video files using FFmpeg.

Provides real-time progress tracking by parsing FFmpeg stderr.
"""
import re
import subprocess
from pathlib import Path
from typing import Optional, Callable
import sys

from ..core.config import get_config
from ..core.exceptions import AudioExtractionError, FFmpegNotFoundError
from ..utils.ffmpeg import require_ffmpeg
from ..utils.paths import PathManager
from ..logging import get_logger

logger = get_logger("audio.extractor")


# FFmpeg progress pattern: time=00:05:32.45 (HH:MM:SS.ms)
TIME_PATTERN = re.compile(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})')


def get_video_duration(video_path: Path) -> float:
    """
    Get video duration in seconds using ffprobe.

    Args:
        video_path: Path to video file

    Returns:
        Duration in seconds, or 0 if unable to determine
    """
    try:
        _, ffprobe_path = require_ffmpeg()
        if not ffprobe_path:
            return 0.0

        cmd = [
            ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            PathManager.for_ffmpeg(video_path),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())

    except Exception as e:
        logger.warning(f"Could not get video duration: {e}")

    return 0.0


class AudioExtractor:
    """
    Extracts audio from video files using FFmpeg.

    Features:
    - Real-time progress reporting
    - Configurable output format for Whisper
    - Proper Windows path handling
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        codec: str = "pcm_s16le",
    ):
        """
        Initialize audio extractor.

        Args:
            sample_rate: Output sample rate (16000 for Whisper)
            channels: Number of channels (1 = mono)
            codec: Audio codec (pcm_s16le for WAV)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.codec = codec

        # Verify FFmpeg is available
        self.ffmpeg_path, self.ffprobe_path = require_ffmpeg()

    def extract(
        self,
        video_path: Path,
        output_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> Path:
        """
        Extract audio from video file.

        Args:
            video_path: Input video file
            output_path: Output audio file (auto-generated if None)
            progress_callback: Called with progress percentage (0-100)

        Returns:
            Path to extracted audio file

        Raises:
            AudioExtractionError: If extraction fails
        """
        video_path = PathManager.normalize(video_path)

        # Generate output path if not provided
        if output_path is None:
            config = get_config()
            output_name = f"{video_path.stem}_audio.wav"
            output_path = config.temp_dir / output_name
            output_path.parent.mkdir(parents=True, exist_ok=True)

        output_path = PathManager.normalize(output_path)

        # Get duration for progress tracking
        duration = get_video_duration(video_path)

        logger.info(f"Extracting audio from: {video_path.name}")
        logger.debug(f"Output: {output_path}")
        logger.debug(f"Duration: {duration:.1f}s")

        # Build FFmpeg command
        cmd = [
            self.ffmpeg_path,
            "-y",  # Overwrite output
            "-i", PathManager.for_ffmpeg(video_path),
            "-vn",  # No video
            "-acodec", self.codec,
            "-ar", str(self.sample_rate),
            "-ac", str(self.channels),
            "-progress", "pipe:1",  # Progress to stdout
            PathManager.for_ffmpeg(output_path),
        ]

        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                # Set lower priority on Windows
                creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS if sys.platform == "win32" else 0,
            )

            # Parse progress from stdout (FFmpeg outputs progress there with -progress pipe:1)
            stderr_output = []
            for line in process.stdout:
                # Look for time in progress output
                if line.startswith("out_time="):
                    time_str = line.split("=")[1].strip()
                    try:
                        parts = time_str.split(":")
                        if len(parts) == 3:
                            hours = int(parts[0])
                            mins = int(parts[1])
                            secs = float(parts[2])
                            current_time = hours * 3600 + mins * 60 + secs

                            if duration > 0 and progress_callback:
                                progress = min(100, (current_time / duration) * 100)
                                progress_callback(progress)
                    except (ValueError, IndexError):
                        pass

            # Wait for process to complete
            _, stderr = process.communicate()
            stderr_output.append(stderr)

            if process.returncode != 0:
                raise AudioExtractionError(str(video_path), stderr)

            # Verify output exists
            if not output_path.exists():
                raise AudioExtractionError(str(video_path), "Output file not created")

            logger.info(f"Audio extracted: {output_path.name}")

            if progress_callback:
                progress_callback(100)

            return output_path

        except subprocess.SubprocessError as e:
            raise AudioExtractionError(str(video_path), str(e))

    def cleanup(self, audio_path: Path) -> bool:
        """
        Clean up temporary audio file.

        Args:
            audio_path: Audio file to delete

        Returns:
            True if deleted successfully
        """
        try:
            if audio_path.exists():
                audio_path.unlink()
                logger.debug(f"Cleaned up: {audio_path}")
                return True
        except Exception as e:
            logger.warning(f"Could not clean up {audio_path}: {e}")

        return False
