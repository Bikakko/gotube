"""Environment diagnostics for GoTube Desktop."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .tools import ToolStatus, detect_ffmpeg, detect_ytdlp


@dataclass(slots=True)
class EnvironmentCheck:
    name: str
    ok: bool
    required: bool = True
    version: str = ""
    path: Path | None = None
    message: str = ""


def check_python_package(
    import_name: str,
    *,
    display_name: str | None = None,
    distribution_name: str | None = None,
    required: bool = True,
) -> EnvironmentCheck:
    name = display_name or distribution_name or import_name
    if importlib.util.find_spec(import_name) is None:
        return EnvironmentCheck(
            name=name,
            ok=False,
            required=required,
            message=f"未安装 Python 依赖：{name}",
        )

    version = ""
    package_name = distribution_name or import_name
    try:
        version = importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        version = ""

    return EnvironmentCheck(
        name=name,
        ok=True,
        required=required,
        version=version,
        message=f"已检测到 Python 依赖：{name}",
    )


def check_executable(
    command: str,
    *,
    args: list[str] | None = None,
    display_name: str | None = None,
    required: bool = True,
) -> EnvironmentCheck:
    name = display_name or command
    resolved = shutil.which(command)
    if not resolved:
        return EnvironmentCheck(
            name=name,
            ok=False,
            required=required,
            message=f"未找到命令：{name}",
        )

    version = ""
    if args is not None:
        version = _command_first_line([resolved, *args])

    return EnvironmentCheck(
        name=name,
        ok=True,
        required=required,
        version=version,
        path=Path(resolved),
        message=f"已检测到命令：{name}",
    )


def collect_environment_report() -> list[EnvironmentCheck]:
    ytdlp = _from_tool_status(detect_ytdlp(), required=True)
    ffmpeg = _from_tool_status(detect_ffmpeg(), required=False)

    return [
        check_python_package(
            "webview",
            display_name="pywebview",
            distribution_name="pywebview",
            required=True,
        ),
        ytdlp,
        check_python_package("PyInstaller", display_name="pyinstaller", required=True),
        ffmpeg,
        check_executable("node", args=["--version"], required=False),
    ]


def has_missing_required_checks(checks: list[EnvironmentCheck]) -> bool:
    return any(check.required and not check.ok for check in checks)


def _from_tool_status(status: ToolStatus, *, required: bool) -> EnvironmentCheck:
    return EnvironmentCheck(
        name=status.name,
        ok=status.available,
        required=required,
        version=status.version,
        path=status.path,
        message=status.message,
    )


def _command_first_line(args: list[str]) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    lines = (result.stdout or result.stderr or "").splitlines()
    return lines[0] if lines else ""
