"""Run pre-package checks for GoTube Desktop."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    checks = [
        [sys.executable, "-m", "unittest", "discover", "tests/desktop"],
        ["node", "--check", "desktop/ui/app.js"],
        [
            sys.executable,
            "-m",
            "py_compile",
            "desktop/app.py",
            "desktop/core/config.py",
            "desktop/core/cookies.py",
            "desktop/core/downloader.py",
            "desktop/core/logs.py",
            "desktop/core/tasks.py",
            "desktop/core/tools.py",
        ],
    ]

    for command in checks:
        print(f"> {' '.join(command)}")
        completed = subprocess.run(command, cwd=ROOT)
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
