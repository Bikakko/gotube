"""In-memory task model for GoTube Desktop."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class DesktopTask:
    id: str
    url: str
    status: str = "pending"
    percent: float = 0.0
    speed: str = ""
    eta: str = ""
    file_path: str = ""
    error: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(cls, *, url: str) -> "DesktopTask":
        return cls(id=uuid.uuid4().hex[:12], url=url)

    def mark_running(self) -> None:
        self.status = "running"
        self.touch()

    def update_progress(self, *, percent: float, speed: str = "", eta: str = "") -> None:
        self.percent = max(0.0, min(float(percent), 100.0))
        self.speed = speed
        self.eta = eta
        self.touch()

    def mark_completed(self, *, file_path: str) -> None:
        self.status = "completed"
        self.percent = 100.0
        self.file_path = file_path
        self.error = ""
        self.touch()

    def mark_failed(self, error: str) -> None:
        self.status = "failed"
        self.error = error
        self.touch()

    def mark_canceled(self) -> None:
        self.status = "canceled"
        self.touch()

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)
