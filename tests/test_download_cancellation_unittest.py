import asyncio
import tempfile
import unittest
from pathlib import Path

from server.downloader import Downloader
from server.queue_manager import QueueManager


ROOT = Path(__file__).resolve().parents[1]


class DownloadCancellationApiContractTests(unittest.TestCase):
    def test_api_exposes_cancel_endpoints(self):
        source = (ROOT / "server" / "api.py").read_text(encoding="utf-8")

        self.assertIn('@router.get("/tasks/active"', source)
        self.assertIn('@router.post("/tasks/cancel-active"', source)
        self.assertIn('@router.post("/tasks/{task_id}/cancel"', source)

    def test_cancel_active_route_precedes_dynamic_cancel_route(self):
        source = (ROOT / "server" / "api.py").read_text(encoding="utf-8")

        cancel_active_idx = source.find('@router.post("/tasks/cancel-active"')
        dynamic_cancel_idx = source.find('@router.post("/tasks/{task_id}/cancel"')

        self.assertGreaterEqual(cancel_active_idx, 0)
        self.assertGreater(dynamic_cancel_idx, cancel_active_idx)

    def test_guest_disconnect_cleanup_cancels_active_tasks_before_directory_cleanup(self):
        source = (ROOT / "server" / "main.py").read_text(encoding="utf-8")

        cancel_idx = source.find("cancel_guest_session_tasks")
        cleanup_idx = source.find("cleanup_guest_session")

        self.assertGreaterEqual(cancel_idx, 0)
        self.assertGreater(cleanup_idx, cancel_idx)


class DownloadCancellationIndexTests(unittest.IsolatedAsyncioTestCase):
    async def test_running_task_is_indexed_by_client_and_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloader = Downloader(download_dir=Path(tmp), cookies_file=None)
            qm = QueueManager(downloader, max_concurrent=1)
            started = asyncio.Event()
            release = asyncio.Event()

            async def fake_download(task, callback):
                task.status = "downloading"
                started.set()
                await release.wait()

            downloader.download = fake_download

            task = await qm.add_task(
                "https://example.com/v",
                "client-a",
                session_id="guest_abcdefghijklmnop",
            )
            await started.wait()

            self.assertIn(
                task.task_id,
                {t.task_id for t in qm.get_active_tasks_for_client("client-a")},
            )
            self.assertIn(
                task.task_id,
                {t.task_id for t in qm.get_active_tasks_for_guest_session("guest_abcdefghijklmnop")},
            )

            release.set()

    async def test_cancel_client_active_tasks_marks_cancel_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloader = Downloader(download_dir=Path(tmp), cookies_file=None)
            qm = QueueManager(downloader, max_concurrent=1)
            started = asyncio.Event()
            release = asyncio.Event()

            async def fake_download(task, callback):
                task.status = "downloading"
                started.set()
                await release.wait()

            downloader.download = fake_download
            task = await qm.add_task("https://example.com/v", "client-a")
            await started.wait()

            cancelled = qm.cancel_client_tasks("client-a", "退出登录时取消")

            self.assertEqual(cancelled, 1)
            self.assertTrue(task.cancel_requested)
            self.assertEqual(task.status, "cancelled")
            self.assertEqual(task.error, "退出登录时取消")
            self.assertEqual(qm.get_active_tasks_for_client("client-a"), [])

            release.set()

    async def test_cancel_guest_session_active_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloader = Downloader(download_dir=Path(tmp), cookies_file=None)
            qm = QueueManager(downloader, max_concurrent=1)
            started = asyncio.Event()
            release = asyncio.Event()

            async def fake_download(task, callback):
                task.status = "downloading"
                started.set()
                await release.wait()

            downloader.download = fake_download
            task = await qm.add_task(
                "https://example.com/v",
                "client-guest",
                session_id="guest_abcdefghijklmnop",
            )
            await started.wait()

            cancelled = qm.cancel_guest_session_tasks("guest_abcdefghijklmnop", "游客页面已关闭")

            self.assertEqual(cancelled, 1)
            self.assertTrue(task.cancel_requested)
            self.assertEqual(task.status, "cancelled")
            self.assertEqual(task.error, "游客页面已关闭")
            self.assertEqual(qm.get_active_tasks_for_guest_session("guest_abcdefghijklmnop"), [])

            release.set()

    async def test_running_task_is_indexed_by_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloader = Downloader(download_dir=Path(tmp), cookies_file=None)
            qm = QueueManager(downloader, max_concurrent=1)
            started = asyncio.Event()
            release = asyncio.Event()

            async def fake_download(task, callback):
                task.status = "downloading"
                started.set()
                await release.wait()

            downloader.download = fake_download

            task = await qm.add_task(
                "https://example.com/v",
                "client-user",
                owner_user_id=123,
            )
            await started.wait()

            self.assertIn(
                task.task_id,
                {t.task_id for t in qm.get_active_tasks_for_owner(123)},
            )

            release.set()


if __name__ == "__main__":
    unittest.main()
