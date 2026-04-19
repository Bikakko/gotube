import unittest

from server.cookie_store import diagnose_cookie_content


COOKIE_HEADER = "# Netscape HTTP Cookie File\n"


class CookieDiagnosticsTests(unittest.TestCase):
    def test_cookie_diagnostics_reports_presence_without_values(self):
        content = (
            COOKIE_HEADER
            +
            ".bilibili.com\tTRUE\t/\tTRUE\t0\tSESSDATA\tbili-secret\n"
            ".x.com\tTRUE\t/\tTRUE\t0\tauth_token\tx-secret\n"
        )

        result = diagnose_cookie_content(content)

        self.assertFalse(result["bilibili"]["has_required"])
        self.assertEqual(result["bilibili"]["present"], ["SESSDATA"])
        self.assertIn("bili_jct", result["bilibili"]["missing"])
        self.assertFalse(result["twitter"]["has_required"])
        self.assertEqual(result["twitter"]["present"], ["auth_token"])
        self.assertNotIn("bili-secret", str(result))
        self.assertNotIn("x-secret", str(result))

    def test_cookie_diagnostics_marks_platform_complete_when_required_names_exist(self):
        content = (
            COOKIE_HEADER
            +
            ".bilibili.com\tTRUE\t/\tTRUE\t0\tSESSDATA\tsecret\n"
            ".bilibili.com\tTRUE\t/\tTRUE\t0\tbili_jct\tsecret\n"
            ".bilibili.com\tTRUE\t/\tTRUE\t0\tDedeUserID\tsecret\n"
            ".x.com\tTRUE\t/\tTRUE\t0\tauth_token\tsecret\n"
            ".x.com\tTRUE\t/\tTRUE\t0\tct0\tsecret\n"
            ".youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\tsecret\n"
            ".youtube.com\tTRUE\t/\tTRUE\t0\t__Secure-1PSID\tsecret\n"
            ".youtube.com\tTRUE\t/\tTRUE\t0\t__Secure-3PSID\tsecret\n"
        )

        result = diagnose_cookie_content(content)

        self.assertTrue(result["bilibili"]["has_required"])
        self.assertTrue(result["twitter"]["has_required"])
        self.assertTrue(result["youtube"]["has_required"])
        self.assertEqual(result["youtube"]["missing"], [])

    def test_cookie_diagnostics_ignores_malformed_lines(self):
        result = diagnose_cookie_content(COOKIE_HEADER + "malformed\n")

        self.assertFalse(result["bilibili"]["has_required"])
        self.assertEqual(result["bilibili"]["present"], [])
        self.assertEqual(result["bilibili"]["domains"], [])


if __name__ == "__main__":
    unittest.main()
