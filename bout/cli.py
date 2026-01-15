"""
Command-line interface for BOUT.

Provides commands for transcription, job management, and cleanup.
"""
import sys
from pathlib import Path
from typing import Optional

try:
    import click
    CLICK_AVAILABLE = True
except ImportError:
    CLICK_AVAILABLE = False

from . import __version__
from .core.config import get_config, Config
from .core.exceptions import BoutError, VideoNotFoundError, UnsupportedVideoError
from .logging import setup_logging, get_logger
from .utils.ffmpeg import check_ffmpeg


def print_banner():
    """Print application banner."""
    print(f"""
============================================================
                    BOUT v{__version__}
              Video Transcription Tool
============================================================
""")


def validate_video(video_path: Path) -> Path:
    """Validate video file exists and is supported."""
    config = get_config()

    if not video_path.exists():
        raise VideoNotFoundError(str(video_path))

    if video_path.suffix.lower() not in config.video_extensions:
        raise UnsupportedVideoError(str(video_path), video_path.suffix)

    return video_path.resolve()


if CLICK_AVAILABLE:
    @click.group()
    @click.version_option(version=__version__)
    @click.option("--debug", is_flag=True, help="Enable debug logging")
    @click.pass_context
    def cli(ctx, debug):
        """BOUT - Video Transcription Tool"""
        ctx.ensure_object(dict)
        ctx.obj["debug"] = debug

        # Initialize logging
        setup_logging(level="DEBUG" if debug else "INFO")

    @cli.command()
    @click.argument("video", type=click.Path(exists=True, path_type=Path))
    @click.option("--output", "-o", type=click.Path(path_type=Path),
                  help="Output directory")
    @click.option("--model", "-m", default="medium",
                  type=click.Choice(["tiny", "base", "small", "medium", "large"]),
                  help="Whisper model size")
    @click.option("--language", "-l", default="es", help="Language code")
    @click.option("--device", "-d", default="auto",
                  type=click.Choice(["auto", "cuda", "cpu"]),
                  help="Processing device")
    @click.option("--diarize", is_flag=True, default=False,
                  help="Enable speaker identification (requires HF_TOKEN)")
    @click.pass_context
    def transcribe(ctx, video, output, model, language, device, diarize):
        """Transcribe a video file."""
        print_banner()
        logger = get_logger("cli")

        config = get_config()
        config.ensure_directories()

        # Override config with CLI options
        config.whisper.model = model
        config.whisper.language = language
        config.whisper.device = device
        if output:
            config.output_dir = Path(output)

        # Check FFmpeg
        if not check_ffmpeg():
            logger.error("FFmpeg not found. Please install FFmpeg.")
            sys.exit(1)

        # Check HF_TOKEN for diarization
        if diarize:
            import os
            hf_token = os.environ.get("HF_TOKEN") or config.diarization.hf_token
            if not hf_token:
                logger.warning("HF_TOKEN not set. Diarization requires a HuggingFace token.")
                logger.info("Get your free token at: https://huggingface.co/settings/tokens")
            else:
                logger.info("Using configured HuggingFace token for diarization")
                logger.info("Make sure you accepted the model license at: https://hf.co/pyannote/speaker-diarization-3.1")

        try:
            video_path = validate_video(video)
            logger.info(f"Processing: {video_path.name}")

            # Import pipeline here to defer heavy imports
            from .pipeline.orchestrator import Orchestrator

            orchestrator = Orchestrator(config, use_diarization=diarize)
            output_path = orchestrator.process(video_path)

            if output_path:
                logger.info(f"Output saved to: {output_path}")
                click.echo(f"\nOutput: {output_path}")
            else:
                logger.error("Transcription failed")
                sys.exit(1)

        except BoutError as e:
            logger.error(str(e))
            if e.suggestions:
                click.echo("\nSuggestions:")
                for i, tip in enumerate(e.suggestions, 1):
                    click.echo(f"  {i}. {tip}")
            sys.exit(1)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            sys.exit(130)

    @cli.command()
    @click.argument("job_id")
    @click.pass_context
    def resume(ctx, job_id):
        """Resume an interrupted transcription job."""
        print_banner()
        logger = get_logger("cli")

        config = get_config()
        config.ensure_directories()

        # Check FFmpeg
        if not check_ffmpeg():
            logger.error("FFmpeg not found. Please install FFmpeg.")
            sys.exit(1)

        try:
            from .pipeline.orchestrator import Orchestrator
            from .state.manager import StateManager

            state_manager = StateManager(config.jobs_dir)
            job = state_manager.get_job(job_id)

            if job is None:
                logger.error(f"Job not found: {job_id}")
                sys.exit(1)

            logger.info(f"Resuming job: {job_id}")
            orchestrator = Orchestrator(config)
            output_path = orchestrator.resume(job)

            if output_path:
                logger.info(f"Output saved to: {output_path}")
            else:
                logger.error("Transcription failed")
                sys.exit(1)

        except BoutError as e:
            logger.error(str(e))
            sys.exit(1)

    @cli.group()
    def jobs():
        """Job management commands."""
        pass

    @jobs.command("list")
    @click.option("--status", "-s", help="Filter by status")
    @click.option("--limit", "-n", default=10, help="Maximum jobs to show")
    def jobs_list(status, limit):
        """List transcription jobs."""
        config = get_config()

        from .state.manager import StateManager

        state_manager = StateManager(config.jobs_dir)
        jobs = state_manager.get_all_jobs()

        if status:
            jobs = [j for j in jobs if j.status.value == status]

        jobs = jobs[:limit]

        if not jobs:
            click.echo("No jobs found.")
            return

        click.echo(f"\n{'ID':<10} {'Status':<12} {'Video':<40} {'Progress':<10}")
        click.echo("-" * 75)

        for job in jobs:
            video_name = job.video_name[:38] + ".." if len(job.video_name) > 40 else job.video_name
            progress = f"{int(job.progress * 100)}%"
            click.echo(f"{job.id:<10} {job.status.value:<12} {video_name:<40} {progress:<10}")

    @cli.command()
    @click.option("--older-than", default="7d", help="Clean files older than (e.g., 7d, 24h)")
    @click.option("--dry-run", is_flag=True, help="Show what would be deleted")
    def clean(older_than, dry_run):
        """Clean up old temporary files and failed jobs."""
        config = get_config()
        logger = get_logger("cli")

        from .state.manager import StateManager

        state_manager = StateManager(config.jobs_dir)

        if dry_run:
            click.echo("Dry run - no files will be deleted")

        # Parse age string
        import re
        match = re.match(r"(\d+)([dhm])", older_than)
        if not match:
            click.echo("Invalid age format. Use: 7d, 24h, or 30m")
            return

        value, unit = match.groups()
        value = int(value)
        if unit == "d":
            max_age_seconds = value * 24 * 3600
        elif unit == "h":
            max_age_seconds = value * 3600
        else:
            max_age_seconds = value * 60

        cleaned = state_manager.cleanup_old_jobs(max_age_seconds, dry_run=dry_run)
        click.echo(f"{'Would clean' if dry_run else 'Cleaned'}: {cleaned} items")

    def main():
        """Main entry point."""
        cli()

