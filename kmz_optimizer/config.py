"""Runtime configuration for the KMZ Optimizer project."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoragePaths:
    """Collection of filesystem paths used by the application."""

    uploads: Path
    outputs: Path

    def ensure(self) -> None:
        """Ensure the backing directories exist."""
        self.uploads.mkdir(parents=True, exist_ok=True)
        self.outputs.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class AppConfig:
    """High level runtime configuration values."""

    max_csv_size_mb: int = 50
    max_kmz_size_mb: int = 10
    allowed_csv_extensions: tuple[str, ...] = ("csv",)
    allowed_kmz_extensions: tuple[str, ...] = ("kmz",)

    @property
    def max_upload_bytes(self) -> int:
        """Maximum upload payload in bytes."""
        return self.max_csv_size_mb * 1024 * 1024


@dataclass(frozen=True)
class QueueConfig:
    """Configuration for the Redis-backed task queue."""

    redis_url: str = "redis://localhost:6379/0"
    queue_name: str = "kmz-optimizer"
    default_timeout: int = 60 * 30  # seconds


APP_CONFIG = AppConfig()
STORAGE_PATHS = StoragePaths(
    uploads=Path(os.environ.get("KMZ_OPTIMIZER_UPLOADS", "uploads")),
    outputs=Path(os.environ.get("KMZ_OPTIMIZER_OUTPUTS", "outputs")),
)
QUEUE_CONFIG = QueueConfig(
    redis_url=os.environ.get("KMZ_OPTIMIZER_REDIS_URL", QueueConfig.redis_url),
    queue_name=os.environ.get("KMZ_OPTIMIZER_QUEUE", QueueConfig.queue_name),
    default_timeout=int(
        os.environ.get("KMZ_OPTIMIZER_QUEUE_TIMEOUT", QueueConfig.default_timeout)
    ),
)

STORAGE_PATHS.ensure()
