"""
Audio chunking for processing large files.

Splits audio into overlapping chunks for memory-efficient transcription.
"""
import subprocess
from pathlib import Path
from typing import List, Optional, Callable
import sys

from ..core.config import get_config
from ..core.types import Chunk, ChunkStatus
from ..core.exceptions import ChunkingError
from ..utils.ffmpeg import require_ffmpeg
from ..utils.paths import PathManager
from ..logging import get_logger

logger = get_logger("audio.chunker")


class AudioChunker:
    """
    Splits audio files into overlapping chunks.

    Features:
    - FFmpeg-based splitting (no memory loading)
    - Configurable chunk duration and overlap
    - Handles edge cases (short files, odd durations)
    """

    def __init__(
        self,
        chunk_duration: int = 300,
        overlap: int = 10,
        min_chunk: int = 30,
    ):
        """
        Initialize audio chunker.

        Args:
            chunk_duration: Target chunk duration in seconds (default: 5 min)
            overlap: Overlap between chunks in seconds (default: 10s)
            min_chunk: Minimum chunk size in seconds (default: 30s)
        """
        self.chunk_duration = chunk_duration
        self.overlap = overlap
        self.min_chunk = min_chunk

        self.ffmpeg_path, _ = require_ffmpeg()

    def calculate_chunks(self, duration: float) -> List[Chunk]:
        """
        Calculate chunk boundaries for an audio file.

        Args:
            duration: Total audio duration in seconds

        Returns:
            List of Chunk objects with timing information
        """
        if duration <= 0:
            return []

        # If audio is shorter than chunk duration, single chunk
        if duration <= self.chunk_duration:
            return [Chunk(
                index=0,
                start_time=0.0,
                end_time=duration,
                overlap_start=0,
            )]

        chunks = []
        effective_step = self.chunk_duration - self.overlap
        start_time = 0.0
        index = 0

        while start_time < duration:
            end_time = min(start_time + self.chunk_duration, duration)

            # Check if remaining audio is too short
            remaining = duration - start_time
            if remaining < self.min_chunk and index > 0:
                # Extend previous chunk to include remaining
                chunks[-1].end_time = duration
                break

            # Calculate overlap at start (0 for first chunk)
            overlap_start = self.overlap if index > 0 else 0

            chunk = Chunk(
                index=index,
                start_time=start_time,
                end_time=end_time,
                overlap_start=overlap_start,
            )
            chunks.append(chunk)

            start_time += effective_step
            index += 1

        logger.debug(f"Calculated {len(chunks)} chunks for {duration:.1f}s audio")
        return chunks

    def split_audio(
        self,
        audio_path: Path,
        output_dir: Path,
        chunks: List[Chunk],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Chunk]:
        """
        Split audio file into chunks.

        Args:
            audio_path: Input audio file
            output_dir: Directory for chunk files
            chunks: List of chunk timing information
            progress_callback: Called with (current, total) for each chunk

        Returns:
            Updated chunks with file paths

        Raises:
            ChunkingError: If splitting fails
        """
        audio_path = PathManager.normalize(audio_path)
        output_dir = PathManager.normalize(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Splitting audio into {len(chunks)} chunks")

        for i, chunk in enumerate(chunks):
            chunk_path = output_dir / f"chunk_{chunk.index:03d}.wav"

            try:
                self._extract_chunk(audio_path, chunk_path, chunk)
                chunk.file_path = chunk_path

                if progress_callback:
                    progress_callback(i + 1, len(chunks))

            except Exception as e:
                logger.error(f"Failed to create chunk {chunk.index}: {e}")
                raise ChunkingError(f"Chunk {chunk.index}: {e}")

        logger.info(f"Created {len(chunks)} audio chunks")
        return chunks

    def _extract_chunk(self, audio_path: Path, output_path: Path, chunk: Chunk):
        """
        Extract a single chunk from audio file.

        Args:
            audio_path: Source audio file
            output_path: Output chunk file
            chunk: Chunk timing information
        """
        duration = chunk.end_time - chunk.start_time

        cmd = [
            self.ffmpeg_path,
            "-y",  # Overwrite
            "-ss", str(chunk.start_time),  # Seek to start
            "-i", PathManager.for_ffmpeg(audio_path),
            "-t", str(duration),  # Duration
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            PathManager.for_ffmpeg(output_path),
        ]

        logger.debug(f"Extracting chunk {chunk.index}: {chunk.start_time:.1f}s - {chunk.end_time:.1f}s")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS if sys.platform == "win32" else 0,
        )

        if result.returncode != 0:
            raise ChunkingError(f"FFmpeg failed: {result.stderr}")

        if not output_path.exists():
            raise ChunkingError(f"Chunk file not created: {output_path}")

    def cleanup_chunks(self, chunks: List[Chunk]) -> int:
        """
        Clean up chunk files.

        Args:
            chunks: List of chunks to clean up

        Returns:
            Number of files deleted
        """
        deleted = 0
        for chunk in chunks:
            if chunk.file_path and chunk.file_path.exists():
                try:
                    chunk.file_path.unlink()
                    deleted += 1
                except Exception as e:
                    logger.warning(f"Could not delete chunk {chunk.index}: {e}")

        logger.debug(f"Cleaned up {deleted} chunk files")
        return deleted

    def cleanup_directory(self, chunks_dir: Path) -> bool:
        """
        Clean up entire chunks directory.

        Args:
            chunks_dir: Directory to remove

        Returns:
            True if successful
        """
        try:
            import shutil
            if chunks_dir.exists():
                shutil.rmtree(chunks_dir)
                logger.debug(f"Removed chunks directory: {chunks_dir}")
                return True
        except Exception as e:
            logger.warning(f"Could not remove {chunks_dir}: {e}")

        return False
