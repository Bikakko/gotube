import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server import admin_api
from server.db import User


COOKIE_HEADER = "# Netscape HTTP Cookie File\n"


class FakeJsonRequest:
    def __init__(self, content: str):
        self.headers = {"Content-Type": "application/json"}
        self._content = content

    async def json(self):
        return {"content": self._content}


class CookieMergeTests(unittest.TestCase):
    def setUp(self):
        self.admin = User(username="admin", password_hash="x", role="admin", is_active=True)

    def test_merge_preserves_unmentioned_cookie_entries_from_same_domain(self):
        existing = (
            COOKIE_HEADER
            + ".youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\told-sapisid\n"
            + ".youtube.com\tTRUE\t/\tTRUE\t0\t__Secure-1PSID\told-1psid\n"
            + ".youtube.com\tTRUE\t/\tTRUE\t0\t__Secure-3PSID\told-3psid\n"
            + ".bilibili.com\tTRUE\t/\tTRUE\t0\tSESSDATA\told-bili\n"
        )
        new = COOKIE_HEADER + ".youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\tnew-sapisid\n"

        merged = admin_api._merge_cookies_content(existing, new)

        self.assertIn("SAPISID\tnew-sapisid", merged)
        self.assertIn("__Secure-1PSID\told-1psid", merged)
        self.assertIn("__Secure-3PSID\told-3psid", merged)
        self.assertIn("SESSDATA\told-bili", merged)
        self.assertNotIn("SAPISID\told-sapisid", merged)

    def test_check_merge_reports_cookie_level_changes(self):
        existing = (
            COOKIE_HEADER
            + ".youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\told-sapisid\n"
            + ".youtube.com\tTRUE\t/\tTRUE\t0\t__Secure-1PSID\told-1psid\n"
            + ".bilibili.com\tTRUE\t/\tTRUE\t0\tSESSDATA\told-bili\n"
        )
        new = (
            COOKIE_HEADER
            + ".youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\tnew-sapisid\n"
            + ".x.com\tTRUE\t/\tTRUE\t0\tauth_token\tnew-x\n"
        )

        with patch("server.admin_api._get_active_cookies_content", return_value=existing):
            result = asyncio.run(
                admin_api.check_cookies_merge(FakeJsonRequest(new), admin=self.admin)
            )

        self.assertEqual(result["will_replace"], [".youtube.com"])
        self.assertEqual(result["will_add"], [".x.com"])
        self.assertEqual(result["will_replace_cookie_count"], 1)
        self.assertEqual(result["will_add_cookie_count"], 1)
        self.assertEqual(result["will_preserve_cookie_count"], 2)
        self.assertTrue(any("SAPISID" in sample for sample in result["replace_cookie_samples"]))
        self.assertTrue(any("__Secure-1PSID" in sample for sample in result["preserve_cookie_samples"]))

    def test_upload_merge_keeps_existing_same_domain_records(self):
        existing = (
            COOKIE_HEADER
            + ".youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\told-sapisid\n"
            + ".youtube.com\tTRUE\t/\tTRUE\t0\t__Secure-1PSID\told-1psid\n"
            + ".youtube.com\tTRUE\t/\tTRUE\t0\t__Secure-3PSID\told-3psid\n"
        )
        new = COOKIE_HEADER + ".youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\tnew-sapisid\n"

        with tempfile.TemporaryDirectory() as tmp:
            cookies_path = Path(tmp) / "cookies.txt"
            cookies_path.write_text(existing, encoding="utf-8")

            with (
                patch("server.admin_api._get_active_cookies_content", return_value=existing),
                patch("server.admin_api._get_cookies_storage_path", return_value=cookies_path),
                patch("server.admin_api._backup_cookies_file", return_value=None),
                patch("server.admin_api._reload_cookies_in_downloader", return_value=None),
            ):
                result = asyncio.run(
                    admin_api.upload_cookies(
                        FakeJsonRequest(new),
                        mode="merge",
                        admin=self.admin,
                    )
                )

            merged = cookies_path.read_text(encoding="utf-8")

        self.assertEqual(result["status"], "ok")
        self.assertIn("Cookie", result["message"])
        self.assertIn("1", result["message"])
        self.assertIn("SAPISID\tnew-sapisid", merged)
        self.assertIn("__Secure-1PSID\told-1psid", merged)
        self.assertIn("__Secure-3PSID\told-3psid", merged)


if __name__ == "__main__":
    unittest.main()
