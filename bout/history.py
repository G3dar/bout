"""
Translation history tracking for BOUT.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class HistoryEntry:
    """A single translation history entry."""
    id: str
    video_name: str
    video_path: str
    output_path: str
    date: str  # ISO format
    duration_seconds: float
    model: str
    diarization: bool
    speakers_found: int
    segments_count: int
    characters_count: int
    processing_time_seconds: float
    status: str  # "completed", "failed"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryEntry":
        return cls(**data)

    @property
    def date_formatted(self) -> str:
        """Return formatted date."""
        dt = datetime.fromisoformat(self.date)
        return dt.strftime("%d/%m/%Y %H:%M")

    @property
    def duration_formatted(self) -> str:
        """Return formatted duration."""
        mins = int(self.duration_seconds // 60)
        secs = int(self.duration_seconds % 60)
        return f"{mins}m {secs}s"


class HistoryManager:
    """Manages translation history."""

    def __init__(self, history_dir: Optional[Path] = None):
        """Initialize history manager."""
        if history_dir is None:
            from .core.config import get_config
            config = get_config()
            history_dir = config.base_dir / "history"

        self.history_dir = Path(history_dir)
        self.history_file = self.history_dir / "history.json"
        self.history_dir.mkdir(parents=True, exist_ok=True)

        self._history: List[HistoryEntry] = []
        self._load()

    def _load(self):
        """Load history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._history = [HistoryEntry.from_dict(entry) for entry in data]
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load history: {e}")
                self._history = []
        else:
            self._history = []

    def _save(self):
        """Save history to file."""
        with open(self.history_file, 'w', encoding='utf-8') as f:
            data = [entry.to_dict() for entry in self._history]
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_entry(
        self,
        video_name: str,
        video_path: str,
        output_path: str,
        duration_seconds: float,
        model: str,
        diarization: bool,
        speakers_found: int,
        segments_count: int,
        characters_count: int,
        processing_time_seconds: float,
        status: str = "completed",
        error: Optional[str] = None,
    ) -> HistoryEntry:
        """Add a new history entry."""
        import uuid

        entry = HistoryEntry(
            id=str(uuid.uuid4())[:8],
            video_name=video_name,
            video_path=str(video_path),
            output_path=str(output_path),
            date=datetime.now().isoformat(),
            duration_seconds=duration_seconds,
            model=model,
            diarization=diarization,
            speakers_found=speakers_found,
            segments_count=segments_count,
            characters_count=characters_count,
            processing_time_seconds=processing_time_seconds,
            status=status,
            error=error,
        )

        self._history.insert(0, entry)  # Most recent first
        self._save()
        return entry

    def get_all(self) -> List[HistoryEntry]:
        """Get all history entries."""
        return self._history.copy()

    def get_recent(self, limit: int = 10) -> List[HistoryEntry]:
        """Get recent history entries."""
        return self._history[:limit]

    def get_by_id(self, entry_id: str) -> Optional[HistoryEntry]:
        """Get entry by ID."""
        for entry in self._history:
            if entry.id == entry_id:
                return entry
        return None

    def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[HistoryEntry]:
        """Get entries within a date range."""
        result = []
        for entry in self._history:
            entry_date = datetime.fromisoformat(entry.date)
            if start_date <= entry_date <= end_date:
                result.append(entry)
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics from history."""
        if not self._history:
            return {
                "total_transcriptions": 0,
                "total_duration_hours": 0,
                "total_characters": 0,
                "avg_processing_time": 0,
                "models_used": {},
            }

        total_duration = sum(e.duration_seconds for e in self._history)
        total_chars = sum(e.characters_count for e in self._history)
        total_processing = sum(e.processing_time_seconds for e in self._history)

        models_used = {}
        for entry in self._history:
            models_used[entry.model] = models_used.get(entry.model, 0) + 1

        return {
            "total_transcriptions": len(self._history),
            "total_duration_hours": total_duration / 3600,
            "total_characters": total_chars,
            "avg_processing_time": total_processing / len(self._history),
            "models_used": models_used,
        }

    def clear(self):
        """Clear all history."""
        self._history = []
        self._save()

    def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry by ID."""
        for i, entry in enumerate(self._history):
            if entry.id == entry_id:
                del self._history[i]
                self._save()
                return True
        return False


# Global instance
_history_manager: Optional[HistoryManager] = None


def get_history_manager() -> HistoryManager:
    """Get global history manager instance."""
    global _history_manager
    if _history_manager is None:
        _history_manager = HistoryManager()
    return _history_manager
