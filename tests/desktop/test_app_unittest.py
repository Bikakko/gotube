import tempfile
import unittest
from pathlib import Path
from threading import Event


class DesktopAppTests(unittest.TestCase):
    def test_desktop_api_returns_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore

            root = Path(tmp)
            api = DesktopApi(config_store=DesktopConfigStore(
                appdata_dir=root / "AppData",
                user_profile=root / "User",
            ))

            config = api.get_config()

            self.assertIn("download_dir", config)
            self.assertTrue(config["download_dir"].endswith("Downloads\\GoTube"))

    def test_desktop_ui_contains_required_sections(self):
        ui = Path("desktop/ui/index.html").read_text(encoding="utf-8")

        self.assertIn("download-url", ui)
        self.assertIn("settings-panel", ui)
        self.assertIn("logs-panel", ui)

    def test_desktop_ui_uses_clear_labels_and_deemphasizes_ffmpeg(self):
        ui = Path("desktop/ui/index.html").read_text(encoding="utf-8")

        self.assertIn("输入视频链接", ui)
        self.assertIn("下载", ui)
        self.assertIn("高级设置", ui)
        self.assertIn("<details", ui)
        self.assertNotIn("涓", ui)
        self.assertNotIn("璁", ui)

    def test_create_download_registers_task_before_background_finish(self):
        with tempfile.TemporaryDirectory() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore
            from desktop.core.tasks import DesktopTask

            release = Event()

            class BlockingDownloader:
                def download(self, url):
                    release.wait(timeout=2)
                    task = DesktopTask.create(url=url)
                    task.mark_completed(file_path="video.mp4")
                    return task

            api = DesktopApi(
                config_store=DesktopConfigStore(
                    appdata_dir=Path(tmp) / "AppData",
                    user_profile=Path(tmp) / "User",
                ),
                downloader_factory=lambda config: BlockingDownloader(),
            )

            api.create_download("https://example.com/video")
            tasks = api.get_tasks()
            release.set()

            self.assertEqual(1, len(tasks))
            self.assertEqual("https://example.com/video", tasks[0]["url"])
            self.assertIn(tasks[0]["status"], {"pending", "running"})


if __name__ == "__main__":
    unittest.main()
