"""
Custom exceptions for BOUT.

Provides meaningful error messages and suggestions for common issues.
"""
from typing import List, Optional


class BoutError(Exception):
    """Base exception for BOUT errors."""

    def __init__(self, message: str, suggestions: Optional[List[str]] = None):
        super().__init__(message)
        self.message = message
        self.suggestions = suggestions or []


class FFmpegError(BoutError):
    """FFmpeg-related errors."""

    def __init__(self, message: str):
        super().__init__(
            message,
            suggestions=[
                "Ensure FFmpeg is installed: https://ffmpeg.org/download.html",
                "Add FFmpeg to your system PATH",
                "Or set FFMPEG_PATH environment variable",
            ]
        )


class FFmpegNotFoundError(FFmpegError):
    """FFmpeg executable not found."""

    def __init__(self):
        super().__init__("FFmpeg not found. Please install FFmpeg to process videos.")


class AudioExtractionError(FFmpegError):
    """Failed to extract audio from video."""

    def __init__(self, video_path: str, stderr: str = ""):
        message = f"Failed to extract audio from: {video_path}"
        if stderr:
            message += f"\nFFmpeg error: {stderr[:500]}"
        super().__init__(message)


class TranscriptionError(BoutError):
    """Transcription-related errors."""
    pass


class ModelLoadError(TranscriptionError):
    """Failed to load Whisper model."""

    def __init__(self, model_name: str, error: str = ""):
        super().__init__(
            f"Failed to load Whisper model '{model_name}': {error}",
            suggestions=[
                "Check your internet connection for model download",
                "Try a smaller model: tiny, base, small",
                "Ensure you have enough disk space",
            ]
        )


class OutOfMemoryError(TranscriptionError):
    """GPU memory exhausted."""

    def __init__(self):
        super().__init__(
            "GPU memory exhausted during transcription",
            suggestions=[
                "Use a smaller Whisper model (e.g., 'small' instead of 'medium')",
                "Close other GPU-intensive applications",
                "Set BOUT_DEVICE=cpu to use CPU instead",
                "Reduce chunk size with BOUT_CHUNK_DURATION",
            ]
        )


class VideoNotFoundError(BoutError):
    """Video file not found."""

    def __init__(self, video_path: str):
        super().__init__(
            f"Video file not found: {video_path}",
            suggestions=[
                "Check the file path is correct",
                "Ensure the file exists and is accessible",
            ]
        )


class UnsupportedVideoError(BoutError):
    """Unsupported video format."""

    def __init__(self, video_path: str, extension: str):
        super().__init__(
            f"Unsupported video format: {extension}",
            suggestions=[
                "Supported formats: mp4, avi, mkv, mov, webm, m4v, wmv, flv",
                "Convert the video using FFmpeg or HandBrake",
            ]
        )


class JobNotFoundError(BoutError):
    """Job not found in state manager."""

    def __init__(self, job_id: str):
        super().__init__(
            f"Job not found: {job_id}",
            suggestions=[
                "Check the job ID is correct",
                "Use 'bout jobs list' to see available jobs",
            ]
        )


class ChunkingError(BoutError):
    """Error during audio chunking."""

    def __init__(self, message: str):
        super().__init__(
            f"Audio chunking failed: {message}",
            suggestions=[
                "Check disk space in temp directory",
                "Ensure the audio file is not corrupted",
            ]
        )
