import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class AdminThemeFrontendTests(unittest.TestCase):
    def test_admin_css_uses_moonlit_workspace_tokens(self):
        css = read_text("www/admin/css/admin.css")

        self.assertIn("--bg: #06101f;", css)
        self.assertIn("--surface: rgba(11, 20, 36, 0.78);", css)
        self.assertIn("--surface-strong: rgba(14, 25, 43, 0.92);", css)
        self.assertIn("--accent: #dfe8ff;", css)
        self.assertIn("--accent-soft: #8cb8ff;", css)
        self.assertIn("--danger: #ff6b78;", css)

    def test_admin_css_defines_glass_shell_for_main_surfaces(self):
        css = read_text("www/admin/css/admin.css")

        self.assertIn("backdrop-filter: blur(18px);", css)
        self.assertIn("box-shadow: 0 18px 60px rgba(2, 7, 18, 0.36);", css)
        self.assertIn("border: 1px solid rgba(222, 232, 255, 0.12);", css)

    def test_admin_css_polishes_topnav_and_empty_states(self):
        css = read_text("www/admin/css/admin.css")

        self.assertIn("scrollbar-width: none;", css)
        self.assertIn(".empty-state-card {", css)
        self.assertIn(".loading-card {", css)
        self.assertIn(".error-card {", css)


if __name__ == "__main__":
    unittest.main()
