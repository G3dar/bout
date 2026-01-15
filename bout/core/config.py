"""
Configuration management for BOUT.

Uses environment variables and sensible defaults.
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Set


@dataclass
class AudioConfig:
    """Audio processing configuration."""
    sample_rate: int = 16000      # Required by Whisper
    channels: int = 1              # Mono
    format: str = "wav"
    codec: str = "pcm_s16le"


@dataclass
class ChunkConfig:
    """Audio chunking configuration."""
    duration_seconds: int = 300    # 5 minutes per chunk
    overlap_seconds: int = 10      # 10 seconds overlap for context
    min_chunk_seconds: int = 30    # Minimum chunk size


@dataclass
class WhisperConfig:
    """Whisper model configuration."""
    model: str = "medium"          # Model size: tiny, base, small, medium, large
    language: str = "es"           # Target language
    device: str = "auto"           # auto, cuda, cpu


@dataclass
class DiarizationConfig:
    """Speaker diarization configuration."""
    hf_token: str = "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"  # HuggingFace token
    model: str = "pyannote/speaker-diarization-3.1"


@dataclass
class LogConfig:
    """Logging configuration."""
    level: str = "INFO"
    max_file_size: int = 10 * 1024 * 1024  # 10 MB
    backup_count: int = 5


@dataclass
class Config:
    """Main application configuration."""
    # Directories
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)
    input_dir: Path = field(default=None)
    output_dir: Path = field(default=None)
    temp_dir: Path = field(default=None)
    logs_dir: Path = field(default=None)
    jobs_dir: Path = field(default=None)

    # Sub-configs
    audio: AudioConfig = field(default_factory=AudioConfig)
    chunk: ChunkConfig = field(default_factory=ChunkConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    diarization: DiarizationConfig = field(default_factory=DiarizationConfig)
    log: LogConfig = field(default_factory=LogConfig)

    # Supported video extensions
    video_extensions: Set[str] = field(default_factory=lambda: {
        ".mp4", ".avi", ".mkv", ".mov", ".webm", ".m4v", ".wmv", ".flv"
    })

    # FFmpeg path (auto-detected or manual)
    ffmpeg_path: Optional[str] = None

    def __post_init__(self):
        """Initialize derived paths."""
        if self.input_dir is None:
            self.input_dir = self.base_dir / "input"
        if self.output_dir is None:
            self.output_dir = self.base_dir / "output"
        if self.temp_dir is None:
            self.temp_dir = self.base_dir / "temp"
        if self.logs_dir is None:
            self.logs_dir = self.base_dir / "logs"
        if self.jobs_dir is None:
            self.jobs_dir = self.base_dir / "jobs"

        # Load from environment
        self._load_from_env()

    def _load_from_env(self):
        """Load configuration from environment variables."""
        if os.environ.get("BOUT_MODEL"):
            self.whisper.model = os.environ["BOUT_MODEL"]
        if os.environ.get("BOUT_LANGUAGE"):
            self.whisper.language = os.environ["BOUT_LANGUAGE"]
        if os.environ.get("BOUT_DEVICE"):
            self.whisper.device = os.environ["BOUT_DEVICE"]
        if os.environ.get("BOUT_LOG_LEVEL"):
            self.log.level = os.environ["BOUT_LOG_LEVEL"]
        if os.environ.get("BOUT_CHUNK_DURATION"):
            self.chunk.duration_seconds = int(os.environ["BOUT_CHUNK_DURATION"])
        if os.environ.get("FFMPEG_PATH"):
            self.ffmpeg_path = os.environ["FFMPEG_PATH"]

    def ensure_directories(self):
        """Create all required directories."""
        for dir_path in [self.input_dir, self.output_dir, self.temp_dir,
                         self.logs_dir, self.jobs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        # Create logs/jobs subdirectory
        (self.logs_dir / "jobs").mkdir(exist_ok=True)


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config):
    """Set the global configuration instance."""
    global _config
    _config = config
