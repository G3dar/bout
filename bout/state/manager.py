"""
State manager for job persistence and recovery.

Provides:
- Job state persistence to JSON files
- Resume capability for interrupted jobs
- Cleanup of old/orphaned jobs
"""
import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from ..core.types import Job, Chunk, JobStatus, ChunkStatus
from ..core.exceptions import JobNotFoundError
from .models import JobState
from ..logging import get_logger

logger = get_logger("state.manager")


class StateManager:
    """
    Manages job state persistence.

    Uses JSON files for simple, portable state storage.
    Each job has its own state file for isolation.
    """

    def __init__(self, jobs_dir: Path):
        """
        Initialize state manager.

        Args:
            jobs_dir: Directory for job state files
        """
        self.jobs_dir = Path(jobs_dir)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _job_file(self, job_id: str) -> Path:
        """Get path to job state file."""
        return self.jobs_dir / f"{job_id}.json"

    def save_job(self, job: Job, chunks_dir: Optional[Path] = None):
        """
        Save job state to disk.

        Args:
            job: Job to save
            chunks_dir: Directory containing chunk files
        """
        job.update()  # Update timestamp

        state = JobState.from_job(job, chunks_dir)
        job_file = self._job_file(job.id)

        try:
            with open(job_file, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved job state: {job.id}")
        except Exception as e:
            logger.error(f"Failed to save job {job.id}: {e}")

    def load_job(self, job_id: str) -> Optional[Job]:
        """
        Load job state from disk.

        Args:
            job_id: Job ID to load

        Returns:
            Job object or None if not found
        """
        job_file = self._job_file(job_id)

        if not job_file.exists():
            return None

        try:
            with open(job_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            state = JobState.from_dict(data)
            return state.to_job()
        except Exception as e:
            logger.error(f"Failed to load job {job_id}: {e}")
            return None

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get job by ID.

        Args:
            job_id: Job ID

        Returns:
            Job or None if not found
        """
        return self.load_job(job_id)

    def get_job_state(self, job_id: str) -> Optional[JobState]:
        """
        Get raw job state (includes chunks_dir).

        Args:
            job_id: Job ID

        Returns:
            JobState or None if not found
        """
        job_file = self._job_file(job_id)

        if not job_file.exists():
            return None

        try:
            with open(job_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return JobState.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load job state {job_id}: {e}")
            return None

    def get_all_jobs(self) -> List[Job]:
        """
        Get all jobs.

        Returns:
            List of all jobs, sorted by created_at (newest first)
        """
        jobs = []
        for job_file in self.jobs_dir.glob("*.json"):
            job_id = job_file.stem
            job = self.load_job(job_id)
            if job:
                jobs.append(job)

        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs

    def get_incomplete_jobs(self) -> List[Job]:
        """
        Get jobs that can be resumed.

        Returns:
            List of incomplete jobs
        """
        resumable_statuses = {
            JobStatus.EXTRACTING,
            JobStatus.CHUNKING,
            JobStatus.TRANSCRIBING,
            JobStatus.MERGING,
            JobStatus.GENERATING,
        }

        jobs = self.get_all_jobs()
        return [j for j in jobs if j.status in resumable_statuses]

    def delete_job(self, job_id: str) -> bool:
        """
        Delete job state file.

        Args:
            job_id: Job ID to delete

        Returns:
            True if deleted
        """
        job_file = self._job_file(job_id)

        try:
            if job_file.exists():
                job_file.unlink()
                logger.debug(f"Deleted job: {job_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}")

        return False

    def update_job_status(self, job_id: str, status: JobStatus, error: Optional[str] = None):
        """
        Update job status.

        Args:
            job_id: Job ID
            status: New status
            error: Error message (for failed status)
        """
        job = self.load_job(job_id)
        if job:
            job.status = status
            job.error = error
            self.save_job(job)

    def save_chunk_result(self, job_id: str, chunk: Chunk):
        """
        Save a single chunk result (checkpoint).

        Args:
            job_id: Job ID
            chunk: Completed chunk
        """
        job = self.load_job(job_id)
        if not job:
            return

        # Update chunk in job
        for i, c in enumerate(job.chunks):
            if c.index == chunk.index:
                job.chunks[i] = chunk
                break

        self.save_job(job)
        logger.debug(f"Checkpoint: job {job_id}, chunk {chunk.index}")

    def cleanup_old_jobs(
        self,
        max_age_seconds: int = 7 * 24 * 3600,
        dry_run: bool = False,
    ) -> int:
        """
        Clean up old completed/failed jobs.

        Args:
            max_age_seconds: Maximum age in seconds
            dry_run: If True, don't actually delete

        Returns:
            Number of jobs cleaned up
        """
        cleaned = 0
        now = time.time()

        for job_file in self.jobs_dir.glob("*.json"):
            try:
                mtime = job_file.stat().st_mtime
                age = now - mtime

                if age > max_age_seconds:
                    job = self.load_job(job_file.stem)
                    if job and job.status in {JobStatus.COMPLETED, JobStatus.FAILED}:
                        if not dry_run:
                            self.delete_job(job.id)
                        cleaned += 1
                        logger.debug(f"{'Would clean' if dry_run else 'Cleaned'}: {job.id}")

            except Exception as e:
                logger.warning(f"Error checking {job_file}: {e}")

        return cleaned

    def cleanup_job_files(self, job: Job, temp_dir: Path):
        """
        Clean up temporary files for a job.

        Args:
            job: Job to clean up
            temp_dir: Temp directory containing job files
        """
        # Clean audio file
        if job.audio_path and job.audio_path.exists():
            try:
                job.audio_path.unlink()
                logger.debug(f"Deleted audio: {job.audio_path}")
            except Exception as e:
                logger.warning(f"Could not delete audio: {e}")

        # Clean chunks directory
        chunks_dir = temp_dir / f"{job.id}_chunks"
        if chunks_dir.exists():
            try:
                shutil.rmtree(chunks_dir)
                logger.debug(f"Deleted chunks dir: {chunks_dir}")
            except Exception as e:
                logger.warning(f"Could not delete chunks dir: {e}")
