import tempfile
import unittest
from pathlib import Path

from tests.desktop.temp_utils import workspace_tempdir


class DesktopDownloaderTests(unittest.TestCase):
    def test_downloader_builds_ytdlp_options_with_download_dir(self):
        with workspace_tempdir() as tmp:
            from desktop.core.downloader import DesktopDownloader

            download_dir = Path(tmp)
            downloader = DesktopDownloader(download_dir=download_dir)
            opts = downloader.build_ytdlp_options()

            self.assertIn(str(download_dir), opts["outtmpl"])

    def test_downloader_injects_cookie_file_and_ffmpeg_location(self):
        with workspace_tempdir() as tmp:
            from desktop.core.downloader import DesktopDownloader

            root = Path(tmp)
            cookies = root / "cookies.txt"
            ffmpeg = root / "bin" / "ffmpeg.exe"
            downloader = DesktopDownloader(
                download_dir=root / "downloads",
                cookies_file=cookies,
                ffmpeg_path=ffmpeg,
            )
            opts = downloader.build_ytdlp_options()

            self.assertEqual(opts["cookiefile"], str(cookies))
            self.assertEqual(opts["ffmpeg_location"], str(ffmpeg.parent))

    def test_downloader_uses_browser_cookies_when_no_cookie_file_exists(self):
        with workspace_tempdir() as tmp:
            from desktop.core.downloader import DesktopDownloader

            downloader = DesktopDownloader(
                download_dir=Path(tmp),
                browser_cookie_source="edge",
            )
            opts = downloader.build_ytdlp_options()

            self.assertEqual(("edge",), opts["cookiesfrombrowser"])
            self.assertNotIn("cookiefile", opts)

    def test_downloader_prefers_manual_cookie_file_over_browser_source(self):
        with workspace_tempdir() as tmp:
            from desktop.core.downloader import DesktopDownloader

            root = Path(tmp)
            cookies = root / "cookies.txt"
            downloader = DesktopDownloader(
                download_dir=root / "downloads",
                cookies_file=cookies,
                browser_cookie_source="edge",
            )
            opts = downloader.build_ytdlp_options()

            self.assertEqual(str(cookies), opts["cookiefile"])
            self.assertNotIn("cookiesfrombrowser", opts)

    def test_progress_hook_raises_cancel_when_cancel_requested(self):
        with workspace_tempdir() as tmp:
            from desktop.core.downloader import DesktopDownloader, DownloadCanceled
            from desktop.core.tasks import DesktopTask

            task = DesktopTask.create(url="https://example.com/video")
            downloader = DesktopDownloader(download_dir=Path(tmp))
            opts = downloader.build_ytdlp_options(
                task=task,
                should_cancel=lambda: True,
            )

            with self.assertRaises(DownloadCanceled):
                opts["progress_hooks"][0]({"status": "downloading"})

            self.assertEqual("canceled", task.status)


if __name__ == "__main__":
    unittest.main()
