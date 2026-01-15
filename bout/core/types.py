"""
Type definitions for BOUT.

Dataclasses for jobs, chunks, and transcription results.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any
import uuid


class JobStatus(str, Enum):
    """Job lifecycle states."""
    PENDING = "pending"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    TRANSCRIBING = "transcribing"
    MERGING = "merging"
    DIARIZING = "diarizing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChunkStatus(str, Enum):
    """Chunk processing states."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TranscriptionSegment:
    """A segment of transcribed text with timing."""
    start: float           # Start time in seconds
    end: float             # End time in seconds
    text: str              # Transcribed text
    speaker: Optional[str] = None  # Speaker label if diarization enabled


@dataclass
class Chunk:
    """Audio chunk information."""
    index: int
    start_time: float      # Start time in original audio (seconds)
    end_time: float        # End time in original audio (seconds)
    overlap_start: float   # Overlap at start (seconds)
    file_path: Optional[Path] = None
    status: ChunkStatus = ChunkStatus.PENDING

    # Transcription result
    text: Optional[str] = None
    segments: List[TranscriptionSegment] = field(default_factory=list)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    @property
    def duration(self) -> float:
        """Chunk duration in seconds."""
        return self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "index": self.index,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "overlap_start": self.overlap_start,
            "file_path": str(self.file_path) if self.file_path else None,
            "status": self.status.value,
            "text": self.text,
            "segments": [
                {"start": s.start, "end": s.end, "text": s.text, "speaker": s.speaker}
                for s in self.segments
            ],
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Chunk":
        """Create from dictionary."""
        segments = [
            TranscriptionSegment(**s) for s in data.get("segments", [])
        ]
        return cls(
            index=data["index"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            overlap_start=data["overlap_start"],
            file_path=Path(data["file_path"]) if data.get("file_path") else None,
            status=ChunkStatus(data.get("status", "pending")),
            text=data.get("text"),
            segments=segments,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            error=data.get("error"),
        )


@dataclass
class Job:
    """Transcription job information."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    video_path: Optional[Path] = None
    video_name: str = ""

    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    duration_seconds: float = 0.0

    # State
    status: JobStatus = JobStatus.PENDING
    error: Optional[str] = None

    # Audio
    audio_path: Optional[Path] = None

    # Chunks
    chunks: List[Chunk] = field(default_factory=list)

    # Output
    output_path: Optional[Path] = None
    transcription_text: Optional[str] = None
    segments: List[TranscriptionSegment] = field(default_factory=list)

    @property
    def total_chunks(self) -> int:
        """Total number of chunks."""
        return len(self.chunks)

    @property
    def completed_chunks(self) -> int:
        """Number of completed chunks."""
        return sum(1 for c in self.chunks if c.status == ChunkStatus.COMPLETED)

    @property
    def progress(self) -> float:
        """Job progress as a fraction (0.0 - 1.0)."""
        if self.status == JobStatus.COMPLETED:
            return 1.0
        if self.status == JobStatus.FAILED:
            return 0.0
        if not self.chunks:
            return 0.0
        return self.completed_chunks / self.total_chunks

    def update(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "video_path": str(self.video_path) if self.video_path else None,
            "video_name": self.video_name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "status": self.status.value,
            "error": self.error,
            "audio_path": str(self.audio_path) if self.audio_path else None,
            "chunks": [c.to_dict() for c in self.chunks],
            "output_path": str(self.output_path) if self.output_path else None,
            "transcription_text": self.transcription_text,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Create from dictionary."""
        chunks = [Chunk.from_dict(c) for c in data.get("chunks", [])]
        return cls(
            id=data["id"],
            video_path=Path(data["video_path"]) if data.get("video_path") else None,
            video_name=data.get("video_name", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            duration_seconds=data.get("duration_seconds", 0.0),
            status=JobStatus(data.get("status", "pending")),
            error=data.get("error"),
            audio_path=Path(data["audio_path"]) if data.get("audio_path") else None,
            chunks=chunks,
            output_path=Path(data["output_path"]) if data.get("output_path") else None,
            transcription_text=data.get("transcription_text"),
        )
