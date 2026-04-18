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


class DownloadTaskCancellationStateTest(unittest.TestCase):
    def test_task_can_record_cancel_request(self):
        task = DownloadTask("cancel1", "https://example.com/v", "client")

        task.request_cancel("用户取消下载")

        self.assertTrue(task.cancel_requested)
        self.assertEqual(task.cancel_reason, "用户取消下载")


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

    def test_preflight_size_limit_sums_split_audio_video_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloader = self.make_downloader(Path(tmp))
            info = {
                "requested_formats": [
                    {"filesize": 6},
                    {"filesize": 5},
                ]
            }

            with self.assertRaises(ValueError):
                downloader._enforce_preflight_size_limit(info, max_size_bytes=10)

    def test_preflight_size_limit_allows_unknown_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloader = self.make_downloader(Path(tmp))
            info = {"requested_formats": [{"format_id": "video"}, {"format_id": "audio"}]}

            downloader._enforce_preflight_size_limit(info, max_size_bytes=10)

    def test_progress_hook_aborts_when_split_artifacts_exceed_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            downloader = self.make_downloader(root)
            split_video = root / "Example.f137.mp4"
            split_audio = root / "Example.f140.m4a"
            split_video.write_bytes(b"123456")
            split_audio.write_bytes(b"12345")
            task = DownloadTask("limit1", "https://example.com/v", "client")
            hook = downloader._make_progress_hook(task, max_size_bytes=10)

            with self.assertRaises(ValueError):
                hook({
                    "status": "downloading",
                    "filename": str(split_audio),
                    "downloaded_bytes": 5,
                    "total_bytes": 5,
                })
