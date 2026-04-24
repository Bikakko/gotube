import unittest
from pathlib import Path


class DesktopDocsTests(unittest.TestCase):
    def test_windows_desktop_doc_covers_install_run_and_package(self):
        doc = Path("docs/ops/desktop-windows.md").read_text(encoding="utf-8")

        self.assertIn("requirements-desktop.txt", doc)
        self.assertIn("python -m desktop.app", doc)
        self.assertIn("desktop/packaging/gotube-desktop.spec", doc)
        self.assertIn("scripts/desktop_check.py", doc)
        self.assertIn("scripts/desktop_build.py", doc)
        self.assertIn("Cookie", doc)
        self.assertIn("删除 Cookie", doc)
        self.assertIn("浏览器 Cookie 来源", doc)
        self.assertIn("ffmpeg", doc)
        self.assertIn("yt-dlp", doc)


if __name__ == "__main__":
    unittest.main()
