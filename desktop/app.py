"""GoTube Desktop entrypoint."""

from __future__ import annotations

import inspect
import os
import sys
import threading
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QToolBox,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QScrollArea,
)

from desktop.core.config import DesktopConfig, DesktopConfigStore
from desktop.core.cookies import DesktopCookieStore
from desktop.core.downloader import DesktopDownloader
from desktop.core.environment import collect_environment_report, has_missing_required_checks
from desktop.core.logs import DesktopLogStore
from desktop.core.tasks import DesktopTask
from desktop.core.tools import detect_ffmpeg, detect_ytdlp, upgrade_ytdlp


DEFAULT_WINDOW_SIZE = (1180, 760)


class DesktopApi:
    def __init__(
        self,
        *,
        config_store: DesktopConfigStore | None = None,
        downloader_factory: Callable[[DesktopConfig], DesktopDownloader] | None = None,
        folder_opener: Callable[[Path], None] | None = None,
    ) -> None:
        self.config_store = config_store or DesktopConfigStore()
        self.config = self.config_store.load()
        self.cookie_store = DesktopCookieStore(self.config_store.config_dir)
        self.log_store = DesktopLogStore(self.config_store.config_dir / "desktop.log")
        self.downloader_factory = downloader_factory or self._create_downloader
        self.folder_opener = folder_opener or self._open_folder
        self.tasks: list[DesktopTask] = []
        self.canceled_task_ids: set[str] = set()
        self._lock = threading.Lock()

    def get_config(self) -> dict:
        return {
            "download_dir": str(self.config.download_dir),
            "cookies_file": str(self.config.cookies_file) if self.config.cookies_file else "",
            "ffmpeg_path": str(self.config.ffmpeg_path) if self.config.ffmpeg_path else "",
            "browser_cookie_source": self.config.browser_cookie_source or "",
        }

    def get_app_info(self) -> dict:
        version_file = _resource_path("VERSION")
        try:
            version = version_file.read_text(encoding="utf-8").strip()
        except OSError:
            version = "unknown"
        return {"name": "GoTube Desktop", "version": version or "unknown"}

    def set_download_dir(self, path: str) -> dict:
        clean_path = path.strip()
        if not clean_path:
            return {"ok": False, "message": "保存位置不能为空", **self.get_config()}
        self.config.download_dir = Path(clean_path)
        self.config_store.save(self.config)
        return {"ok": True, "message": "保存位置已更新", **self.get_config()}

    def set_ffmpeg_path(self, path: str) -> dict:
        self.config.ffmpeg_path = Path(path) if path else None
        self.config_store.save(self.config)
        return self.get_config()

    def open_download_dir(self) -> dict:
        self.config.download_dir.mkdir(parents=True, exist_ok=True)
        self.folder_opener(self.config.download_dir)
        return {"ok": True, "path": str(self.config.download_dir)}

    def open_task_location(self, task_id: str) -> dict:
        with self._lock:
            task = next((item for item in self.tasks if item.id == task_id), None)
        if task is None:
            return {"ok": False, "message": "任务不存在"}
        if task.status != "completed" or not task.file_path:
            return {"ok": False, "message": "任务尚未完成"}

        folder = Path(task.file_path).parent
        folder.mkdir(parents=True, exist_ok=True)
        self.folder_opener(folder)
        return {"ok": True, "message": "已打开文件位置", "path": str(folder)}

    def save_cookie(self, content: str) -> dict:
        result = self.cookie_store.save_manual_cookie(content)
        if result.ok:
            self.config.cookies_file = result.path
            self.config_store.save(self.config)
        return {"ok": result.ok, "message": result.message}

    def delete_cookie(self) -> dict:
        result = self.cookie_store.delete_cookie_file()
        if result.ok:
            self.config.cookies_file = None
            self.config_store.save(self.config)
            self._append_log("Cookie 已删除")
        return {"ok": result.ok, "message": result.message}

    def import_browser_cookie(self, browser: str) -> dict:
        result = self.cookie_store.import_from_browser(browser)
        if result.ok:
            self.config.browser_cookie_source = browser.strip().lower()
            self.config_store.save(self.config)
            self._append_log(f"浏览器 Cookie 来源已设置：{self.config.browser_cookie_source}")
        return {"ok": result.ok, "message": result.message}

    def detect_tools(self) -> dict:
        ffmpeg = detect_ffmpeg(configured_path=self.config.ffmpeg_path)
        ytdlp = detect_ytdlp()
        return {
            "ffmpeg": _tool_to_dict(ffmpeg),
            "yt_dlp": _tool_to_dict(ytdlp),
        }

    def get_environment(self) -> dict:
        checks = collect_environment_report()
        return {
            "missing_required": has_missing_required_checks(checks),
            "checks": [_environment_check_to_dict(check) for check in checks],
        }

    def upgrade_ytdlp(self) -> dict:
        result = upgrade_ytdlp()
        return {
            "ok": result.ok,
            "message": result.message,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def create_download(self, url: str) -> dict:
        task = DesktopTask.create(url=url)
        with self._lock:
            self.tasks.append(task)
        self._append_log(f"下载任务已创建：{url}")

        def run() -> None:
            with self._lock:
                if task.id in self.canceled_task_ids:
                    return
                task.mark_running()
            downloader = self.downloader_factory(self.config)

            def on_progress(progress_task: DesktopTask) -> None:
                with self._lock:
                    if task.id in self.canceled_task_ids:
                        return
                    _copy_task_state(target=task, source=progress_task)

            try:
                finished_task = _download_with_supported_args(
                    downloader,
                    url,
                    on_progress=on_progress,
                    should_cancel=lambda: task.id in self.canceled_task_ids,
                )
                with self._lock:
                    if task.id in self.canceled_task_ids:
                        task.mark_canceled()
                        self._append_log(f"下载任务已取消：{url}")
                        removed = _cleanup_partial_downloads(downloader)
                        if removed:
                            self._append_log(f"已清理临时文件：{removed}")
                        return
                    _copy_task_state(target=task, source=finished_task)
                if task.status == "completed":
                    self._append_log(f"下载任务已完成：{url}")
                elif task.status == "canceled":
                    self._append_log(f"下载任务已取消：{url}")
                else:
                    self._append_log(f"下载任务失败：{url}，{task.error}")
            except Exception as exc:
                task.mark_failed(str(exc))
                self._append_log(f"下载任务失败：{url}，{exc}")

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return {"ok": True, "message": "下载任务已开始", "task_id": task.id}

    def cancel_task(self, task_id: str) -> dict:
        with self._lock:
            for task in self.tasks:
                if task.id == task_id:
                    if task.status in {"completed", "failed", "canceled"}:
                        return {"ok": False, "message": "任务已经结束"}
                    self.canceled_task_ids.add(task_id)
                    task.mark_canceled()
                    self._append_log(f"下载任务已取消：{task.url}")
                    return {"ok": True, "message": "任务已取消"}
        return {"ok": False, "message": "任务不存在"}

    def clear_finished_tasks(self) -> dict:
        finished_statuses = {"completed", "failed", "canceled"}
        with self._lock:
            before = len(self.tasks)
            self.tasks = [task for task in self.tasks if task.status not in finished_statuses]
            removed = before - len(self.tasks)
        if removed:
            self._append_log(f"已清理任务记录：{removed}")
        return {"ok": True, "message": f"已清理 {removed} 个任务", "removed": removed}

    def get_tasks(self) -> list[dict]:
        with self._lock:
            tasks = list(self.tasks)
        return [
            {
                "id": task.id,
                "url": task.url,
                "status": task.status,
                "percent": task.percent,
                "speed": task.speed,
                "eta": task.eta,
                "file_path": task.file_path,
                "error": task.error,
            }
            for task in tasks
        ]

    def get_logs(self) -> dict:
        return {"lines": self.log_store.read_recent()}

    def update_window_size(self, width: int, height: int) -> None:
        self.config.last_window_size = (width, height)
        self.config_store.save(self.config)

    def _create_downloader(self, config: DesktopConfig) -> DesktopDownloader:
        return DesktopDownloader(
            download_dir=config.download_dir,
            cookies_file=config.cookies_file,
            browser_cookie_source=config.browser_cookie_source,
            ffmpeg_path=config.ffmpeg_path,
        )

    def _open_folder(self, path: Path) -> None:
        os.startfile(path)  # type: ignore[attr-defined]

    def _append_log(self, line: str) -> None:
        try:
            self.log_store.append(line)
        except OSError:
            pass


class DesktopMainWindow(QMainWindow):
    def __init__(self, api: DesktopApi) -> None:
        super().__init__()
        self.api = api
        self.setWindowTitle("GoTube Desktop")
        self.setMinimumSize(1040, 680)
        self.resize(*self.api.config.last_window_size or DEFAULT_WINDOW_SIZE)

        self.status_label = QLabel()
        self.version_label = QLabel()
        self.tools_label = QLabel()
        self.env_label = QLabel()
        self.url_input = QLineEdit()
        self.task_list = QListWidget()
        self.cookie_input = QTextEdit()
        self.browser_cookie_source = QComboBox()
        self.download_cookie_input = QTextEdit()
        self.download_browser_cookie_source = QComboBox()
        self.download_dir_input = QLineEdit()
        self.ffmpeg_path_input = QLineEdit()
        self.logs_view = QPlainTextEdit()
        self.logs_view.setReadOnly(True)
        self.tabs = QTabWidget()
        self.settings_scroll = QScrollArea()

        self.download_cookie_group = QGroupBox("Cookie 快捷操作")
        self.download_save_cookie_button = QPushButton("保存 Cookie")
        self.download_delete_cookie_button = QPushButton("删除 Cookie")
        self.download_import_cookie_button = QPushButton("浏览器 Cookie")

        self._build_ui()
        self._connect_signals()
        self.refresh_all()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1000)
        self.refresh_timer.timeout.connect(self.refresh_tasks)
        self.refresh_timer.timeout.connect(self.refresh_logs)
        self.refresh_timer.start()

    def _build_ui(self) -> None:
        container = QWidget()
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        title = QLabel("GoTube Desktop")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.version_label)
        root_layout.addLayout(header_layout)

        self.tabs.addTab(self._build_download_page(), "下载")
        self.tabs.addTab(self._build_settings_page(), "设置")
        self.tabs.addTab(self._build_logs_page(), "日志")
        root_layout.addWidget(self.tabs)
        root_layout.addWidget(self.status_label)

        self.setCentralWidget(container)

        refresh_action = QAction("立即刷新", self)
        refresh_action.triggered.connect(self.refresh_all)
        self.addAction(refresh_action)

    def _build_download_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        url_row = QHBoxLayout()
        self.url_input.setPlaceholderText("输入视频链接")
        self.url_input.setClearButtonEnabled(True)
        self.url_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        download_button = QPushButton("开始下载")
        open_dir_button = QPushButton("打开下载目录")
        clear_button = QPushButton("清理已结束任务")
        self.cancel_task_button = QPushButton("取消所选任务")
        self.open_task_location_button = QPushButton("打开文件位置")
        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(download_button)
        url_row.addWidget(open_dir_button)
        url_row.addWidget(clear_button)
        layout.addLayout(url_row)

        task_actions = QHBoxLayout()
        task_actions.addWidget(self.cancel_task_button)
        task_actions.addWidget(self.open_task_location_button)
        task_actions.addStretch(1)
        layout.addLayout(task_actions)

        cookie_layout = QVBoxLayout(self.download_cookie_group)
        self.download_cookie_input.setPlaceholderText("可直接粘贴 Netscape 格式 Cookie")
        self.download_cookie_input.setFixedHeight(110)
        self.download_browser_cookie_source.addItems(["edge", "chrome", "firefox"])
        cookie_buttons = QHBoxLayout()
        cookie_buttons.addWidget(self.download_browser_cookie_source)
        cookie_buttons.addWidget(self.download_import_cookie_button)
        cookie_buttons.addWidget(self.download_save_cookie_button)
        cookie_buttons.addWidget(self.download_delete_cookie_button)
        cookie_layout.addWidget(self.download_cookie_input)
        cookie_layout.addLayout(cookie_buttons)
        layout.addWidget(self.download_cookie_group)

        self.task_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.task_list, 1)

        download_button.clicked.connect(self.handle_create_download)
        open_dir_button.clicked.connect(self.handle_open_download_dir)
        clear_button.clicked.connect(self.handle_clear_finished_tasks)

        return page

    def _build_settings_page(self) -> QWidget:
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        toolbox = QToolBox()
        toolbox.addItem(self._build_download_settings_panel(), "保存位置")
        toolbox.addItem(self._build_manual_cookie_panel(), "手动 Cookie")
        toolbox.addItem(self._build_browser_cookie_panel(), "浏览器 Cookie")
        toolbox.addItem(self._build_advanced_panel(), "高级设置")
        content_layout.addWidget(toolbox)
        content_layout.addStretch(1)

        self.settings_scroll.setWidget(content)
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        return self.settings_scroll

    def _build_download_settings_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        form = QFormLayout()
        self.download_dir_input.setReadOnly(True)
        form.addRow("保存目录", self.download_dir_input)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        choose = QPushButton("选择目录")
        open_dir = QPushButton("打开目录")
        choose.clicked.connect(self.handle_choose_download_dir)
        open_dir.clicked.connect(self.handle_open_download_dir)
        buttons.addWidget(choose)
        buttons.addWidget(open_dir)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        return panel

    def _build_manual_cookie_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.cookie_input.setPlaceholderText("可在这里保存手动 Cookie")
        self.cookie_input.setMinimumHeight(180)
        layout.addWidget(self.cookie_input)

        buttons = QHBoxLayout()
        save = QPushButton("保存 Cookie")
        delete = QPushButton("删除 Cookie")
        save.clicked.connect(self.handle_save_cookie)
        delete.clicked.connect(self.handle_delete_cookie)
        buttons.addWidget(save)
        buttons.addWidget(delete)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        return panel

    def _build_browser_cookie_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        row = QHBoxLayout()
        self.browser_cookie_source.addItems(["edge", "chrome", "firefox"])
        import_button = QPushButton("导入浏览器 Cookie")
        import_button.clicked.connect(self.handle_import_browser_cookie)
        row.addWidget(QLabel("浏览器来源"))
        row.addWidget(self.browser_cookie_source)
        row.addWidget(import_button)
        row.addStretch(1)
        layout.addLayout(row)
        return panel

    def _build_advanced_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        form = QFormLayout()
        self.ffmpeg_path_input.setReadOnly(True)
        form.addRow("ffmpeg 路径", self.ffmpeg_path_input)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        choose_ffmpeg = QPushButton("指定 ffmpeg")
        detect_tools_button = QPushButton("检测环境")
        upgrade_button = QPushButton("升级 yt-dlp")
        choose_ffmpeg.clicked.connect(self.handle_choose_ffmpeg_path)
        detect_tools_button.clicked.connect(self.refresh_environment)
        upgrade_button.clicked.connect(self.handle_upgrade_ytdlp)
        buttons.addWidget(choose_ffmpeg)
        buttons.addWidget(detect_tools_button)
        buttons.addWidget(upgrade_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addWidget(self.tools_label)
        layout.addWidget(self.env_label)
        return panel

    def _build_logs_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        controls = QHBoxLayout()
        refresh = QPushButton("刷新日志")
        refresh.clicked.connect(self.refresh_logs)
        controls.addWidget(refresh)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.logs_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.logs_view, 1)
        return page

    def _connect_signals(self) -> None:
        self.url_input.returnPressed.connect(self.handle_create_download)
        self.cancel_task_button.clicked.connect(self.handle_cancel_selected_task)
        self.open_task_location_button.clicked.connect(self.handle_open_selected_task_location)
        self.download_save_cookie_button.clicked.connect(self.handle_download_page_save_cookie)
        self.download_delete_cookie_button.clicked.connect(self.handle_delete_cookie)
        self.download_import_cookie_button.clicked.connect(self.handle_download_page_import_browser_cookie)

    def refresh_all(self) -> None:
        self.refresh_version()
        self.refresh_config()
        self.refresh_tasks()
        self.refresh_logs()
        self.refresh_environment()

    def refresh_version(self) -> None:
        info = self.api.get_app_info()
        self.version_label.setText(f"版本 {info['version']}")

    def refresh_config(self) -> None:
        config = self.api.get_config()
        self.download_dir_input.setText(config["download_dir"])
        self.ffmpeg_path_input.setText(config["ffmpeg_path"])
        self.browser_cookie_source.setCurrentText(config["browser_cookie_source"] or "edge")
        self.download_browser_cookie_source.setCurrentText(config["browser_cookie_source"] or "edge")

    def refresh_tasks(self) -> None:
        tasks = self.api.get_tasks()
        selected_id = self._selected_task_id()
        self.task_list.clear()
        for task in tasks:
            label = self._format_task(task)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, task["id"])
            self.task_list.addItem(item)
            if task["id"] == selected_id:
                self.task_list.setCurrentItem(item)

    def refresh_logs(self) -> None:
        lines = self.api.get_logs()["lines"]
        self.logs_view.setPlainText("\n".join(lines))
        cursor = self.logs_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.logs_view.setTextCursor(cursor)

    def refresh_environment(self) -> None:
        tools = self.api.detect_tools()
        env = self.api.get_environment()
        self.tools_label.setText(
            "工具状态  "
            f"yt-dlp: {self._tool_summary(tools['yt_dlp'])}    "
            f"ffmpeg: {self._tool_summary(tools['ffmpeg'])}"
        )
        missing = "缺少必要环境" if env["missing_required"] else "环境检查通过"
        summary = "；".join(
            f"{item['name']}：{item['message']}" for item in env["checks"] if item["message"]
        )
        self.env_label.setText(f"{missing}    {summary}")

    def handle_create_download(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            self._show_message("请输入视频链接", error=True)
            return
        result = self.api.create_download(url)
        self._show_message(result["message"], error=not result["ok"])
        if result["ok"]:
            self.url_input.clear()
            self.refresh_tasks()

    def handle_cancel_selected_task(self) -> None:
        task_id = self._selected_task_id()
        if not task_id:
            self._show_message("请先选择任务", error=True)
            return
        result = self.api.cancel_task(task_id)
        self._show_message(result["message"], error=not result["ok"])
        self.refresh_tasks()

    def handle_open_selected_task_location(self) -> None:
        task_id = self._selected_task_id()
        if not task_id:
            self._show_message("请先选择任务", error=True)
            return
        result = self.api.open_task_location(task_id)
        self._show_message(result["message"], error=not result["ok"])

    def handle_open_download_dir(self) -> None:
        result = self.api.open_download_dir()
        self._show_message("已打开下载目录", error=not result["ok"])

    def handle_clear_finished_tasks(self) -> None:
        result = self.api.clear_finished_tasks()
        self._show_message(result["message"], error=not result["ok"])
        self.refresh_tasks()

    def handle_save_cookie(self) -> None:
        result = self.api.save_cookie(self.cookie_input.toPlainText())
        self._show_message(result["message"], error=not result["ok"])
        self.refresh_config()

    def handle_download_page_save_cookie(self) -> None:
        result = self.api.save_cookie(self.download_cookie_input.toPlainText())
        self._show_message(result["message"], error=not result["ok"])
        if result["ok"]:
            self.cookie_input.setPlainText(self.download_cookie_input.toPlainText())
        self.refresh_config()

    def handle_delete_cookie(self) -> None:
        result = self.api.delete_cookie()
        self._show_message(result["message"], error=not result["ok"])
        if result["ok"]:
            self.cookie_input.clear()
            self.download_cookie_input.clear()
        self.refresh_config()

    def handle_import_browser_cookie(self) -> None:
        browser = self.browser_cookie_source.currentText()
        result = self.api.import_browser_cookie(browser)
        self._show_message(result["message"], error=not result["ok"])
        if result["ok"]:
            self.download_browser_cookie_source.setCurrentText(browser)
        self.refresh_config()

    def handle_download_page_import_browser_cookie(self) -> None:
        browser = self.download_browser_cookie_source.currentText()
        result = self.api.import_browser_cookie(browser)
        self._show_message(result["message"], error=not result["ok"])
        if result["ok"]:
            self.browser_cookie_source.setCurrentText(browser)
        self.refresh_config()

    def handle_choose_download_dir(self) -> None:
        current = self.api.get_config()["download_dir"]
        chosen = QFileDialog.getExistingDirectory(self, "选择保存目录", current)
        if not chosen:
            return
        result = self.api.set_download_dir(chosen)
        self._show_message(result["message"], error=not result["ok"])
        self.refresh_config()

    def handle_choose_ffmpeg_path(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(self, "选择 ffmpeg", self.ffmpeg_path_input.text(), "Executable (*.exe);;All Files (*)")
        if not chosen:
            return
        self.api.set_ffmpeg_path(chosen)
        self.refresh_config()
        self.refresh_environment()
        self._show_message("ffmpeg 路径已更新")

    def handle_upgrade_ytdlp(self) -> None:
        result = self.api.upgrade_ytdlp()
        self._show_message(result["message"], error=not result["ok"])
        self.refresh_environment()
        self.refresh_logs()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.api.update_window_size(self.width(), self.height())
        super().closeEvent(event)

    def _selected_task_id(self) -> str:
        item = self.task_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else ""

    def _show_message(self, text: str, *, error: bool = False) -> None:
        self.status_label.setText(text)
        if error:
            QMessageBox.warning(self, "GoTube Desktop", text)

    @staticmethod
    def _tool_summary(tool: dict) -> str:
        if tool["available"]:
            return tool["version"] or tool["path"] or "available"
        return tool["message"] or "unavailable"

    @staticmethod
    def _format_task(task: dict) -> str:
        status_map = {
            "pending": "排队中",
            "running": "下载中",
            "completed": "已完成",
            "failed": "失败",
            "canceled": "已取消",
        }
        status = status_map.get(task["status"], task["status"])
        progress = f"{task['percent']:.1f}%" if task["percent"] else status
        extras = "  ".join(filter(None, [task["speed"], task["eta"]]))
        suffix = f"  {extras}" if extras else ""
        return f"[{status}] {progress}{suffix}\n{task['url']}"


def _tool_to_dict(status) -> dict:
    return {
        "name": status.name,
        "available": status.available,
        "version": status.version,
        "path": str(status.path) if status.path else "",
        "source": status.source,
        "message": status.message,
    }


def _environment_check_to_dict(check) -> dict:
    return {
        "name": check.name,
        "ok": check.ok,
        "required": check.required,
        "version": check.version,
        "path": str(check.path) if check.path else "",
        "message": check.message,
    }


def _copy_task_state(*, target: DesktopTask, source: DesktopTask) -> None:
    target.status = source.status
    target.percent = source.percent
    target.speed = source.speed
    target.eta = source.eta
    target.file_path = source.file_path
    target.error = source.error
    target.updated_at = source.updated_at


def _download_with_supported_args(
    downloader,
    url: str,
    *,
    on_progress,
    should_cancel,
) -> DesktopTask:
    params = inspect.signature(downloader.download).parameters
    kwargs = {"on_progress": on_progress}
    if "should_cancel" in params:
        kwargs["should_cancel"] = should_cancel
    return downloader.download(url, **kwargs)


def _cleanup_partial_downloads(downloader) -> int:
    cleanup = getattr(downloader, "cleanup_partial_downloads", None)
    if not callable(cleanup):
        return 0
    return int(cleanup() or 0)


def _resource_path(relative_path: str) -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / relative_path
    return Path(__file__).resolve().parents[1] / relative_path


def create_application() -> QApplication:
    app = QApplication.instance()
    if app is not None:
        return app
    app = QApplication(sys.argv)
    app.setApplicationName("GoTube Desktop")
    app.setOrganizationName("GoTube")
    return app


def main() -> None:
    app = create_application()
    window = DesktopMainWindow(DesktopApi())
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
