import unittest
from pathlib import Path

from server.downloader import Downloader


class DownloaderErrorMessageTests(unittest.TestCase):
    def test_bilibili_412_points_to_cookie_or_risk_control(self):
        with self.subTest("Bilibili HTTP 412"):
            downloader = Downloader(download_dir=Path("downloads"), cookies_file=None)
            message = downloader._format_error_message(
                Exception(
                    "[BiliBili] 1QsBXB8Ez8: Unable to download webpage: "
                    "HTTP Error 412: Precondition Failed"
                )
            )

            self.assertIn("B 站", message)
            self.assertIn("Cookie", message)
            self.assertIn("412", message)


if __name__ == "__main__":
    unittest.main()
