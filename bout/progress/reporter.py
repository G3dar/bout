"""
Progress reporting using Rich library.

Provides beautiful console output with progress bars.
"""
import time
from typing import Optional, Callable
from contextlib import contextmanager

try:
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TaskProgressColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
        MofNCompleteColumn,
    )
    from rich.panel import Panel
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from .tracker import ProgressTracker, Stage


class ProgressReporter:
    """
    Reports progress to the console using Rich.

    Provides:
    - Overall job progress bar
    - Current stage progress bar
    - Chunk progress for transcription
    - Time elapsed and remaining
    """

    def __init__(self, tracker: ProgressTracker):
        """
        Initialize progress reporter.

        Args:
            tracker: ProgressTracker to report on
        """
        self.tracker = tracker
        self.console = Console(stderr=True) if RICH_AVAILABLE else None
        self.progress: Optional[Progress] = None
        self.overall_task_id = None
        self.stage_task_id = None
        self.start_time = time.time()

    def __enter__(self) -> "ProgressReporter":
        if not RICH_AVAILABLE:
            return self

        # Create progress display
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TextColumn("ETA:"),
            TimeRemainingColumn(),
            console=self.console,
            transient=False,
        )
        self.progress.start()

        # Add overall progress task
        self.overall_task_id = self.progress.add_task(
            f"[cyan]Overall: {self.tracker.video_name[:40]}",
            total=100,
        )

        # Register callback
        self.tracker.on_update = self._on_progress_update

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.progress:
            self.progress.stop()

    def _on_progress_update(self, tracker: ProgressTracker):
        """Handle progress updates from tracker."""
        if not self.progress:
            return

        # Update overall progress
        if self.overall_task_id is not None:
            self.progress.update(
                self.overall_task_id,
                completed=tracker.overall_percent,
            )

        # Update stage progress
        stage_progress = tracker.current_stage_progress
        if stage_progress:
            if self.stage_task_id is None:
                self.stage_task_id = self.progress.add_task(
                    f"  {stage_progress.description}",
                    total=stage_progress.total,
                )
            else:
                self.progress.update(
                    self.stage_task_id,
                    description=f"  {stage_progress.description}",
                    completed=stage_progress.completed,
                    total=stage_progress.total,
                )

    def start_stage(self, stage: Stage, description: str, total: float = 100):
        """Start a new stage with a fresh progress bar."""
        self.tracker.start_stage(stage, description, total)

        if self.progress and self.stage_task_id is not None:
            # Complete previous stage task
            self.progress.update(self.stage_task_id, visible=False)

        # Create new stage task
        if self.progress:
            self.stage_task_id = self.progress.add_task(
                f"  {description}",
                total=total,
            )

    def update(self, advance: float = 0, completed: Optional[float] = None):
        """Update current stage progress."""
        self.tracker.update_stage(advance=advance, completed=completed)

    def complete_stage(self):
        """Complete the current stage."""
        self.tracker.complete_stage()

        if self.progress and self.stage_task_id is not None:
            stage = self.tracker.current_stage_progress
            if stage:
                self.progress.update(
                    self.stage_task_id,
                    completed=stage.total,
                )

    def print_summary(self):
        """Print final summary."""
        elapsed = time.time() - self.start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        if self.console:
            self.console.print()
            self.console.print(f"[green]Completed in {minutes}m {seconds}s[/green]")
        else:
            print(f"\nCompleted in {minutes}m {seconds}s")


class SimpleReporter:
    """
    Simple text-based progress reporter for non-Rich environments.
    """

    def __init__(self, tracker: ProgressTracker):
        self.tracker = tracker
        self.last_percent = -1

    def __enter__(self) -> "SimpleReporter":
        print(f"Processing: {self.tracker.video_name}")
        self.tracker.on_update = self._on_progress_update
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print()

    def _on_progress_update(self, tracker: ProgressTracker):
        """Print progress updates."""
        percent = int(tracker.overall_percent)
        if percent != self.last_percent:
            self.last_percent = percent
            status = tracker.get_status_text()
            print(f"\r[{percent:3d}%] {status}", end="", flush=True)

    def start_stage(self, stage: Stage, description: str, total: float = 100):
        self.tracker.start_stage(stage, description, total)

    def update(self, advance: float = 0, completed: Optional[float] = None):
        self.tracker.update_stage(advance=advance, completed=completed)

    def complete_stage(self):
        self.tracker.complete_stage()

    def print_summary(self):
        print("\nCompleted!")


def create_reporter(tracker: ProgressTracker):
    """Create appropriate reporter based on available libraries."""
    if RICH_AVAILABLE:
        return ProgressReporter(tracker)
    return SimpleReporter(tracker)
