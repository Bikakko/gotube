"""Build GoTube Desktop with PyInstaller."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build GoTube Desktop")
    parser.add_argument("--skip-check", action="store_true", help="skip scripts/desktop_check.py")
    args = parser.parse_args()

    if not args.skip_check:
        check = subprocess.run([sys.executable, "scripts/desktop_check.py"], cwd=ROOT)
        if check.returncode != 0:
            return check.returncode

    command = [
        "pyinstaller",
        "--clean",
        "--noconfirm",
        "--distpath",
        "desktop_dist",
        "--workpath",
        "desktop_build",
        "desktop/packaging/gotube-desktop.spec",
    ]
    print(f"> {' '.join(command)}")
    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
