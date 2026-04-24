import unittest


class DesktopTaskTests(unittest.TestCase):
    def test_task_transitions_from_pending_to_running(self):
        from desktop.core.tasks import DesktopTask

        task = DesktopTask.create(url="https://example.test/video")
        task.mark_running()

        self.assertEqual(task.status, "running")

    def test_task_records_progress_and_completion(self):
        from desktop.core.tasks import DesktopTask

        task = DesktopTask.create(url="https://example.test/video")
        task.update_progress(percent=42.5, speed="1.2MiB/s", eta="00:10")
        task.mark_completed(file_path="D:/Videos/out.mp4")

        self.assertEqual(task.percent, 100.0)
        self.assertEqual(task.status, "completed")
        self.assertEqual(task.file_path, "D:/Videos/out.mp4")

    def test_task_records_failure(self):
        from desktop.core.tasks import DesktopTask

        task = DesktopTask.create(url="https://example.test/video")
        task.mark_failed("network error")

        self.assertEqual(task.status, "failed")
        self.assertEqual(task.error, "network error")


if __name__ == "__main__":
    unittest.main()
