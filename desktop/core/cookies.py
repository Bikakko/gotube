"""Cookie management for GoTube Desktop."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class CookieActionResult:
    ok: bool
    message: str
    path: Path | None = None


class DesktopCookieStore:
    def __init__(self, app_dir: Path) -> None:
        self.app_dir = Path(app_dir)
        self.cookie_file = self.app_dir / "cookies.txt"

    def save_manual_cookie(self, content: str) -> CookieActionResult:
        valid, message = validate_netscape_cookie_content(content)
        if not valid:
            return CookieActionResult(ok=False, message=message)

        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.cookie_file.write_text(content, encoding="utf-8")
        return CookieActionResult(ok=True, message="Cookie 已保存", path=self.cookie_file)

    def delete_cookie_file(self) -> CookieActionResult:
        if self.cookie_file.exists():
            self.cookie_file.unlink()
        return CookieActionResult(ok=True, message="Cookie 已删除", path=self.cookie_file)

    def get_cookie_file(self) -> Path | None:
        return self.cookie_file if self.cookie_file.exists() else None

    def import_from_browser(self, browser: str) -> CookieActionResult:
        browser_name = (browser or "").strip().lower()
        if browser_name not in {"edge", "chrome", "firefox"}:
            return CookieActionResult(ok=False, message=f"暂不支持浏览器: {browser}")

        return CookieActionResult(
            ok=False,
            message="浏览器 Cookie 导入入口已就绪，后续将接入 yt-dlp 浏览器 Cookie 能力",
        )


def validate_netscape_cookie_content(content: str) -> tuple[bool, str]:
    if not content or not content.strip():
        return False, "Cookie 内容为空"

    lines = content.splitlines()
    if not lines or not lines[0].startswith("# Netscape HTTP Cookie File"):
        return False, "Cookie 文件必须是 Netscape 格式"

    data_lines = [
        line for line in lines
        if line.strip() and not line.startswith("#")
    ]
    if not data_lines:
        return False, "Cookie 文件没有有效记录"

    for line in data_lines:
        if len(line.split("\t")) < 7:
            return False, "Cookie 记录字段不足"

    return True, "Cookie 格式有效"
