import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class AdminUsersFrontendTests(unittest.TestCase):
    def test_users_js_uses_management_shell_and_standard_copy(self):
        source = read_text("www/admin/js/users.js")

        self.assertIn("className: 'user-management-shell'", source)
        self.assertIn("className: `user-identity-card ${(user.role || 'user')}`", source)
        self.assertIn("className: 'user-search-summary user-summary-pill'", source)
        self.assertIn(r"textContent: '\u7528\u6237'", source)
        self.assertIn(r"textContent: '\u65b0\u589e\u7528\u6237'", source)
        self.assertIn(r"\u8f93\u5165\u8d26\u53f7\u3001\u6635\u79f0\u6216\u7528\u6237 ID", source)
        self.assertIn(r"textContent: '\u5168\u90e8\u72b6\u6001'", source)
        self.assertIn(r"textContent: '\u5168\u90e8\u89d2\u8272'", source)
        self.assertIn("state.userStatusFilter", source)
        self.assertIn("state.userRoleFilter", source)

    def test_users_css_styles_management_table_shell(self):
        css = read_text("www/admin/css/admin.css")

        self.assertIn(".user-management-shell {", css)
        self.assertIn(".users-table-shell {", css)
        self.assertIn(".user-identity-card {", css)
        self.assertIn(".user-note-badge {", css)
        self.assertIn(".user-summary-pill {", css)
        self.assertIn(".user-actions-compact {", css)
        self.assertIn(".user-toolbar-main {", css)
        self.assertIn(".user-filter-select {", css)

    def test_users_js_supports_account_nickname_and_id_display(self):
        source = read_text("www/admin/js/users.js")
        render_source = read_text("www/admin/js/render.js")

        self.assertIn(r"placeholder: '\u8f93\u5165\u8d26\u53f7\u3001\u6635\u79f0\u6216\u7528\u6237 ID'", source)
        self.assertIn("id: 'edit-display-name'", source)
        self.assertIn("display_name: displayName", source)
        self.assertIn(r"textContent: `\u8d26\u53f7\uff1a${user.username}", source)
        self.assertIn("function formatUserIdentityText(user)", render_source)
        self.assertIn("className: 'users-col-identity'", source)
        self.assertIn(r"textContent: '\u7528\u6237'", source)


if __name__ == "__main__":
    unittest.main()
