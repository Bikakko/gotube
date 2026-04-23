import tempfile
import unittest
from pathlib import Path

from server.health_checks import collect_runtime_health, read_runtime_logs


COOKIE_HEADER = "# Netscape HTTP Cookie File\n"


class HealthChecksTests(unittest.TestCase):
    def test_health_check_reports_runtime_cookie_source_and_writable_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            download_dir = root / "downloads"
            download_dir.mkdir()
            (root / "VERSION").write_text("4.2.1", encoding="utf-8")
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
            self.assertEqual(result["version"], "4.2.1")
            self.assertIn("ffmpeg_summary", result)
            self.assertIn("yt_dlp_summary", result)
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

    def test_read_runtime_logs_splits_app_and_access_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_path = root / "server.log"
            log_path.write_text(
                "\n".join([
                    '2026-04-23 10:00:00 [INFO] server.main: app started',
                    'time="[23/Apr/2026:10:00:01 +0800]" remote="127.0.0.1" method="GET" path="/" query="" status=200 bytes=123 referer="-" agent="ua"',
                    '2026-04-23 10:00:02 [ERROR] server.downloader: failed job',
                    'time="[23/Apr/2026:10:00:03 +0800]" remote="127.0.0.1" method="GET" path="/health" query="" status=200 bytes=45 referer="-" agent="ua"',
                ]),
                encoding="utf-8",
            )

            app_logs = read_runtime_logs(log_path=log_path, log_type="app", line_limit=10)
            access_logs = read_runtime_logs(log_path=log_path, log_type="access", line_limit=10)

            self.assertEqual(app_logs["type"], "app")
            self.assertEqual(access_logs["type"], "access")
            self.assertEqual(len(app_logs["lines"]), 2)
            self.assertEqual(len(access_logs["lines"]), 2)
            self.assertIn("app started", app_logs["lines"][0])
            self.assertIn('path="/"', access_logs["lines"][0])

    def test_read_runtime_logs_handles_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = read_runtime_logs(log_path=root / "missing.log", log_type="app", line_limit=5)

            self.assertEqual(result["type"], "app")
            self.assertEqual(result["lines"], [])
            self.assertFalse(result["exists"])


if __name__ == "__main__":
    unittest.main()
