import tempfile
import unittest
from pathlib import Path


class DesktopDownloaderTests(unittest.TestCase):
    def test_downloader_builds_ytdlp_options_with_download_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            from desktop.core.downloader import DesktopDownloader

            download_dir = Path(tmp)
            downloader = DesktopDownloader(download_dir=download_dir)
            opts = downloader.build_ytdlp_options()

            self.assertIn(str(download_dir), opts["outtmpl"])

    def test_downloader_injects_cookie_file_and_ffmpeg_location(self):
        with tempfile.TemporaryDirectory() as tmp:
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


if __name__ == "__main__":
    unittest.main()
