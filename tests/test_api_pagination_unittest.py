import asyncio
import unittest
from datetime import UTC, datetime

from server.api import get_tasks
from server.downloader import DownloadTask


class ApiPaginationTests(unittest.TestCase):
    class _Queue:
        def __init__(self, tasks):
            self._tasks = tasks

        def get_client_tasks(self, client_id):
            return list(self._tasks)

    def test_get_tasks_supports_pagination_metadata(self):
        tasks = []
        for index in range(3):
            task = DownloadTask(f"task-{index}", f"https://example.test/{index}", "client-1")
            task.created_at = datetime.now(UTC)
            tasks.append(task)

        result = asyncio.run(get_tasks(client_id="client-1", page=2, per_page=1, qm=self._Queue(tasks)))

        self.assertEqual(result["total"], 3)
        self.assertEqual(result["page"], 2)
        self.assertEqual(result["per_page"], 1)
        self.assertEqual(result["total_pages"], 3)
        self.assertEqual(len(result["tasks"]), 1)
        self.assertEqual(result["tasks"][0].task_id, "task-1")


if __name__ == "__main__":
    unittest.main()
