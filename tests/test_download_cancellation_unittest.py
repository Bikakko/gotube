import asyncio
import tempfile
import unittest
from pathlib import Path

from server.downloader import Downloader
from server.queue_manager import QueueManager


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
