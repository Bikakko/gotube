import tempfile
import unittest
from pathlib import Path

from server.health_checks import collect_runtime_health


COOKIE_HEADER = "# Netscape HTTP Cookie File\n"


class HealthChecksTests(unittest.TestCase):
    def test_health_check_reports_runtime_cookie_source_and_writable_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            download_dir = root / "downloads"
            download_dir.mkdir()
            db_path = root / "gotube.db"
            db_path.write_bytes(b"")
            cookies_path = root / "data" / "cookies.txt"
            cookies_path.parent.mkdir()
            cookies_path.write_text(
                COOKIE_HEADER + ".bilibili.com\tTRUE\t/\tTRUE\t0\tSESSDATA\tsecret\n",
                encoding="utf-8",
            )

            result = collect_runtime_health(
                project_root=root,
                download_dir=download_dir,
                db_path=db_path,
                cookies_path=cookies_path,
            )

            self.assertEqual(result["cookie_source"], "upload")
            self.assertTrue(result["cookie_file_exists"])
            self.assertIn("cookie_diagnostics", result)
            self.assertTrue(result["download_dir_writable"])
            self.assertTrue(result["database_writable"])
            self.assertIn("ffmpeg_available", result)
            self.assertIn("yt_dlp_version", result)
            self.assertIn("blockers", result)
            self.assertNotIn("secret", str(result))

    def test_health_check_reports_missing_cookie_as_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            download_dir = root / "downloads"
            download_dir.mkdir()

            result = collect_runtime_health(
                project_root=root,
                download_dir=download_dir,
                db_path=root / "gotube.db",
                cookies_path=None,
            )

            self.assertEqual(result["cookie_source"], "none")
            self.assertFalse(result["cookie_file_exists"])
            self.assertFalse(result["cookie_diagnostics"]["bilibili"]["has_required"])


if __name__ == "__main__":
    unittest.main()
