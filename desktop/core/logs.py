"""Local log storage for GoTube Desktop."""

from __future__ import annotations

from collections import deque
from datetime import datetime
from pathlib import Path


class DesktopLogStore:
    def __init__(self, path: Path, *, max_lines: int = 200) -> None:
        self.path = path
        self.max_lines = max_lines

    def append(self, message: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {message}"
        with self.path.open("a", encoding="utf-8") as file:
            file.write(line + "\n")

    def read_recent(self) -> list[str]:
        if not self.path.exists():
            return []

        lines: deque[str] = deque(maxlen=self.max_lines)
        with self.path.open("r", encoding="utf-8", errors="replace") as file:
            for line in file:
                lines.append(line.rstrip("\n"))
        return list(lines)
