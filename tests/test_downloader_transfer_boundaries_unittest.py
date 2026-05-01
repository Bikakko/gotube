import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.downloader import DownloadCancelledError, DownloadTask, Downloader


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

    async def test_guest_transfer_copies_file_when_windows_move_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            downloader = self.make_downloader(root)
            session_id = "guest_abc_abcd1234"
            session_dir = root / "temp_guest" / session_id
            video_dir = session_dir / "LockedVideo_12345678"
            video_file = video_dir / "12345678.mp4"
            meta_file = video_dir / "meta.json"
            video_dir.mkdir(parents=True)
            video_file.write_bytes(b"video")
            meta_file.write_text("{}", encoding="utf-8")

            def locked_move(source, target):
                raise OSError(32, "另一个程序正在使用此文件")

            with patch("server.downloader.shutil.move", side_effect=locked_move):
                result = downloader.transfer_guest_session(session_id)

            target_file = root / "LockedVideo_12345678" / "12345678.mp4"
            target_meta = root / "LockedVideo_12345678" / "meta.json"

            self.assertEqual(result["transferred_count"], 1)
            self.assertEqual(result["errors"], [])
            self.assertTrue(target_file.exists())
            self.assertEqual(target_file.read_bytes(), b"video")
            self.assertTrue(target_meta.exists())


class DownloadTaskCancellationStateTest(unittest.IsolatedAsyncioTestCase):
    def test_task_can_record_cancel_request(self):
        task = DownloadTask("cancel1", "https://example.com/v", "client")

        task.request_cancel("用户取消下载")

        self.assertTrue(task.cancel_requested)
        self.assertEqual(task.cancel_reason, "用户取消下载")

    def test_progress_hook_raises_when_task_cancel_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloader = Downloader(download_dir=Path(tmp), cookies_file=None)
            task = DownloadTask("cancel2", "https://example.com/v", "client")
            task.request_cancel("用户取消下载")
            hook = downloader._make_progress_hook(task)

            with self.assertRaises(DownloadCancelledError) as ctx:
                hook({"status": "downloading", "downloaded_bytes": 1, "total_bytes": 10})

            self.assertIn("用户取消下载", str(ctx.exception))

    async def test_download_marks_cancelled_and_cleans_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            downloader = Downloader(download_dir=root, cookies_file=None)
            task = DownloadTask("cancel3", "https://example.com/v", "client")
            artifact = root / "Example.mp4.part"
            artifact.write_bytes(b"x")
            task.download_artifact_path = str(artifact)
            events = []

            async def fake_do_download(url, task, progress_callback):
                task.request_cancel("用户取消下载")
                raise DownloadCancelledError("用户取消下载")

            async def fake_extract_info(url, task):
                task.title = "Example"
                return {}

            async def progress_callback(task):
                events.append((task.status, task.error))

            downloader._extract_info = fake_extract_info
            downloader._do_download = fake_do_download

            await downloader.download(task, progress_callback)

            self.assertEqual(task.status, "cancelled")
            self.assertEqual(task.error, "用户取消下载")
            self.assertFalse(artifact.exists())
            self.assertIn(("cancelled", "用户取消下载"), events)


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

    def test_progress_hook_weights_split_media_phases_instead_of_restarting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            downloader = self.make_downloader(root)
            task = DownloadTask("phase1", "https://example.com/v", "client")
            task.download_phase_count = 2
            hook = downloader._make_progress_hook(task)
            video_part = root / "Example.f137.mp4"
            audio_part = root / "Example.f140.m4a"

            hook({
                "status": "downloading",
                "filename": str(video_part),
                "downloaded_bytes": 5,
                "total_bytes": 10,
            })
            self.assertAlmostEqual(task.progress, 25.0)

            hook({
                "status": "finished",
                "filename": str(video_part),
            })
            self.assertAlmostEqual(task.progress, 50.0)

            hook({
                "status": "downloading",
                "filename": str(audio_part),
                "downloaded_bytes": 5,
                "total_bytes": 10,
            })
            self.assertAlmostEqual(task.progress, 75.0)

            hook({
                "status": "finished",
                "filename": str(audio_part),
            })
            self.assertAlmostEqual(task.progress, 100.0)
