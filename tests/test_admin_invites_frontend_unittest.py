import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class AdminInvitesFrontendTests(unittest.TestCase):
    def test_invites_js_defaults_to_active_view_and_has_archive_tabs(self):
        source = read_text("www/admin/js/invites.js")

        self.assertIn("state.inviteView || 'active'", source)
        self.assertIn("label: '可用邀请码'", source)
        self.assertIn("label: '归档记录'", source)
        self.assertIn("暂无可用邀请码", source)
        self.assertIn("暂无归档邀请码", source)
        self.assertIn("invite-actions-placeholder", source)

    def test_invites_css_reserves_action_column_width(self):
        css = read_text("www/admin/css/admin.css")

        self.assertIn(".invite-view-tabs {", css)
        self.assertIn(".invite-view-tab {", css)
        self.assertIn(".invite-actions-head,", css)
        self.assertIn(".invite-actions-placeholder {", css)


if __name__ == "__main__":
    unittest.main()
