import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path
from threading import Event

from tests.desktop.temp_utils import workspace_tempdir


class DesktopAppTests(unittest.TestCase):
    def test_desktop_api_returns_config(self):
        with workspace_tempdir() as tmp:
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

    def test_desktop_api_returns_version(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore

            api = DesktopApi(config_store=DesktopConfigStore(
                appdata_dir=Path(tmp) / "AppData",
                user_profile=Path(tmp) / "User",
            ))

            info = api.get_app_info()

            self.assertIn("version", info)
            self.assertTrue(info["version"])

    def test_desktop_api_returns_environment_report(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore

            api = DesktopApi(config_store=DesktopConfigStore(
                appdata_dir=Path(tmp) / "AppData",
                user_profile=Path(tmp) / "User",
            ))

            report = api.get_environment()

            self.assertIn("checks", report)
            self.assertIn("missing_required", report)
            self.assertTrue(any(check["name"] == "yt-dlp" for check in report["checks"]))

    def test_resource_path_uses_pyinstaller_bundle_root(self):
        from desktop.app import _resource_path

        with patch("sys._MEIPASS", "C:/bundle/root", create=True):
            path = _resource_path("desktop/ui/index.html")

        self.assertEqual(Path("C:/bundle/root/desktop/ui/index.html"), path)

    def test_set_download_dir_rejects_blank_path(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore

            api = DesktopApi(config_store=DesktopConfigStore(
                appdata_dir=Path(tmp) / "AppData",
                user_profile=Path(tmp) / "User",
            ))
            before = api.get_config()["download_dir"]

            result = api.set_download_dir("  ")

            self.assertFalse(result["ok"])
            self.assertEqual(before, api.get_config()["download_dir"])

    def test_desktop_ui_contains_required_sections(self):
        ui = Path("desktop/ui/index.html").read_text(encoding="utf-8")

        self.assertIn("desktop-tabs", ui)
        self.assertIn('data-page="download-page"', ui)
        self.assertIn('data-page="settings-panel"', ui)
        self.assertIn('data-page="logs-panel"', ui)
        self.assertIn("download-page", ui)
        self.assertIn("download-url", ui)
        self.assertIn("settings-panel", ui)
        self.assertIn("logs-panel", ui)
        self.assertIn("app-version", ui)

    def test_desktop_ui_uses_clear_labels_and_deemphasizes_ffmpeg(self):
        ui = Path("desktop/ui/index.html").read_text(encoding="utf-8")

        self.assertIn("输入视频链接", ui)
        self.assertIn("下载", ui)
        self.assertIn("高级设置", ui)
        self.assertIn("<details", ui)
        self.assertNotIn("涓", ui)
        self.assertNotIn("璁", ui)

    def test_desktop_ui_refreshes_task_list(self):
        script = Path("desktop/ui/app.js").read_text(encoding="utf-8")

        self.assertIn("async function refreshTasks()", script)
        self.assertIn("renderTasks", script)
        self.assertIn("get_tasks", script)
        self.assertIn("setInterval(refreshTasks", script)

    def test_desktop_ui_has_open_download_dir_button(self):
        ui = Path("desktop/ui/index.html").read_text(encoding="utf-8")
        script = Path("desktop/ui/app.js").read_text(encoding="utf-8")

        self.assertIn("open-download-dir-button", ui)
        self.assertIn("open_download_dir", script)

    def test_desktop_download_page_has_cookie_shortcuts(self):
        ui = Path("desktop/ui/index.html").read_text(encoding="utf-8")

        self.assertIn("download-cookie-panel", ui)
        self.assertIn("download-browser-cookie-source", ui)
        self.assertIn("download-import-browser-cookie-button", ui)
        self.assertIn("download-save-cookie-button", ui)
        self.assertIn("download-delete-cookie-button", ui)

    def test_desktop_settings_inputs_are_collapsible(self):
        ui = Path("desktop/ui/index.html").read_text(encoding="utf-8")
        style = Path("desktop/ui/style.css").read_text(encoding="utf-8")

        self.assertIn("settings-group", ui)
        self.assertIn("<summary>保存位置</summary>", ui)
        self.assertIn("<summary>手动 Cookie</summary>", ui)
        self.assertIn("<summary>浏览器 Cookie 来源</summary>", ui)
        self.assertIn("settings-scroll", ui)
        self.assertIn(".settings-scroll", style)

    def test_desktop_ui_can_show_environment_report(self):
        ui = Path("desktop/ui/index.html").read_text(encoding="utf-8")
        script = Path("desktop/ui/app.js").read_text(encoding="utf-8")

        self.assertIn("detect-environment-button", ui)
        self.assertIn("get_environment", script)
        self.assertIn("formatEnvironmentReport", script)

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
            wait_for(lambda: any("下载任务已取消" in line for line in api.get_logs()["lines"]))

            self.assertTrue(cancel_result["ok"])
            self.assertEqual("canceled", api.get_tasks()[0]["status"])
            self.assertEqual("", api.get_tasks()[0]["file_path"])
            self.assertTrue(downloader.cleaned)
            self.assertTrue(any("已清理临时文件：2" in line for line in api.get_logs()["lines"]))

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
            wait_for(lambda: any("下载任务失败" in line for line in api.get_logs()["lines"]))
            logs = api.get_logs()["lines"]

            self.assertTrue(any("下载任务失败" in line for line in logs))
            self.assertFalse(any("下载任务已完成" in line for line in logs))

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

            api = DesktopApi(config_store=DesktopConfigStore(
                appdata_dir=Path(tmp) / "AppData",
                user_profile=Path(tmp) / "User",
            ))
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

            api = DesktopApi(config_store=DesktopConfigStore(
                appdata_dir=Path(tmp) / "AppData",
                user_profile=Path(tmp) / "User",
            ))
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

            self.assertTrue(any("下载任务已创建" in line for line in logs["lines"]))

    def test_desktop_api_ignores_log_write_failures(self):
        with workspace_tempdir() as tmp:
            from desktop.app import DesktopApi
            from desktop.core.config import DesktopConfigStore

            api = DesktopApi(config_store=DesktopConfigStore(
                appdata_dir=Path(tmp) / "AppData",
                user_profile=Path(tmp) / "User",
            ))
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

            api = DesktopApi(config_store=DesktopConfigStore(
                appdata_dir=Path(tmp) / "AppData",
                user_profile=Path(tmp) / "User",
            ))

            result = api.import_browser_cookie("edge")

            self.assertTrue(result["ok"])
            self.assertEqual("edge", api.get_config()["browser_cookie_source"])

    def test_desktop_ui_has_delete_cookie_button(self):
        ui = Path("desktop/ui/index.html").read_text(encoding="utf-8")
        script = Path("desktop/ui/app.js").read_text(encoding="utf-8")

        self.assertIn("delete-cookie-button", ui)
        self.assertIn("delete_cookie", script)

    def test_desktop_ui_has_browser_cookie_import(self):
        ui = Path("desktop/ui/index.html").read_text(encoding="utf-8")
        script = Path("desktop/ui/app.js").read_text(encoding="utf-8")

        self.assertIn("browser-cookie-source", ui)
        self.assertIn("import_browser_cookie", script)

    def test_desktop_ui_can_cancel_task(self):
        script = Path("desktop/ui/app.js").read_text(encoding="utf-8")

        self.assertIn("cancel_task", script)
        self.assertIn("cancel-task-button", script)

    def test_desktop_ui_can_open_completed_task_location(self):
        script = Path("desktop/ui/app.js").read_text(encoding="utf-8")

        self.assertIn("open_task_location", script)
        self.assertIn("open-task-location-button", script)

    def test_desktop_ui_can_clear_finished_tasks(self):
        ui = Path("desktop/ui/index.html").read_text(encoding="utf-8")
        script = Path("desktop/ui/app.js").read_text(encoding="utf-8")

        self.assertIn("clear-finished-tasks-button", ui)
        self.assertIn("clear_finished_tasks", script)

    def test_desktop_ui_localizes_task_status(self):
        script = Path("desktop/ui/app.js").read_text(encoding="utf-8")

        self.assertIn("formatTaskStatus", script)
        self.assertIn("下载中", script)
        self.assertIn("已完成", script)
        self.assertIn("已取消", script)

    def test_desktop_ui_uses_fixed_dashboard_layout_without_page_scroll(self):
        style = Path("desktop/ui/style.css").read_text(encoding="utf-8")
        app = Path("desktop/app.py").read_text(encoding="utf-8")

        self.assertIn("overflow: hidden", style)
        self.assertIn("height: 100vh", style)
        self.assertIn("grid-template-rows", style)
        self.assertIn(".desktop-tabs", style)
        self.assertIn(".tab-button", style)
        self.assertIn(".page", style)
        self.assertIn(".page.is-active", style)
        self.assertIn(".download-panel", style)
        self.assertIn(".task-list", style)
        self.assertIn("min-height: 0", style)
        self.assertIn("overflow: auto", style)
        self.assertIn("height=700", app)

    def test_desktop_ui_switches_between_pages(self):
        script = Path("desktop/ui/app.js").read_text(encoding="utf-8")

        self.assertIn("function switchPage", script)
        self.assertIn("tab-button", script)
        self.assertIn("is-active", script)
        self.assertIn("aria-selected", script)


if __name__ == "__main__":
    unittest.main()


def wait_for(predicate, *, attempts=50):
    for _ in range(attempts):
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition was not met")
