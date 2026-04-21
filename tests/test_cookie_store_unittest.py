import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from server import cookie_store
from server.health_checks import collect_runtime_health


COOKIE_HEADER = "# Netscape HTTP Cookie File\n"


class CookieStoreTests(unittest.TestCase):
    def test_runtime_cookie_import_from_env_marks_env_import_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            env_cookie = Path(tmp) / "env-cookies.txt"
            env_cookie.write_text(
                COOKIE_HEADER + ".youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\tsecret\n",
                encoding="utf-8",
            )

            with (
                patch("server.cookie_store.get_data_dir", return_value=data_dir),
                patch("server.cookie_store.settings", SimpleNamespace(get_cookies_file=lambda: env_cookie)),
            ):
                runtime = cookie_store.get_runtime_cookies_file()

                self.assertIsNotNone(runtime)
                self.assertTrue(runtime.exists())
                self.assertEqual(cookie_store.get_runtime_cookies_source(), "env_import")

    def test_runtime_cookie_delete_clears_source_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            runtime_cookie = data_dir / "cookies.txt"
            runtime_cookie.write_text(
                COOKIE_HEADER + ".x.com\tTRUE\t/\tTRUE\t0\tauth_token\tsecret\n",
                encoding="utf-8",
            )

            with patch("server.cookie_store.get_data_dir", return_value=data_dir):
                cookie_store.set_runtime_cookies_source("upload")
                self.assertEqual(cookie_store.get_runtime_cookies_source(), "upload")

                deleted = cookie_store.delete_uploaded_cookies_file()

                self.assertTrue(deleted)
                self.assertFalse(runtime_cookie.exists())
                self.assertFalse((data_dir / ".cookies_runtime_source").exists())

    def test_health_check_reports_env_import_cookie_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            download_dir = root / "downloads"
            download_dir.mkdir()
            db_path = root / "gotube.db"
            db_path.write_bytes(b"")
            cookies_path = root / "data" / "cookies.txt"
            cookies_path.parent.mkdir()
            cookies_path.write_text(
                COOKIE_HEADER
                + ".youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\tsecret\n"
                + ".youtube.com\tTRUE\t/\tTRUE\t0\t__Secure-1PSID\tsecret\n"
                + ".youtube.com\tTRUE\t/\tTRUE\t0\t__Secure-3PSID\tsecret\n",
                encoding="utf-8",
            )

            with (
                patch("server.health_checks.get_active_cookies_file_for_status", return_value=cookies_path),
                patch("server.health_checks.get_runtime_cookies_source", return_value="env_import"),
            ):
                result = collect_runtime_health(
                    project_root=root,
                    download_dir=download_dir,
                    db_path=db_path,
                )

            self.assertEqual(result["cookie_source"], "env_import")
            self.assertTrue(result["cookie_file_exists"])


if __name__ == "__main__":
    unittest.main()
