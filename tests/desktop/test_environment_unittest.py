import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from desktop.core.environment import (
    EnvironmentCheck,
    check_executable,
    check_python_package,
    collect_environment_report,
    has_missing_required_checks,
)
from desktop.core.tools import ToolStatus


class DesktopEnvironmentTests(unittest.TestCase):
    def test_check_python_package_reports_missing_package(self):
        with patch("importlib.util.find_spec", return_value=None):
            check = check_python_package("missing_package", display_name="missing")

        self.assertEqual("missing", check.name)
        self.assertFalse(check.ok)
        self.assertTrue(check.required)
        self.assertIn("未安装", check.message)

    def test_check_python_package_reports_available_package(self):
        check = check_python_package("sys", display_name="python-runtime", required=False)

        self.assertEqual("python-runtime", check.name)
        self.assertTrue(check.ok)
        self.assertFalse(check.required)

    def test_check_executable_reports_missing_command(self):
        with patch("shutil.which", return_value=None):
            check = check_executable("missing-tool")

        self.assertEqual("missing-tool", check.name)
        self.assertFalse(check.ok)
        self.assertIn("未找到", check.message)

    def test_check_executable_reports_available_command(self):
        check = check_executable(sys.executable, args=["--version"], display_name="python")

        self.assertEqual("python", check.name)
        self.assertTrue(check.ok)
        self.assertTrue(check.version)
        self.assertTrue(check.path)

    def test_collect_environment_report_includes_desktop_runtime_checks(self):
        with (
            patch("desktop.core.environment.detect_ytdlp") as detect_ytdlp,
            patch("desktop.core.environment.detect_ffmpeg") as detect_ffmpeg,
            patch("desktop.core.environment.check_python_package") as package_check,
        ):
            detect_ytdlp.return_value = ToolStatus(name="yt-dlp", available=True, version="1.0")
            detect_ffmpeg.return_value = ToolStatus(name="ffmpeg", available=False, message="missing")
            package_check.side_effect = [
                EnvironmentCheck(name="PySide6", ok=True),
                EnvironmentCheck(name="pyinstaller", ok=True),
            ]

            report = collect_environment_report()

        names = [check.name for check in report]
        self.assertEqual(["PySide6", "yt-dlp", "pyinstaller", "ffmpeg"], names)
        self.assertFalse(report[3].required)
        self.assertFalse(has_missing_required_checks(report))

    def test_desktop_doctor_script_exists_and_supports_strict_mode(self):
        script = Path("scripts/desktop_doctor.py").read_text(encoding="utf-8")

        self.assertIn("collect_environment_report", script)
        self.assertIn("--strict", script)
        self.assertIn("has_missing_required_checks", script)


if __name__ == "__main__":
    unittest.main()
