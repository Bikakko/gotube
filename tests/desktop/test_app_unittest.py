import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
