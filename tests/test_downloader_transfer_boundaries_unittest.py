import asyncio
import tempfile
import unittest
from pathlib import Path

from server.downloader import DownloadTask, Downloader


class DownloaderTransferBoundariesTest(unittest.IsolatedAsyncioTestCase):
    def make_downloader(self, root: Path) -> Downloader:
        return Downloader(download_dir=root, cookies_file=None)

    async def test_short_download_pushes_progress_before_impl_finishes(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloader = self.make_downloader(Path(tmp))
            task = DownloadTask("short1", "https://example.com/v", "client")
            task.status = "downloading"
            events = []

            async def fake_impl(url, task):
                task.downloaded_bytes = 100
                task.total_bytes = 100
                task.progress = 100.0
                return str(Path(tmp) / "video.mp4")

            async def progress_callback(task):
                events.append((task.status, task.progress, task.downloaded_bytes))

            downloader._do_download_impl = fake_impl

            await downloader._do_download(task.url, task, progress_callback)

            self.assertGreaterEqual(len(events), 1)
            self.assertEqual(events[0][0], "downloading")

    async def test_large_download_pushes_when_bytes_change_without_percent_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloader = self.make_downloader(Path(tmp))
            task = DownloadTask("large1", "https://example.com/v", "client")
            task.status = "downloading"
            events = []

            async def fake_impl(url, task):
                for _ in range(3):
                    task.downloaded_bytes += 1024
                    await asyncio.sleep(0.25)
                return str(Path(tmp) / "video.mp4")

            async def progress_callback(task):
                events.append((task.progress, task.downloaded_bytes))

            downloader._do_download_impl = fake_impl

            await downloader._do_download(task.url, task, progress_callback)

            self.assertTrue(any(downloaded > 0 for _, downloaded in events))


class DownloaderArtifactCleanupTest(unittest.TestCase):
    def make_downloader(self, root: Path) -> Downloader:
        return Downloader(download_dir=root, cookies_file=None)

    def test_cleanup_download_artifacts_removes_split_media_siblings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            downloader = self.make_downloader(root)
            final_file = root / "Example.mp4"
            split_video = root / "Example.f137.mp4"
            split_audio = root / "Example.f140.m4a"
            partial = root / "Example.mp4.part"
            unrelated = root / "Other.f140.m4a"
            for path in [final_file, split_video, split_audio, partial, unrelated]:
                path.write_bytes(b"x")

            task = DownloadTask("cleanup1", "https://example.com/v", "client")
            removed = downloader.cleanup_download_artifacts(task, temp_file=str(final_file))

            self.assertEqual(removed, 4)
            self.assertFalse(final_file.exists())
            self.assertFalse(split_video.exists())
            self.assertFalse(split_audio.exists())
            self.assertFalse(partial.exists())
            self.assertTrue(unrelated.exists())

    def test_final_size_limit_uses_merged_file_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            downloader = self.make_downloader(root)
            final_file = root / "Example.mp4"
            final_file.write_bytes(b"12345")

            with self.assertRaises(ValueError):
                downloader._enforce_final_size_limit(str(final_file), max_size_bytes=4)
