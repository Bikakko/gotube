import json
import tempfile
import unittest
from pathlib import Path

from tests.desktop.temp_utils import workspace_tempdir


class DesktopConfigTests(unittest.TestCase):
    def test_load_uses_default_download_dir(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            appdata = root / "AppData"
            profile = root / "User"

            from desktop.core.config import DesktopConfigStore

            store = DesktopConfigStore(appdata_dir=appdata, user_profile=profile)
            config = store.load()

            self.assertEqual(config.download_dir, profile / "Downloads" / "GoTube")

    def test_save_and_load_round_trip(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            appdata = root / "AppData"
            profile = root / "User"
            download_dir = root / "Videos"
            cookies_file = root / "cookies.txt"
            ffmpeg_path = root / "bin" / "ffmpeg.exe"

            from desktop.core.config import DesktopConfig, DesktopConfigStore

            store = DesktopConfigStore(appdata_dir=appdata, user_profile=profile)
            store.save(DesktopConfig(
                download_dir=download_dir,
                cookies_file=cookies_file,
                ffmpeg_path=ffmpeg_path,
                browser_cookie_source="edge",
            ))
            loaded = store.load()

            self.assertEqual(loaded.download_dir, download_dir)
            self.assertEqual(loaded.cookies_file, cookies_file)
            self.assertEqual(loaded.ffmpeg_path, ffmpeg_path)
            self.assertEqual(loaded.browser_cookie_source, "edge")

    def test_invalid_config_falls_back_to_default(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            appdata = root / "AppData"
            profile = root / "User"
            config_path = appdata / "GoTubeDesktop" / "config.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(json.dumps({"download_dir": ""}), encoding="utf-8")

            from desktop.core.config import DesktopConfigStore

            store = DesktopConfigStore(appdata_dir=appdata, user_profile=profile)
            config = store.load()

            self.assertEqual(config.download_dir, profile / "Downloads" / "GoTube")


if __name__ == "__main__":
    unittest.main()
