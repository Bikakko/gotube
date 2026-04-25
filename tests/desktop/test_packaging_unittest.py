import unittest
from pathlib import Path


class DesktopPackagingTests(unittest.TestCase):
    def test_desktop_requirements_include_shell_and_packager(self):
        requirements = Path("requirements-desktop.txt").read_text(encoding="utf-8")

        self.assertIn("PySide6", requirements)
        self.assertIn("pyinstaller", requirements)
        self.assertIn("yt-dlp", requirements)
        self.assertNotIn("pywebview", requirements)

    def test_pyinstaller_spec_bundles_version_and_icon(self):
        spec = Path("desktop/packaging/gotube-desktop.spec").read_text(encoding="utf-8")

        self.assertIn('str(ROOT / "desktop/app.py")', spec)
        self.assertIn("VERSION", spec)
        self.assertIn("GoTubeDesktop", spec)
        self.assertIn("desktop/assets/gotube.ico", spec)
        self.assertTrue(Path("desktop/assets/gotube.ico").is_file())

    def test_gitignore_excludes_desktop_packaging_outputs(self):
        ignore = Path(".gitignore").read_text(encoding="utf-8", errors="ignore")

        self.assertIn("desktop_build/", ignore)
        self.assertIn("desktop_dist/", ignore)
        self.assertIn(".venv-desktop/", ignore)

    def test_desktop_check_script_runs_required_verifications(self):
        script = Path("scripts/desktop_check.py").read_text(encoding="utf-8")

        self.assertIn("unittest", script)
        self.assertIn("tests/desktop", script)
        self.assertIn("py_compile", script)
        self.assertNotIn("desktop/ui/app.js", script)

    def test_desktop_entrypoint_uses_absolute_package_imports_for_pyinstaller(self):
        script = Path("desktop/app.py").read_text(encoding="utf-8")

        self.assertNotIn("from .core", script)
        self.assertIn("from desktop.core.config", script)
        self.assertIn("PySide6", script)

    def test_desktop_build_script_runs_check_before_pyinstaller(self):
        script = Path("scripts/desktop_build.py").read_text(encoding="utf-8")

        self.assertIn("desktop_doctor.py", script)
        self.assertIn("--strict", script)
        self.assertIn("desktop_check.py", script)
        self.assertIn("-m", script)
        self.assertIn("PyInstaller", script)
        self.assertIn("desktop_dist", script)
        self.assertIn("desktop_build", script)
        self.assertIn("desktop/packaging/gotube-desktop.spec", script)


if __name__ == "__main__":
    unittest.main()
