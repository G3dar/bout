"""
Progress tracking for the transcription pipeline.

Tracks progress across multiple stages with weighted contributions to overall progress.
"""
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict
from enum import Enum


class Stage(str, Enum):
    """Pipeline stages."""
    EXTRACT = "extract"
    CHUNK = "chunk"
    TRANSCRIBE = "transcribe"
    MERGE = "merge"
    DIARIZE = "diarize"
    GENERATE = "generate"


@dataclass
class StageProgress:
    """Progress information for a single stage."""
    name: str
    description: str
    total: float = 100.0
    completed: float = 0.0
    weight: float = 0.0  # Contribution to overall progress

    @property
    def progress(self) -> float:
        """Progress as fraction (0.0 - 1.0)."""
        if self.total <= 0:
            return 0.0
        return min(1.0, self.completed / self.total)

    @property
    def percent(self) -> float:
        """Progress as percentage (0 - 100)."""
        return self.progress * 100


# Stage weights for overall progress calculation
STAGE_WEIGHTS = {
    Stage.EXTRACT: 0.10,     # 10% - Audio extraction
    Stage.CHUNK: 0.05,       # 5% - Chunking
    Stage.TRANSCRIBE: 0.50,  # 50% - Transcription (main work)
    Stage.MERGE: 0.05,       # 5% - Merging results
    Stage.DIARIZE: 0.15,     # 15% - Speaker diarization
    Stage.GENERATE: 0.15,    # 15% - Document generation
}


class ProgressTracker:
    """
    Tracks progress across pipeline stages.

    Supports callbacks for UI updates and calculates weighted overall progress.
    """

    def __init__(
        self,
        video_name: str,
        total_duration: float,
        on_update: Optional[Callable[["ProgressTracker"], None]] = None,
    ):
        """
        Initialize progress tracker.

        Args:
            video_name: Name of the video being processed
            total_duration: Total video duration in seconds
            on_update: Callback invoked on progress updates
        """
        self.video_name = video_name
        self.total_duration = total_duration
        self.on_update = on_update

        # Stage tracking
        self.stages: Dict[Stage, StageProgress] = {}
        self.current_stage: Optional[Stage] = None
        self.completed_stages: set = set()

        # Chunk tracking (for transcription stage)
        self.total_chunks: int = 0
        self.current_chunk: int = 0

    def start_stage(
        self,
        stage: Stage,
        description: str,
        total: float = 100.0,
    ) -> StageProgress:
        """
        Start a new pipeline stage.

        Args:
            stage: Stage identifier
            description: Human-readable description
            total: Total units of work for this stage

        Returns:
            StageProgress instance
        """
        progress = StageProgress(
            name=stage.value,
            description=description,
            total=total,
            weight=STAGE_WEIGHTS.get(stage, 0.0),
        )
        self.stages[stage] = progress
        self.current_stage = stage
        self._notify()
        return progress

    def update_stage(
        self,
        advance: float = 0,
        completed: Optional[float] = None,
        description: Optional[str] = None,
    ):
        """
        Update current stage progress.

        Args:
            advance: Amount to add to current progress
            completed: Set absolute completed value (overrides advance)
            description: Update the stage description
        """
        if self.current_stage is None:
            return

        stage = self.stages[self.current_stage]

        if completed is not None:
            stage.completed = completed
        else:
            stage.completed += advance

        if description:
            stage.description = description

        self._notify()

    def complete_stage(self):
        """Mark current stage as complete."""
        if self.current_stage is None:
            return

        stage = self.stages[self.current_stage]
        stage.completed = stage.total
        self.completed_stages.add(self.current_stage)
        self._notify()

    def set_chunks(self, total: int):
        """Set total number of chunks for transcription stage."""
        self.total_chunks = total

    def start_chunk(self, chunk_index: int):
        """Start processing a chunk."""
        self.current_chunk = chunk_index

    def complete_chunk(self, chunk_index: int):
        """Mark a chunk as complete."""
        # Update transcription stage progress based on chunks
        if Stage.TRANSCRIBE in self.stages:
            stage = self.stages[Stage.TRANSCRIBE]
            if self.total_chunks > 0:
                stage.completed = ((chunk_index + 1) / self.total_chunks) * stage.total
                self._notify()

    @property
    def overall_progress(self) -> float:
        """
        Calculate weighted overall progress.

        Returns:
            Progress as fraction (0.0 - 1.0)
        """
        total_weight = sum(STAGE_WEIGHTS.values())
        weighted_sum = 0.0

        for stage, weight in STAGE_WEIGHTS.items():
            if stage in self.stages:
                weighted_sum += self.stages[stage].progress * weight
            elif stage in self.completed_stages:
                weighted_sum += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    @property
    def overall_percent(self) -> float:
        """Overall progress as percentage."""
        return self.overall_progress * 100

    @property
    def current_stage_progress(self) -> Optional[StageProgress]:
        """Get current stage progress."""
        if self.current_stage:
            return self.stages.get(self.current_stage)
        return None

    def _notify(self):
        """Notify callback of progress update."""
        if self.on_update:
            self.on_update(self)

    def get_status_text(self) -> str:
        """Get a human-readable status string."""
        if self.current_stage is None:
            return "Initializing..."

        stage = self.stages.get(self.current_stage)
        if stage is None:
            return "Processing..."

        if self.current_stage == Stage.TRANSCRIBE and self.total_chunks > 0:
            return f"{stage.description} (Chunk {self.current_chunk + 1}/{self.total_chunks})"

        return stage.description
