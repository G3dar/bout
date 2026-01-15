"""
Pipeline orchestrator.

Coordinates all stages of the transcription pipeline with progress tracking
and state management for recovery.
"""
from pathlib import Path
from typing import Optional

from ..core.config import Config, get_config
from ..core.types import Job, JobStatus, ChunkStatus
from ..core.exceptions import BoutError
from ..audio import AudioExtractor, AudioChunker, get_video_duration
from ..transcription import TranscriptionEngine, ChunkMerger
from ..diarization import DiarizationEngine
from ..output import DocumentGenerator
from ..state import StateManager
from ..progress import ProgressTracker, Stage
from ..progress.reporter import create_reporter
from ..logging import get_logger, JobLogger

logger = get_logger("pipeline")


class Orchestrator:
    """
    Orchestrates the complete transcription pipeline.

    Stages:
    1. Extract audio from video
    2. Split audio into chunks (if needed)
    3. Transcribe each chunk
    4. Merge chunk results
    5. Generate output document

    Supports:
    - Progress tracking at each stage
    - Checkpoint/resume capability
    - Memory management between chunks
    """

    def __init__(self, config: Optional[Config] = None, use_diarization: bool = False):
        """
        Initialize orchestrator.

        Args:
            config: Configuration (uses global if None)
            use_diarization: Enable speaker identification
        """
        self.config = config or get_config()
        self.config.ensure_directories()
        self.use_diarization = use_diarization

        self.state_manager = StateManager(self.config.jobs_dir)
        self.audio_extractor = AudioExtractor(
            sample_rate=self.config.audio.sample_rate,
            channels=self.config.audio.channels,
        )
        self.audio_chunker = AudioChunker(
            chunk_duration=self.config.chunk.duration_seconds,
            overlap=self.config.chunk.overlap_seconds,
            min_chunk=self.config.chunk.min_chunk_seconds,
        )
        self.transcription_engine = TranscriptionEngine(
            model_name=self.config.whisper.model,
            language=self.config.whisper.language,
            device=self.config.whisper.device,
        )
        self.chunk_merger = ChunkMerger(
            overlap_seconds=self.config.chunk.overlap_seconds,
        )
        self.diarization_engine = DiarizationEngine() if use_diarization else None
        self.document_generator = DocumentGenerator()

    def process(self, video_path: Path) -> Optional[Path]:
        """
        Process a video file from start to finish.

        Args:
            video_path: Path to video file

        Returns:
            Path to generated document, or None on failure
        """
        video_path = Path(video_path).resolve()

        # Get video duration
        duration = get_video_duration(video_path)
        logger.info(f"Video duration: {duration:.1f}s")

        # Create job
        job = Job(
            video_path=video_path,
            video_name=video_path.name,
            duration_seconds=duration,
        )

        # Create progress tracker
        tracker = ProgressTracker(
            video_name=video_path.name,
            total_duration=duration,
        )

        with JobLogger(job.id, video_path.name) as job_log:
            with create_reporter(tracker) as reporter:
                try:
                    return self._execute_pipeline(job, tracker, reporter, job_log)
                except KeyboardInterrupt:
                    logger.info("Interrupted by user")
                    job.status = JobStatus.CANCELLED
                    self.state_manager.save_job(job)
                    return None
                except BoutError as e:
                    logger.error(f"Pipeline error: {e}")
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    self.state_manager.save_job(job)
                    raise
                except Exception as e:
                    logger.error(f"Unexpected error: {e}", exc_info=True)
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    self.state_manager.save_job(job)
                    raise BoutError(f"Pipeline failed: {e}")

    def _execute_pipeline(
        self,
        job: Job,
        tracker: ProgressTracker,
        reporter,
        job_log: JobLogger,
    ) -> Optional[Path]:
        """
        Execute all pipeline stages.

        Args:
            job: Job object
            tracker: Progress tracker
            reporter: Progress reporter
            job_log: Job-specific logger

        Returns:
            Output path or None
        """
        chunks_dir = self.config.temp_dir / f"{job.id}_chunks"

        # Stage 1: Extract audio
        job.status = JobStatus.EXTRACTING
        self.state_manager.save_job(job)

        reporter.start_stage(Stage.EXTRACT, "Extracting audio")
        job_log.info("Stage 1: Extracting audio")

        audio_path = self.audio_extractor.extract(
            job.video_path,
            progress_callback=lambda p: reporter.update(completed=p),
        )
        job.audio_path = audio_path
        reporter.complete_stage()
        job_log.info(f"Audio extracted: {audio_path.name}")

        # Stage 2: Split into chunks
        job.status = JobStatus.CHUNKING
        self.state_manager.save_job(job)

        reporter.start_stage(Stage.CHUNK, "Splitting audio into chunks")
        job_log.info("Stage 2: Chunking audio")

        chunks = self.audio_chunker.calculate_chunks(job.duration_seconds)
        tracker.set_chunks(len(chunks))

        if len(chunks) > 1:
            chunks = self.audio_chunker.split_audio(
                audio_path,
                chunks_dir,
                chunks,
                progress_callback=lambda c, t: reporter.update(completed=(c / t) * 100),
            )
        else:
            # Single chunk - use full audio file
            chunks[0].file_path = audio_path

        job.chunks = chunks
        reporter.complete_stage()
        job_log.info(f"Created {len(chunks)} chunks")

        # Save job with chunks for recovery
        self.state_manager.save_job(job, chunks_dir)

        # Stage 3: Transcribe chunks
        job.status = JobStatus.TRANSCRIBING
        self.state_manager.save_job(job, chunks_dir)

        reporter.start_stage(Stage.TRANSCRIBE, "Transcribing audio", total=len(chunks))
        job_log.info("Stage 3: Transcribing chunks")

        def on_chunk_progress(current, total):
            reporter.update(completed=current)
            tracker.complete_chunk(current - 1)

        def on_chunk_checkpoint(chunk):
            self.state_manager.save_chunk_result(job.id, chunk)
            job_log.info(f"Chunk {chunk.index} completed: {len(chunk.text or '')} chars")

        job.chunks = self.transcription_engine.transcribe_all_chunks(
            job.chunks,
            progress_callback=on_chunk_progress,
            checkpoint_callback=on_chunk_checkpoint,
        )

        reporter.complete_stage()
        job_log.info("Transcription completed")

        # Stage 4: Merge chunks
        job.status = JobStatus.MERGING
        self.state_manager.save_job(job, chunks_dir)

        reporter.start_stage(Stage.MERGE, "Merging transcriptions")
        job_log.info("Stage 4: Merging chunks")

        full_text, segments = self.chunk_merger.merge_chunks(job.chunks)
        job.transcription_text = full_text
        job.segments = segments

        reporter.complete_stage()
        job_log.info(f"Merged: {len(full_text)} chars, {len(segments)} segments")

        # Stage 5: Diarization (optional)
        if self.use_diarization and self.diarization_engine:
            job.status = JobStatus.DIARIZING
            self.state_manager.save_job(job, chunks_dir)

            reporter.start_stage(Stage.DIARIZE, "Identifying speakers")
            job_log.info("Stage 5: Identifying speakers")

            try:
                if self.diarization_engine.is_available():
                    diar_segments = self.diarization_engine.diarize(job.audio_path)
                    segments = self.diarization_engine.merge_with_transcription(
                        segments, diar_segments
                    )
                    segments = self.diarization_engine.consolidate_segments(segments)
                    job.segments = segments
                    job_log.info(f"Identified speakers in {len(segments)} segments")
                else:
                    job_log.warning("HF_TOKEN not configured, skipping diarization")
            except Exception as e:
                job_log.warning(f"Diarization failed: {e}, continuing without speaker labels")

            reporter.complete_stage()
        else:
            # Skip diarization - mark as complete for progress
            reporter.start_stage(Stage.DIARIZE, "Diarization skipped")
            reporter.complete_stage()

        # Stage 6: Generate document
        job.status = JobStatus.GENERATING
        self.state_manager.save_job(job, chunks_dir)

        reporter.start_stage(Stage.GENERATE, "Generating document")
        job_log.info("Stage 6: Generating document")

        output_path = self.document_generator.generate(
            video_name=job.video_name,
            text=full_text,
            segments=segments,
            duration_seconds=job.duration_seconds,
        )
        job.output_path = output_path

        reporter.complete_stage()
        reporter.print_summary()

        # Mark complete
        job.status = JobStatus.COMPLETED
        self.state_manager.save_job(job)

        # Cleanup temp files
        self._cleanup(job, chunks_dir)

        job_log.info(f"Output: {output_path}")
        return output_path

    def resume(self, job: Job) -> Optional[Path]:
        """
        Resume an interrupted job.

        Args:
            job: Job to resume (loaded from state)

        Returns:
            Output path or None
        """
        logger.info(f"Resuming job: {job.id}")
        logger.info(f"Status: {job.status.value}")
        logger.info(f"Completed chunks: {job.completed_chunks}/{job.total_chunks}")

        # Load full state
        state = self.state_manager.get_job_state(job.id)
        if not state:
            raise BoutError(f"Could not load state for job {job.id}")

        chunks_dir = Path(state.chunks_dir) if state.chunks_dir else None

        # Create progress tracker
        tracker = ProgressTracker(
            video_name=job.video_name,
            total_duration=job.duration_seconds,
        )

        with JobLogger(job.id, job.video_name) as job_log:
            with create_reporter(tracker) as reporter:
                try:
                    return self._resume_from_status(job, chunks_dir, tracker, reporter, job_log)
                except Exception as e:
                    logger.error(f"Resume failed: {e}", exc_info=True)
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    self.state_manager.save_job(job)
                    raise

    def _resume_from_status(
        self,
        job: Job,
        chunks_dir: Optional[Path],
        tracker: ProgressTracker,
        reporter,
        job_log: JobLogger,
    ) -> Optional[Path]:
        """
        Resume from the job's current status.

        Args:
            job: Job to resume
            chunks_dir: Directory with chunk files
            tracker: Progress tracker
            reporter: Progress reporter
            job_log: Job logger

        Returns:
            Output path or None
        """
        # Skip completed stages
        if job.status == JobStatus.TRANSCRIBING:
            # Resume transcription from where we left off
            tracker.set_chunks(len(job.chunks))

            reporter.start_stage(Stage.TRANSCRIBE, "Resuming transcription", total=len(job.chunks))
            job_log.info(f"Resuming transcription from chunk {job.completed_chunks}")

            def on_chunk_progress(current, total):
                reporter.update(completed=current)

            def on_chunk_checkpoint(chunk):
                self.state_manager.save_chunk_result(job.id, chunk)

            job.chunks = self.transcription_engine.transcribe_all_chunks(
                job.chunks,
                progress_callback=on_chunk_progress,
                checkpoint_callback=on_chunk_checkpoint,
            )

            reporter.complete_stage()

        # Continue with remaining stages
        if job.status in {JobStatus.TRANSCRIBING, JobStatus.MERGING}:
            job.status = JobStatus.MERGING
            reporter.start_stage(Stage.MERGE, "Merging transcriptions")

            full_text, segments = self.chunk_merger.merge_chunks(job.chunks)
            job.transcription_text = full_text
            job.segments = segments

            reporter.complete_stage()

        if job.status in {JobStatus.TRANSCRIBING, JobStatus.MERGING, JobStatus.GENERATING}:
            job.status = JobStatus.GENERATING
            reporter.start_stage(Stage.GENERATE, "Generating document")

            output_path = self.document_generator.generate(
                video_name=job.video_name,
                text=job.transcription_text,
                segments=job.segments,
                duration_seconds=job.duration_seconds,
            )
            job.output_path = output_path

            reporter.complete_stage()
            reporter.print_summary()

        # Mark complete
        job.status = JobStatus.COMPLETED
        self.state_manager.save_job(job)

        # Cleanup
        self._cleanup(job, chunks_dir)

        return job.output_path

    def _cleanup(self, job: Job, chunks_dir: Optional[Path]):
        """Clean up temporary files after successful completion."""
        logger.debug("Cleaning up temporary files")

        # Clean audio file
        if job.audio_path:
            self.audio_extractor.cleanup(job.audio_path)

        # Clean chunks
        if chunks_dir:
            self.audio_chunker.cleanup_directory(chunks_dir)
