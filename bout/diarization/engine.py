"""
Speaker diarization using pyannote.audio.

Identifies different speakers in audio files.
"""
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from ..core.config import get_config
from ..core.types import TranscriptionSegment
from ..utils.system import cleanup_gpu_memory, get_memory_info
from ..logging import get_logger

logger = get_logger("diarization.engine")


class DiarizationEngine:
    """
    Speaker diarization using pyannote.

    Features:
    - Automatic speaker detection
    - GPU acceleration
    - Integration with transcription segments
    """

    def __init__(self, hf_token: Optional[str] = None):
        """
        Initialize diarization engine.

        Args:
            hf_token: HuggingFace token (from config/env if None)
        """
        config = get_config()
        # Priority: parameter > environment > config
        self.hf_token = hf_token or os.environ.get("HF_TOKEN") or config.diarization.hf_token
        self.pipeline = None
        self.device = None

    def is_available(self) -> bool:
        """Check if diarization is available (token configured)."""
        return bool(self.hf_token)

    def _detect_device(self) -> str:
        """Detect best available device."""
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        return "cpu"

    def load_pipeline(self):
        """
        Load the pyannote diarization pipeline.

        Raises:
            RuntimeError: If token is not configured or loading fails
        """
        if self.pipeline is not None:
            return

        if not self.hf_token:
            raise RuntimeError(
                "HuggingFace token not configured. "
                "Set HF_TOKEN environment variable."
            )

        self.device = self._detect_device()
        logger.info(f"Loading diarization pipeline on {self.device}")

        try:
            from pyannote.audio import Pipeline
            import torch

            # Set HF_TOKEN in environment for huggingface_hub
            os.environ["HF_TOKEN"] = self.hf_token
            os.environ["HUGGING_FACE_HUB_TOKEN"] = self.hf_token

            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token,
            )

            if self.device == "cuda":
                self.pipeline.to(torch.device("cuda"))

            logger.info("Diarization pipeline loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load diarization pipeline: {e}")
            raise RuntimeError(f"Diarization loading failed: {e}")

    def unload_pipeline(self):
        """Unload pipeline and free memory."""
        if self.pipeline is not None:
            del self.pipeline
            self.pipeline = None
            cleanup_gpu_memory()
            logger.debug("Diarization pipeline unloaded")

    def diarize(self, audio_path: Path) -> List[Dict[str, Any]]:
        """
        Perform speaker diarization on audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            List of segments with speaker labels:
            [{"start": float, "end": float, "speaker": str}, ...]
        """
        self.load_pipeline()

        logger.info(f"Diarizing: {audio_path.name}")

        try:
            # Run diarization
            diarization = self.pipeline(str(audio_path))

            # Extract segments
            segments = []
            speaker_map = {}
            speaker_counter = 1

            for turn, _, speaker in diarization.itertracks(yield_label=True):
                # Map speaker IDs to friendly names
                if speaker not in speaker_map:
                    speaker_map[speaker] = f"Hablante {speaker_counter}"
                    speaker_counter += 1

                segments.append({
                    "start": turn.start,
                    "end": turn.end,
                    "speaker": speaker_map[speaker],
                })

            logger.info(f"Found {len(speaker_map)} speakers, {len(segments)} segments")
            return segments

        except Exception as e:
            logger.error(f"Diarization failed: {e}")
            raise

    def merge_with_transcription(
        self,
        transcription_segments: List[TranscriptionSegment],
        diarization_segments: List[Dict[str, Any]],
    ) -> List[TranscriptionSegment]:
        """
        Merge transcription with diarization results.

        Assigns speaker labels to transcription segments based on timing overlap.

        Args:
            transcription_segments: Segments from Whisper
            diarization_segments: Segments from diarization

        Returns:
            Transcription segments with speaker labels added
        """
        logger.debug("Merging transcription with diarization")

        for trans_seg in transcription_segments:
            # Find the diarization segment with maximum overlap
            best_speaker = None
            best_overlap = 0.0

            for diar_seg in diarization_segments:
                # Calculate overlap
                overlap_start = max(trans_seg.start, diar_seg["start"])
                overlap_end = min(trans_seg.end, diar_seg["end"])
                overlap = max(0, overlap_end - overlap_start)

                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = diar_seg["speaker"]

            trans_seg.speaker = best_speaker or "Hablante"

        return transcription_segments

    def consolidate_segments(
        self,
        segments: List[TranscriptionSegment],
        gap_threshold: float = 1.0,
    ) -> List[TranscriptionSegment]:
        """
        Consolidate consecutive segments from the same speaker.

        Args:
            segments: Transcription segments with speaker labels
            gap_threshold: Maximum gap to merge (seconds)

        Returns:
            Consolidated segments
        """
        if not segments:
            return []

        consolidated = []
        current = segments[0]

        for seg in segments[1:]:
            # Check if we should merge
            same_speaker = seg.speaker == current.speaker
            small_gap = (seg.start - current.end) <= gap_threshold

            if same_speaker and small_gap:
                # Merge: extend current segment
                current.end = seg.end
                current.text = current.text + " " + seg.text
            else:
                # Start new segment
                consolidated.append(current)
                current = TranscriptionSegment(
                    start=seg.start,
                    end=seg.end,
                    text=seg.text,
                    speaker=seg.speaker,
                )

        consolidated.append(current)

        logger.debug(f"Consolidated {len(segments)} -> {len(consolidated)} segments")
        return consolidated
