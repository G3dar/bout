"""
Whisper transcription engine.

Provides chunked transcription with memory management.
"""
import gc
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any

from ..core.config import get_config
from ..core.types import Chunk, ChunkStatus, TranscriptionSegment
from ..core.exceptions import ModelLoadError, OutOfMemoryError, TranscriptionError
from ..utils.system import cleanup_gpu_memory, get_memory_info
from ..logging import get_logger

logger = get_logger("transcription.engine")


class TranscriptionEngine:
    """
    Whisper-based transcription engine.

    Features:
    - Lazy model loading
    - GPU memory management
    - Per-chunk transcription with checkpointing
    - Automatic OOM recovery
    """

    def __init__(
        self,
        model_name: str = "medium",
        language: str = "es",
        device: str = "auto",
    ):
        """
        Initialize transcription engine.

        Args:
            model_name: Whisper model (tiny, base, small, medium, large)
            language: Target language code
            device: Processing device (auto, cuda, cpu)
        """
        self.model_name = model_name
        self.language = language
        self.requested_device = device

        self.model = None
        self.device = None

    def _detect_device(self) -> str:
        """Detect best available device."""
        if self.requested_device != "auto":
            return self.requested_device

        try:
            import torch
            if torch.cuda.is_available():
                mem = get_memory_info()
                if mem.gpu_available_mb and mem.gpu_available_mb > 1000:
                    logger.info(f"Using GPU: {mem.gpu_name}")
                    return "cuda"
        except ImportError:
            pass

        logger.info("Using CPU")
        return "cpu"

    def load_model(self):
        """
        Load Whisper model into memory.

        Raises:
            ModelLoadError: If model loading fails
        """
        if self.model is not None:
            return

        self.device = self._detect_device()

        logger.info(f"Loading Whisper model '{self.model_name}' on {self.device}")

        try:
            import whisper
            self.model = whisper.load_model(self.model_name, device=self.device)
            logger.info("Model loaded successfully")

        except Exception as e:
            raise ModelLoadError(self.model_name, str(e))

    def unload_model(self):
        """Unload model and free memory."""
        if self.model is not None:
            del self.model
            self.model = None
            cleanup_gpu_memory()
            logger.debug("Model unloaded")

    def transcribe_chunk(
        self,
        chunk: Chunk,
        max_retries: int = 3,
    ) -> Chunk:
        """
        Transcribe a single audio chunk.

        Args:
            chunk: Chunk with file_path set
            max_retries: Number of retries on OOM

        Returns:
            Updated chunk with transcription

        Raises:
            TranscriptionError: If transcription fails
        """
        if chunk.file_path is None or not chunk.file_path.exists():
            raise TranscriptionError(f"Chunk file not found: {chunk.file_path}")

        self.load_model()

        logger.debug(f"Transcribing chunk {chunk.index}: {chunk.file_path.name}")

        for attempt in range(max_retries):
            try:
                # Clean up before each attempt
                cleanup_gpu_memory()

                result = self.model.transcribe(
                    str(chunk.file_path),
                    language=self.language,
                    task="transcribe",
                    verbose=False,
                )

                # Extract segments
                segments = []
                for seg in result.get("segments", []):
                    # Adjust times relative to original audio
                    start = chunk.start_time + seg["start"]
                    end = chunk.start_time + seg["end"]

                    segments.append(TranscriptionSegment(
                        start=start,
                        end=end,
                        text=seg["text"].strip(),
                    ))

                chunk.text = result.get("text", "").strip()
                chunk.segments = segments
                chunk.status = ChunkStatus.COMPLETED

                from datetime import datetime
                chunk.completed_at = datetime.now()

                logger.debug(f"Chunk {chunk.index} transcribed: {len(chunk.text)} chars")
                return chunk

            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    logger.warning(f"OOM on chunk {chunk.index}, attempt {attempt + 1}/{max_retries}")
                    cleanup_gpu_memory()

                    if attempt == max_retries - 1:
                        # Last resort: try on CPU
                        if self.device != "cpu":
                            logger.warning("Falling back to CPU for this chunk")
                            return self._transcribe_on_cpu(chunk)
                        raise OutOfMemoryError()
                else:
                    raise TranscriptionError(f"Chunk {chunk.index}: {e}")

        chunk.status = ChunkStatus.FAILED
        chunk.error = "Max retries exceeded"
        return chunk

    def _transcribe_on_cpu(self, chunk: Chunk) -> Chunk:
        """
        Transcribe chunk on CPU as fallback.

        Args:
            chunk: Chunk to transcribe

        Returns:
            Updated chunk
        """
        try:
            import whisper

            # Unload GPU model
            self.unload_model()

            # Load CPU model
            cpu_model = whisper.load_model(self.model_name, device="cpu")

            result = cpu_model.transcribe(
                str(chunk.file_path),
                language=self.language,
                task="transcribe",
                verbose=False,
            )

            # Extract segments
            segments = []
            for seg in result.get("segments", []):
                start = chunk.start_time + seg["start"]
                end = chunk.start_time + seg["end"]
                segments.append(TranscriptionSegment(
                    start=start,
                    end=end,
                    text=seg["text"].strip(),
                ))

            chunk.text = result.get("text", "").strip()
            chunk.segments = segments
            chunk.status = ChunkStatus.COMPLETED

            from datetime import datetime
            chunk.completed_at = datetime.now()

            # Clean up CPU model
            del cpu_model
            gc.collect()

            # Reload GPU model for next chunk
            self.load_model()

            return chunk

        except Exception as e:
            chunk.status = ChunkStatus.FAILED
            chunk.error = str(e)
            return chunk

    def transcribe_all_chunks(
        self,
        chunks: List[Chunk],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        checkpoint_callback: Optional[Callable[[Chunk], None]] = None,
    ) -> List[Chunk]:
        """
        Transcribe all chunks with progress tracking.

        Args:
            chunks: List of chunks to transcribe
            progress_callback: Called with (current, total) after each chunk
            checkpoint_callback: Called after each chunk for saving state

        Returns:
            List of transcribed chunks
        """
        self.load_model()

        total = len(chunks)
        completed = 0

        for chunk in chunks:
            # Skip already completed chunks (for resume)
            if chunk.status == ChunkStatus.COMPLETED:
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)
                continue

            # Transcribe chunk
            chunk = self.transcribe_chunk(chunk)

            # Checkpoint
            if checkpoint_callback:
                checkpoint_callback(chunk)

            completed += 1
            if progress_callback:
                progress_callback(completed, total)

            # Clean up memory between chunks
            cleanup_gpu_memory()

        return chunks
