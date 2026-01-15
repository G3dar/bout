"""
System utilities for memory management and process control.
"""
import gc
import os
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class MemoryInfo:
    """Memory information."""
    system_total_mb: float
    system_available_mb: float
    gpu_total_mb: Optional[float] = None
    gpu_available_mb: Optional[float] = None
    gpu_name: Optional[str] = None


def get_memory_info() -> MemoryInfo:
    """
    Get current memory information.

    Returns:
        MemoryInfo with system and GPU memory stats
    """
    # System memory
    try:
        import psutil
        mem = psutil.virtual_memory()
        system_total = mem.total / (1024 * 1024)
        system_available = mem.available / (1024 * 1024)
    except ImportError:
        system_total = 0
        system_available = 0

    # GPU memory
    gpu_total = None
    gpu_available = None
    gpu_name = None

    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            gpu_total = props.total_memory / (1024 * 1024)
            gpu_available = (props.total_memory - torch.cuda.memory_allocated(0)) / (1024 * 1024)
    except ImportError:
        pass

    return MemoryInfo(
        system_total_mb=system_total,
        system_available_mb=system_available,
        gpu_total_mb=gpu_total,
        gpu_available_mb=gpu_available,
        gpu_name=gpu_name,
    )


def cleanup_gpu_memory():
    """
    Force GPU memory cleanup.

    Should be called between processing chunks to prevent memory accumulation.
    """
    gc.collect()

    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except ImportError:
        pass


def set_process_priority(priority: str = "below_normal"):
    """
    Set the process priority.

    Args:
        priority: One of 'idle', 'below_normal', 'normal', 'above_normal', 'high'
    """
    try:
        import psutil

        priorities = {
            "idle": psutil.IDLE_PRIORITY_CLASS,
            "below_normal": psutil.BELOW_NORMAL_PRIORITY_CLASS,
            "normal": psutil.NORMAL_PRIORITY_CLASS,
            "above_normal": psutil.ABOVE_NORMAL_PRIORITY_CLASS,
            "high": psutil.HIGH_PRIORITY_CLASS,
        }

        if sys.platform == "win32":
            p = psutil.Process(os.getpid())
            p.nice(priorities.get(priority, psutil.BELOW_NORMAL_PRIORITY_CLASS))
    except ImportError:
        pass
    except Exception:
        pass  # Silently ignore priority setting failures


def get_optimal_whisper_model() -> str:
    """
    Select optimal Whisper model based on available GPU memory.

    Returns:
        Model name: 'tiny', 'base', 'small', 'medium', or 'large'
    """
    mem = get_memory_info()

    if mem.gpu_available_mb is None:
        # No GPU - use small model for reasonable CPU performance
        return "small"

    vram_gb = mem.gpu_available_mb / 1024

    if vram_gb >= 10:
        return "large"
    elif vram_gb >= 5:
        return "medium"
    elif vram_gb >= 2.5:
        return "small"
    elif vram_gb >= 1.5:
        return "base"
    else:
        return "tiny"
