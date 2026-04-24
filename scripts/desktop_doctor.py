"""Print GoTube Desktop environment diagnostics."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from desktop.core.environment import collect_environment_report, has_missing_required_checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Check GoTube Desktop runtime environment.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return non-zero when required checks are missing",
    )
    args = parser.parse_args()

    checks = collect_environment_report()
    for check in checks:
        label = "OK" if check.ok else "MISS"
        required = "required" if check.required else "optional"
        details = check.version or str(check.path or "") or check.message
        print(f"[{label}] {check.name} ({required}) {details}".rstrip())

    if args.strict and has_missing_required_checks(checks):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
