"""
State models for job persistence.

Extends core types with serialization support.
"""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from ..core.types import Job, Chunk, JobStatus


@dataclass
class JobState:
    """
    Serializable job state for persistence.

    Includes all data needed to resume a job.
    """
    # Job identity
    job_id: str
    video_path: str
    video_name: str

    # Timing
    created_at: str
    updated_at: str
    duration_seconds: float

    # Status
    status: str
    error: Optional[str] = None

    # Audio
    audio_path: Optional[str] = None

    # Chunking
    chunks_dir: Optional[str] = None
    chunk_config: Dict[str, Any] = field(default_factory=dict)
    chunks: List[Dict[str, Any]] = field(default_factory=list)

    # Output
    output_path: Optional[str] = None
    transcription_text: Optional[str] = None

    def to_job(self) -> Job:
        """Convert to Job object."""
        job = Job(
            id=self.job_id,
            video_path=Path(self.video_path) if self.video_path else None,
            video_name=self.video_name,
            created_at=datetime.fromisoformat(self.created_at),
            updated_at=datetime.fromisoformat(self.updated_at),
            duration_seconds=self.duration_seconds,
            status=JobStatus(self.status),
            error=self.error,
            audio_path=Path(self.audio_path) if self.audio_path else None,
            chunks=[Chunk.from_dict(c) for c in self.chunks],
            output_path=Path(self.output_path) if self.output_path else None,
            transcription_text=self.transcription_text,
        )
        return job

    @classmethod
    def from_job(cls, job: Job, chunks_dir: Optional[Path] = None) -> "JobState":
        """Create from Job object."""
        from ..core.config import get_config
        config = get_config()

        return cls(
            job_id=job.id,
            video_path=str(job.video_path) if job.video_path else "",
            video_name=job.video_name,
            created_at=job.created_at.isoformat(),
            updated_at=job.updated_at.isoformat(),
            duration_seconds=job.duration_seconds,
            status=job.status.value,
            error=job.error,
            audio_path=str(job.audio_path) if job.audio_path else None,
            chunks_dir=str(chunks_dir) if chunks_dir else None,
            chunk_config={
                "duration_seconds": config.chunk.duration_seconds,
                "overlap_seconds": config.chunk.overlap_seconds,
            },
            chunks=[c.to_dict() for c in job.chunks],
            output_path=str(job.output_path) if job.output_path else None,
            transcription_text=job.transcription_text,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "video_path": self.video_path,
            "video_name": self.video_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "error": self.error,
            "audio_path": self.audio_path,
            "chunks_dir": self.chunks_dir,
            "chunk_config": self.chunk_config,
            "chunks": self.chunks,
            "output_path": self.output_path,
            "transcription_text": self.transcription_text,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobState":
        """Create from dictionary."""
        return cls(
            job_id=data["job_id"],
            video_path=data["video_path"],
            video_name=data["video_name"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            duration_seconds=data.get("duration_seconds", 0.0),
            status=data["status"],
            error=data.get("error"),
            audio_path=data.get("audio_path"),
            chunks_dir=data.get("chunks_dir"),
            chunk_config=data.get("chunk_config", {}),
            chunks=data.get("chunks", []),
            output_path=data.get("output_path"),
            transcription_text=data.get("transcription_text"),
        )
