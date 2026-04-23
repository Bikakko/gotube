import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class AdminSystemFrontendTests(unittest.TestCase):
    def test_system_js_uses_standard_runtime_copy(self):
        source = read_text("www/admin/js/system.js")
        render_source = read_text("www/admin/js/render.js")

        self.assertIn("运行巡检加载失败", source)
        self.assertIn("Cookie 状态加载失败", source)
        self.assertIn("加载运行巡检中", source)
        self.assertIn("加载运行日志中", source)
        self.assertIn("暂无应用日志", source)
        self.assertIn("暂无访问日志", source)
        self.assertIn("createSystemSummaryCard('版本'", source)
        self.assertNotIn("createSystemSummaryCard('Git'", source)
        self.assertIn("更新 Cookie", source)
        self.assertIn("删除当前 Cookie", render_source)
        self.assertIn("运行日志", render_source)
        self.assertIn("刷新日志", render_source)
        self.assertIn("复制日志", render_source)

    def test_cookies_js_uses_standard_status_copy(self):
        source = read_text("www/admin/js/cookies.js")

        self.assertIn("上传或更新 Cookie", source)
        self.assertIn("未配置 Cookie", source)
        self.assertIn("查看平台诊断", source)
        self.assertIn("上传新 Cookie 时，只会覆盖匹配的 Cookie 记录", source)


if __name__ == "__main__":
    unittest.main()
