"""
Cross-platform path handling utilities.

Handles Windows path quirks and provides safe path operations.
"""
import re
from pathlib import Path
from typing import Union


class PathManager:
    """Cross-platform path utilities."""

    # Characters not allowed in filenames on Windows
    UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*]')

    @staticmethod
    def normalize(path: Union[str, Path]) -> Path:
        """
        Normalize a path to absolute form.

        Args:
            path: Path string or Path object

        Returns:
            Resolved absolute Path
        """
        return Path(path).resolve()

    @staticmethod
    def for_ffmpeg(path: Path) -> str:
        """
        Format a path for FFmpeg commands.

        FFmpeg prefers forward slashes on all platforms.

        Args:
            path: Path object

        Returns:
            String path with forward slashes
        """
        return str(path).replace("\\", "/")

    @classmethod
    def safe_filename(cls, name: str, max_length: int = 100) -> str:
        """
        Create a safe filename by removing problematic characters.

        Args:
            name: Original filename
            max_length: Maximum length for the result

        Returns:
            Safe filename string
        """
        # Remove unsafe characters
        safe = cls.UNSAFE_CHARS.sub("_", name)
        # Replace multiple underscores with single
        safe = re.sub(r"_+", "_", safe)
        # Trim leading/trailing underscores
        safe = safe.strip("_")
        # Limit length
        if len(safe) > max_length:
            safe = safe[:max_length]
        return safe

    @staticmethod
    def ensure_extension(path: Path, extension: str) -> Path:
        """
        Ensure a path has the specified extension.

        Args:
            path: Original path
            extension: Desired extension (with or without dot)

        Returns:
            Path with the extension
        """
        if not extension.startswith("."):
            extension = f".{extension}"
        if path.suffix.lower() != extension.lower():
            return path.with_suffix(extension)
        return path

    @staticmethod
    def get_unique_path(path: Path) -> Path:
        """
        Get a unique path by adding a number suffix if needed.

        Args:
            path: Desired path

        Returns:
            Unique path that doesn't exist
        """
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 1

        while True:
            new_path = parent / f"{stem}_{counter}{suffix}"
            if not new_path.exists():
                return new_path
            counter += 1
