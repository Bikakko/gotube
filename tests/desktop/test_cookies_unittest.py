import tempfile
import unittest
from pathlib import Path


COOKIE_HEADER = "# Netscape HTTP Cookie File\n"


class DesktopCookieTests(unittest.TestCase):
    def test_save_manual_cookie_rejects_invalid_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            from desktop.core.cookies import DesktopCookieStore

            store = DesktopCookieStore(Path(tmp))
            result = store.save_manual_cookie("not a netscape cookie file")

            self.assertFalse(result.ok)
            self.assertFalse(store.cookie_file.exists())

    def test_save_manual_cookie_writes_valid_netscape_cookie(self):
        with tempfile.TemporaryDirectory() as tmp:
            from desktop.core.cookies import DesktopCookieStore

            store = DesktopCookieStore(Path(tmp))
            content = COOKIE_HEADER + ".youtube.com\tTRUE\t/\tTRUE\t0\tSID\tsecret\n"
            result = store.save_manual_cookie(content)

            self.assertTrue(result.ok)
            self.assertEqual(store.cookie_file.read_text(encoding="utf-8"), content)

    def test_delete_cookie_file_removes_saved_cookie(self):
        with tempfile.TemporaryDirectory() as tmp:
            from desktop.core.cookies import DesktopCookieStore

            store = DesktopCookieStore(Path(tmp))
            store.cookie_file.write_text(COOKIE_HEADER, encoding="utf-8")
            result = store.delete_cookie_file()

            self.assertTrue(result.ok)
            self.assertFalse(store.cookie_file.exists())

    def test_import_from_browser_returns_structured_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            from desktop.core.cookies import DesktopCookieStore

            store = DesktopCookieStore(Path(tmp))
            result = store.import_from_browser("edge")

            self.assertIsInstance(result.ok, bool)
            self.assertTrue(result.message)


if __name__ == "__main__":
    unittest.main()
