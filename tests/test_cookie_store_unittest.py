import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server import cookie_store
from server.downloader import Downloader


COOKIE_HEADER = "# Netscape HTTP Cookie File\n"


class FakeSettings:
    def __init__(self, project_root: Path, env_cookie: Path | None) -> None:
        self.project_root = project_root
        self._env_cookie = env_cookie

    def get_cookies_file(self) -> Path | None:
        return self._env_cookie if self._env_cookie and self._env_cookie.exists() else None


class CookieStoreTests(unittest.TestCase):
    def test_runtime_cookie_imports_env_cookie_once_into_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_cookie = root / "cookies.txt"
            env_content = COOKIE_HEADER + ".example.com\tTRUE\t/\tTRUE\t0\tSID\tenv\n"
            env_cookie.write_text(env_content, encoding="utf-8")

            with patch.object(cookie_store, "settings", FakeSettings(root, env_cookie)):
                runtime_cookie = cookie_store.get_runtime_cookies_file()

            uploaded_cookie = root / "data" / "cookies.txt"
            self.assertEqual(runtime_cookie, uploaded_cookie)
            self.assertEqual(uploaded_cookie.read_text(encoding="utf-8"), env_content)
            self.assertEqual(env_cookie.read_text(encoding="utf-8"), env_content)

    def test_runtime_cookie_prefers_uploaded_cookie_over_env_cookie(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_cookie = root / "cookies.txt"
            uploaded_cookie = root / "data" / "cookies.txt"
            env_cookie.write_text(COOKIE_HEADER + ".env.test\tTRUE\t/\tTRUE\t0\tSID\tenv\n", encoding="utf-8")
            uploaded_cookie.parent.mkdir(parents=True)
            uploaded_cookie.write_text(COOKIE_HEADER + ".upload.test\tTRUE\t/\tTRUE\t0\tSID\tupload\n", encoding="utf-8")

            with patch.object(cookie_store, "settings", FakeSettings(root, env_cookie)):
                self.assertEqual(cookie_store.get_runtime_cookies_file(), uploaded_cookie)
                uploaded_cookie.unlink()
                self.assertIsNone(cookie_store.get_runtime_cookies_file())

    def test_deleted_uploaded_cookie_does_not_fall_back_to_env_cookie(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_cookie = root / "cookies.txt"
            uploaded_cookie = root / "data" / "cookies.txt"
            env_cookie.write_text(COOKIE_HEADER + ".env.test\tTRUE\t/\tTRUE\t0\tSID\tenv\n", encoding="utf-8")
            uploaded_cookie.parent.mkdir(parents=True)
            uploaded_cookie.write_text(COOKIE_HEADER + ".upload.test\tTRUE\t/\tTRUE\t0\tSID\tupload\n", encoding="utf-8")

            with patch.object(cookie_store, "settings", FakeSettings(root, env_cookie)):
                self.assertTrue(cookie_store.delete_uploaded_cookies_file())
                self.assertIsNone(cookie_store.get_runtime_cookies_file())

            self.assertTrue(env_cookie.exists())
            self.assertFalse(uploaded_cookie.exists())

    def test_downloader_uses_runtime_cookie_source_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_cookie = root / "cookies.txt"
            env_cookie.write_text(COOKIE_HEADER + ".env.test\tTRUE\t/\tTRUE\t0\tSID\tenv\n", encoding="utf-8")

            with patch.object(cookie_store, "settings", FakeSettings(root, env_cookie)):
                with patch("server.downloader.get_runtime_cookies_file", cookie_store.get_runtime_cookies_file):
                    downloader = Downloader(download_dir=root / "downloads")

            self.assertEqual(downloader.cookies_file, root / "data" / "cookies.txt")


if __name__ == "__main__":
    unittest.main()
