import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class AdminUsersFrontendTests(unittest.TestCase):
    def test_users_js_uses_management_shell_and_standard_copy(self):
        source = read_text("www/admin/js/users.js")

        self.assertIn("className: 'user-management-shell'", source)
        self.assertIn("className: 'user-name-cell'", source)
        self.assertIn("className: 'user-search-summary user-summary-pill'", source)
        self.assertIn("textContent: '用户'", source)
        self.assertIn("textContent: '新增用户'", source)
        self.assertIn("'输入用户名或用户 ID'", source)
        self.assertIn("textContent: '全部状态'", source)
        self.assertIn("textContent: '全部角色'", source)
        self.assertIn("state.userStatusFilter", source)
        self.assertIn("state.userRoleFilter", source)

    def test_users_css_styles_management_table_shell(self):
        css = read_text("www/admin/css/admin.css")

        self.assertIn(".user-management-shell {", css)
        self.assertIn(".users-table-shell {", css)
        self.assertIn(".user-name-cell {", css)
        self.assertIn(".user-summary-pill {", css)
        self.assertIn(".user-actions-compact {", css)
        self.assertIn(".user-toolbar-main {", css)
        self.assertIn(".user-filter-select {", css)


if __name__ == "__main__":
    unittest.main()
