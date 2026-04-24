import unittest
import tempfile
from pathlib import Path

from tests.desktop.temp_utils import workspace_tempdir


class DesktopLogsTests(unittest.TestCase):
    def test_log_store_appends_and_reads_recent_lines(self):
        from desktop.core.logs import DesktopLogStore

        with workspace_tempdir() as tmp:
            store = DesktopLogStore(Path(tmp) / "desktop.log", max_lines=2)
            store.append("first")
            store.append("second")
            store.append("third")

            recent = store.read_recent()
        self.assertEqual(2, len(recent))
        self.assertTrue(recent[0].endswith("second"))
        self.assertTrue(recent[1].endswith("third"))

    def test_log_store_creates_parent_directory(self):
        from desktop.core.logs import DesktopLogStore

        with workspace_tempdir() as tmp:
            log_file = Path(tmp) / "nested" / "desktop.log"
            store = DesktopLogStore(log_file)
            store.append("hello")

            self.assertTrue(log_file.exists())
            self.assertIn("hello", log_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
