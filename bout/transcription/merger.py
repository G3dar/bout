"""
Chunk transcription merging.

Handles overlap deduplication and timestamp adjustment.
"""
from typing import List
from difflib import SequenceMatcher

from ..core.types import Chunk, TranscriptionSegment
from ..logging import get_logger

logger = get_logger("transcription.merger")


class ChunkMerger:
    """
    Merges transcriptions from overlapping chunks.

    Features:
    - Overlap deduplication using fuzzy matching
    - Timestamp continuity adjustment
    - Handles various chunk configurations
    """

    def __init__(self, overlap_seconds: float = 10.0):
        """
        Initialize merger.

        Args:
            overlap_seconds: Expected overlap duration between chunks
        """
        self.overlap_seconds = overlap_seconds

    def merge_chunks(self, chunks: List[Chunk]) -> tuple[str, List[TranscriptionSegment]]:
        """
        Merge transcriptions from all chunks.

        Args:
            chunks: List of transcribed chunks (must be sorted by index)

        Returns:
            Tuple of (full_text, all_segments)
        """
        if not chunks:
            return "", []

        # Sort by index
        chunks = sorted(chunks, key=lambda c: c.index)

        # Filter to completed chunks only
        completed = [c for c in chunks if c.text is not None]
        if not completed:
            return "", []

        # Single chunk case
        if len(completed) == 1:
            return completed[0].text, completed[0].segments

        logger.info(f"Merging {len(completed)} chunk transcriptions")

        all_segments: List[TranscriptionSegment] = []
        full_text_parts: List[str] = []

        for i, chunk in enumerate(completed):
            if i == 0:
                # First chunk: include everything
                segments = self._filter_segments_first_chunk(chunk)
            elif i == len(completed) - 1:
                # Last chunk: skip overlap at start
                segments = self._filter_segments_last_chunk(chunk)
            else:
                # Middle chunks: skip overlap at both ends
                segments = self._filter_segments_middle_chunk(chunk)

            all_segments.extend(segments)
            chunk_text = " ".join(s.text for s in segments)
            full_text_parts.append(chunk_text)

        # Sort all segments by start time
        all_segments.sort(key=lambda s: s.start)

        # Join text parts
        full_text = " ".join(full_text_parts)

        # Clean up extra whitespace
        full_text = " ".join(full_text.split())

        logger.info(f"Merged result: {len(full_text)} chars, {len(all_segments)} segments")

        return full_text, all_segments

    def _filter_segments_first_chunk(self, chunk: Chunk) -> List[TranscriptionSegment]:
        """
        Filter segments for first chunk.

        Includes everything up to the overlap boundary.
        """
        cutoff = chunk.end_time - self.overlap_seconds
        filtered = []

        for seg in chunk.segments:
            if seg.end <= cutoff:
                # Fully before cutoff - include
                filtered.append(seg)
            elif seg.start < cutoff:
                # Crosses cutoff - include if midpoint is before cutoff
                midpoint = (seg.start + seg.end) / 2
                if midpoint < cutoff:
                    filtered.append(seg)

        return filtered

    def _filter_segments_last_chunk(self, chunk: Chunk) -> List[TranscriptionSegment]:
        """
        Filter segments for last chunk.

        Skips overlap at the start.
        """
        # Account for overlap at start
        skip_until = chunk.start_time + chunk.overlap_start
        filtered = []

        for seg in chunk.segments:
            if seg.start >= skip_until:
                # Fully after skip point - include
                filtered.append(seg)
            elif seg.end > skip_until:
                # Crosses skip point - include if midpoint is after skip
                midpoint = (seg.start + seg.end) / 2
                if midpoint >= skip_until:
                    filtered.append(seg)

        return filtered

    def _filter_segments_middle_chunk(self, chunk: Chunk) -> List[TranscriptionSegment]:
        """
        Filter segments for middle chunks.

        Skips overlap at both ends.
        """
        skip_until = chunk.start_time + chunk.overlap_start
        cutoff = chunk.end_time - self.overlap_seconds
        filtered = []

        for seg in chunk.segments:
            midpoint = (seg.start + seg.end) / 2

            # Check if segment is in the valid range
            if seg.start >= skip_until and seg.end <= cutoff:
                filtered.append(seg)
            elif midpoint >= skip_until and midpoint <= cutoff:
                # Partially in range - include if midpoint is valid
                filtered.append(seg)

        return filtered

    def merge_text_simple(self, chunks: List[Chunk]) -> str:
        """
        Simple text merge without segment handling.

        Uses fuzzy matching to remove duplicate text at boundaries.

        Args:
            chunks: List of transcribed chunks

        Returns:
            Merged full text
        """
        if not chunks:
            return ""

        completed = sorted(
            [c for c in chunks if c.text],
            key=lambda c: c.index
        )

        if not completed:
            return ""

        if len(completed) == 1:
            return completed[0].text

        merged_parts = [completed[0].text]

        for i in range(1, len(completed)):
            prev_text = merged_parts[-1]
            curr_text = completed[i].text

            # Find overlap using fuzzy matching
            overlap_chars = self._find_text_overlap(prev_text, curr_text)

            if overlap_chars > 0:
                # Skip the overlapping part from current text
                curr_text = curr_text[overlap_chars:]

            merged_parts.append(curr_text)

        result = " ".join(merged_parts)
        return " ".join(result.split())

    def _find_text_overlap(
        self,
        text1: str,
        text2: str,
        max_check: int = 500,
    ) -> int:
        """
        Find overlapping text between end of text1 and start of text2.

        Args:
            text1: First text (check ending)
            text2: Second text (check beginning)
            max_check: Maximum characters to check

        Returns:
            Number of characters that overlap
        """
        # Get endings of text1 and beginnings of text2
        end1 = text1[-max_check:] if len(text1) > max_check else text1
        start2 = text2[:max_check] if len(text2) > max_check else text2

        # Try different overlap lengths
        best_overlap = 0
        best_ratio = 0.0

        for length in range(min(len(end1), len(start2), 200), 10, -10):
            candidate1 = end1[-length:]
            candidate2 = start2[:length]

            ratio = SequenceMatcher(None, candidate1, candidate2).ratio()

            if ratio > 0.8 and ratio > best_ratio:
                best_ratio = ratio
                best_overlap = length

        return best_overlap
