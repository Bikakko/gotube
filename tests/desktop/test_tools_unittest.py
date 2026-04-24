import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.desktop.temp_utils import workspace_tempdir


class DesktopToolsTests(unittest.TestCase):
    def test_ffmpeg_detection_accepts_configured_executable(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_text("", encoding="utf-8")

            from desktop.core.tools import detect_ffmpeg

            result = detect_ffmpeg(configured_path=ffmpeg)

            self.assertTrue(result.available)
            self.assertEqual(result.path, ffmpeg)
            self.assertEqual(result.source, "configured")

    def test_ffmpeg_detection_reports_missing_configured_path(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)

            from desktop.core.tools import detect_ffmpeg

            result = detect_ffmpeg(configured_path=root / "missing.exe")

            self.assertFalse(result.available)
            self.assertIn("未找到", result.message)

    def test_ytdlp_detection_reads_installed_python_package_version(self):
        from desktop.core.tools import detect_ytdlp

        result = detect_ytdlp()

        self.assertIsInstance(result.available, bool)
        if result.available:
            self.assertTrue(result.version)

    def test_upgrade_ytdlp_returns_structured_failure(self):
        from desktop.core.tools import upgrade_ytdlp

        with patch("subprocess.run") as run:
            run.side_effect = OSError("blocked")

            result = upgrade_ytdlp(python_executable=sys.executable)

        self.assertFalse(result.ok)
        self.assertIn("blocked", result.message)


if __name__ == "__main__":
    unittest.main()