else:
    # Fallback for when Click is not available
    import argparse

    def main():
        """Main entry point (argparse fallback)."""
        parser = argparse.ArgumentParser(
            description="BOUT - Video Transcription Tool"
        )
        parser.add_argument("--version", action="version", version=f"BOUT {__version__}")
        parser.add_argument("--debug", action="store_true", help="Enable debug logging")

        subparsers = parser.add_subparsers(dest="command")

        # Transcribe command
        transcribe_parser = subparsers.add_parser("transcribe", help="Transcribe a video")
        transcribe_parser.add_argument("video", type=Path, help="Video file path")
        transcribe_parser.add_argument("--output", "-o", type=Path, help="Output directory")
        transcribe_parser.add_argument("--model", "-m", default="medium",
                                       choices=["tiny", "base", "small", "medium", "large"])
        transcribe_parser.add_argument("--language", "-l", default="es")
        transcribe_parser.add_argument("--device", "-d", default="auto",
                                       choices=["auto", "cuda", "cpu"])

        # Resume command
        resume_parser = subparsers.add_parser("resume", help="Resume a job")
        resume_parser.add_argument("job_id", help="Job ID to resume")

        args = parser.parse_args()

        # Initialize logging
        setup_logging(level="DEBUG" if args.debug else "INFO")

        print_banner()

        if args.command == "transcribe":
            config = get_config()
            config.ensure_directories()
            config.whisper.model = args.model
            config.whisper.language = args.language
            config.whisper.device = args.device
            if args.output:
                config.output_dir = args.output

            if not check_ffmpeg():
                print("ERROR: FFmpeg not found")
                sys.exit(1)

            try:
                video_path = validate_video(args.video)
                from .pipeline.orchestrator import Orchestrator
                orchestrator = Orchestrator(config)
                output_path = orchestrator.process(video_path)
                if output_path:
                    print(f"\nOutput: {output_path}")
                else:
                    sys.exit(1)
            except BoutError as e:
                print(f"ERROR: {e}")
                sys.exit(1)

        elif args.command == "resume":
            print("Resume not implemented in fallback mode")
            sys.exit(1)

        else:
            parser.print_help()


if __name__ == "__main__":
    main()
