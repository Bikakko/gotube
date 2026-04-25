import os
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from tests.desktop.temp_utils import workspace_tempdir


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class DesktopAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from desktop.app import create_application

        cls.qt_app = create_application()

    def test_desktop_api_returns_config(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore

            root = Path(tmp)
            api = DesktopApi(
                config_store=DesktopConfigStore(
                    appdata_dir=root / "AppData",
                    user_profile=root / "User",
                )
            )

            config = api.get_config()

            self.assertIn("download_dir", config)
            self.assertTrue(config["download_dir"].endswith("Downloads\\GoTube"))

    def test_desktop_api_returns_version(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore

            api = DesktopApi(
                config_store=DesktopConfigStore(
                    appdata_dir=Path(tmp) / "AppData",
                    user_profile=Path(tmp) / "User",
                )
            )

            info = api.get_app_info()

            self.assertIn("version", info)
            self.assertTrue(info["version"])

    def test_desktop_api_returns_environment_report(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore

            api = DesktopApi(
                config_store=DesktopConfigStore(
                    appdata_dir=Path(tmp) / "AppData",
                    user_profile=Path(tmp) / "User",
                )
            )

            report = api.get_environment()

            self.assertIn("checks", report)
            self.assertIn("missing_required", report)
            self.assertTrue(any(check["name"] == "yt-dlp" for check in report["checks"]))

    def test_resource_path_uses_pyinstaller_bundle_root(self):
        from desktop.app import _resource_path

        with patch("sys._MEIPASS", "C:/bundle/root", create=True):
            path = _resource_path("VERSION")

        self.assertEqual(Path("C:/bundle/root/VERSION"), path)

    def test_create_application_reuses_qapplication_instance(self):
        from desktop.app import create_application

        app1 = create_application()
        app2 = create_application()

        self.assertIs(app1, app2)

    def test_desktop_main_window_has_native_tabs(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi, DesktopMainWindow
            from desktop.core.config import DesktopConfigStore

            api = DesktopApi(
                config_store=DesktopConfigStore(
                    appdata_dir=Path(tmp) / "AppData",
                    user_profile=Path(tmp) / "User",
                )
            )
            window = DesktopMainWindow(api)

            self.assertEqual("GoTube Desktop", window.windowTitle())
            self.assertEqual(3, window.tabs.count())
            self.assertEqual("下载", window.tabs.tabText(0))
            self.assertEqual("设置", window.tabs.tabText(1))
            self.assertEqual("日志", window.tabs.tabText(2))

    def test_desktop_main_window_uses_scrollable_settings_area(self):
        with workspace_tempdir() as tmp:
            from PySide6.QtWidgets import QScrollArea

            from desktop.app import DesktopApi, DesktopMainWindow
            from desktop.core.config import DesktopConfigStore

            api = DesktopApi(
                config_store=DesktopConfigStore(
                    appdata_dir=Path(tmp) / "AppData",
                    user_profile=Path(tmp) / "User",
                )
            )
            window = DesktopMainWindow(api)

            self.assertIsInstance(window.settings_scroll, QScrollArea)
            self.assertTrue(window.settings_scroll.widgetResizable())

    def test_desktop_main_window_has_cookie_shortcuts_on_download_page(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi, DesktopMainWindow
            from desktop.core.config import DesktopConfigStore

            api = DesktopApi(
                config_store=DesktopConfigStore(
                    appdata_dir=Path(tmp) / "AppData",
                    user_profile=Path(tmp) / "User",
                )
            )
            window = DesktopMainWindow(api)

            self.assertEqual("Cookie 快捷操作", window.download_cookie_group.title())
            self.assertEqual("保存 Cookie", window.download_save_cookie_button.text())
            self.assertEqual("删除 Cookie", window.download_delete_cookie_button.text())
            self.assertEqual("浏览器 Cookie", window.download_import_cookie_button.text())

    def test_desktop_main_window_applies_saved_window_size(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi, DesktopMainWindow
            from desktop.core.config import DesktopConfigStore

            store = DesktopConfigStore(
                appdata_dir=Path(tmp) / "AppData",
                user_profile=Path(tmp) / "User",
            )
            config = store.load()
            config.last_window_size = (1320, 840)
            store.save(config)
            api = DesktopApi(config_store=store)

            window = DesktopMainWindow(api)

            self.assertEqual(1320, window.width())
            self.assertEqual(840, window.height())

    def test_set_download_dir_rejects_blank_path(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore

            api = DesktopApi(
                config_store=DesktopConfigStore(
                    appdata_dir=Path(tmp) / "AppData",
                    user_profile=Path(tmp) / "User",
                )
            )
            before = api.get_config()["download_dir"]

            result = api.set_download_dir("  ")

            self.assertFalse(result["ok"])
            self.assertEqual(before, api.get_config()["download_dir"])

    def test_create_download_registers_task_before_background_finish(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore
            from desktop.core.tasks import DesktopTask

            release = Event()

            class BlockingDownloader:
                def download(self, url, on_progress=None):
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

    def test_download_progress_updates_registered_task_before_finish(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore
            from desktop.core.tasks import DesktopTask

            release = Event()

            class ProgressDownloader:
                def download(self, url, on_progress=None):
                    task = DesktopTask.create(url=url)
                    task.mark_running()
                    task.update_progress(percent=42.0, speed="1 MiB/s", eta="10s")
                    if on_progress:
                        on_progress(task)
                    release.wait(timeout=2)
                    task.mark_completed(file_path="video.mp4")
                    return task

            api = DesktopApi(
                config_store=DesktopConfigStore(
                    appdata_dir=Path(tmp) / "AppData",
                    user_profile=Path(tmp) / "User",
                ),
                downloader_factory=lambda config: ProgressDownloader(),
            )

            api.create_download("https://example.com/video")
            wait_for(lambda: api.get_tasks()[0]["percent"] == 42.0)
            release.set()

            task = api.get_tasks()[0]
            self.assertEqual("running", task["status"])
            self.assertEqual("1 MiB/s", task["speed"])

    def test_cancel_task_prevents_late_completion_from_overwriting_state(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore
            from desktop.core.tasks import DesktopTask

            release = Event()

            class SlowDownloader:
                def __init__(self):
                    self.cleaned = False

                def download(self, url, on_progress=None, should_cancel=None):
                    task = DesktopTask.create(url=url)
                    task.mark_running()
                    if on_progress:
                        on_progress(task)
                    if should_cancel and should_cancel():
                        task.mark_canceled()
                        return task
                    release.wait(timeout=2)
                    if should_cancel and should_cancel():
                        task.mark_canceled()
                        return task
                    task.mark_completed(file_path="video.mp4")
                    return task

                def cleanup_partial_downloads(self):
                    self.cleaned = True
                    return 2

            downloader = SlowDownloader()
            api = DesktopApi(
                config_store=DesktopConfigStore(
                    appdata_dir=Path(tmp) / "AppData",
                    user_profile=Path(tmp) / "User",
                ),
                downloader_factory=lambda config: downloader,
            )

            created = api.create_download("https://example.com/video")
            wait_for(lambda: api.get_tasks()[0]["status"] == "running")
            cancel_result = api.cancel_task(created["task_id"])
            release.set()
            wait_for(lambda: any("已取消" in line for line in api.get_logs()["lines"]))

            self.assertTrue(cancel_result["ok"])
            self.assertEqual("canceled", api.get_tasks()[0]["status"])
            self.assertEqual("", api.get_tasks()[0]["file_path"])
            self.assertTrue(downloader.cleaned)

    def test_failed_download_is_logged_as_failed(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore
            from desktop.core.tasks import DesktopTask

            class FailingDownloader:
                def download(self, url, on_progress=None):
                    task = DesktopTask.create(url=url)
                    task.mark_failed("network error")
                    return task

            api = DesktopApi(
                config_store=DesktopConfigStore(
                    appdata_dir=Path(tmp) / "AppData",
                    user_profile=Path(tmp) / "User",
                ),
                downloader_factory=lambda config: FailingDownloader(),
            )

            api.create_download("https://example.com/video")
            wait_for(lambda: api.get_tasks()[0]["status"] == "failed")
            wait_for(lambda: any("失败" in line for line in api.get_logs()["lines"]))
            logs = api.get_logs()["lines"]

            self.assertTrue(any("失败" in line for line in logs))
            self.assertFalse(any("完成" in line for line in logs))

    def test_open_download_dir_creates_directory_and_uses_opener(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore

            opened = []
            api = DesktopApi(
                config_store=DesktopConfigStore(
                    appdata_dir=Path(tmp) / "AppData",
                    user_profile=Path(tmp) / "User",
                ),
                folder_opener=lambda path: opened.append(path),
            )

            result = api.open_download_dir()

            self.assertTrue(result["ok"])
            self.assertTrue(Path(result["path"]).exists())
            self.assertEqual([Path(result["path"])], opened)

    def test_open_task_location_uses_completed_file_parent(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore
            from desktop.core.tasks import DesktopTask

            opened = []
            api = DesktopApi(
                config_store=DesktopConfigStore(
                    appdata_dir=Path(tmp) / "AppData",
                    user_profile=Path(tmp) / "User",
                ),
                folder_opener=lambda path: opened.append(path),
            )
            task = DesktopTask.create(url="https://example.com/video")
            file_path = Path(tmp) / "downloads" / "video.mp4"
            task.mark_completed(file_path=str(file_path))
            api.tasks.append(task)

            result = api.open_task_location(task.id)

            self.assertTrue(result["ok"])
            self.assertEqual([file_path.parent], opened)

    def test_open_task_location_rejects_unfinished_task(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore
            from desktop.core.tasks import DesktopTask

            api = DesktopApi(
                config_store=DesktopConfigStore(
                    appdata_dir=Path(tmp) / "AppData",
                    user_profile=Path(tmp) / "User",
                )
            )
            task = DesktopTask.create(url="https://example.com/video")
            task.mark_running()
            api.tasks.append(task)

            result = api.open_task_location(task.id)

            self.assertFalse(result["ok"])

    def test_clear_finished_tasks_keeps_running_tasks(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore
            from desktop.core.tasks import DesktopTask

            api = DesktopApi(
                config_store=DesktopConfigStore(
                    appdata_dir=Path(tmp) / "AppData",
                    user_profile=Path(tmp) / "User",
                )
            )
            running = DesktopTask.create(url="https://example.com/running")
            running.mark_running()
            completed = DesktopTask.create(url="https://example.com/done")
            completed.mark_completed(file_path=str(Path(tmp) / "done.mp4"))
            failed = DesktopTask.create(url="https://example.com/failed")
            failed.mark_failed("failed")
            api.tasks.extend([running, completed, failed])

            result = api.clear_finished_tasks()

            self.assertTrue(result["ok"])
            self.assertEqual(2, result["removed"])
            self.assertEqual([running.id], [task["id"] for task in api.get_tasks()])

    def test_desktop_api_reads_logs_from_store(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore

            store = DesktopConfigStore(
                appdata_dir=Path(tmp) / "AppData",
                user_profile=Path(tmp) / "User",
            )
            api = DesktopApi(config_store=store)

            api.create_download("https://example.com/video")
            reloaded_api = DesktopApi(config_store=store)
            logs = reloaded_api.get_logs()

            self.assertTrue(any("任务已创建" in line for line in logs["lines"]))

    def test_desktop_api_ignores_log_write_failures(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore

            api = DesktopApi(
                config_store=DesktopConfigStore(
                    appdata_dir=Path(tmp) / "AppData",
                    user_profile=Path(tmp) / "User",
                )
            )
            api.log_store.path.parent.mkdir(parents=True, exist_ok=True)
            api.log_store.path.parent.rmdir()

            api._append_log("should not crash")

    def test_delete_cookie_clears_saved_cookie_and_config(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore

            store = DesktopConfigStore(
                appdata_dir=Path(tmp) / "AppData",
                user_profile=Path(tmp) / "User",
            )
            api = DesktopApi(config_store=store)
            content = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tsecret\n"
            save_result = api.save_cookie(content)

            self.assertTrue(save_result["ok"])
            self.assertTrue(Path(api.get_config()["cookies_file"]).exists())

            delete_result = api.delete_cookie()

            self.assertTrue(delete_result["ok"])
            self.assertEqual("", api.get_config()["cookies_file"])

    def test_import_browser_cookie_updates_config_source(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore

            api = DesktopApi(
                config_store=DesktopConfigStore(
                    appdata_dir=Path(tmp) / "AppData",
                    user_profile=Path(tmp) / "User",
                )
            )

            result = api.import_browser_cookie("edge")

            self.assertTrue(result["ok"])
            self.assertEqual("edge", api.get_config()["browser_cookie_source"])


if __name__ == "__main__":
    unittest.main()


def wait_for(predicate, *, attempts=50):
    for _ in range(attempts):
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition was not met")
