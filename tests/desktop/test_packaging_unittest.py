import unittest
from pathlib import Path


class DesktopPackagingTests(unittest.TestCase):
    def test_desktop_requirements_include_shell_and_packager(self):
        requirements = Path("requirements-desktop.txt").read_text(encoding="utf-8")

        self.assertIn("pywebview", requirements)
        self.assertIn("pyinstaller", requirements)
        self.assertIn("yt-dlp", requirements)

    def test_pyinstaller_spec_bundles_ui_and_version(self):
        spec = Path("desktop/packaging/gotube-desktop.spec").read_text(encoding="utf-8")

        self.assertIn('str(ROOT / "desktop/app.py")', spec)
        self.assertIn("desktop/ui", spec)
        self.assertIn("VERSION", spec)
        self.assertIn("GoTubeDesktop", spec)

    def test_gitignore_excludes_desktop_packaging_outputs(self):
        ignore = Path(".gitignore").read_text(encoding="utf-8", errors="ignore")

        self.assertIn("desktop_build/", ignore)
        self.assertIn("desktop_dist/", ignore)
        self.assertIn(".venv-desktop/", ignore)

    def test_desktop_check_script_runs_required_verifications(self):
        script = Path("scripts/desktop_check.py").read_text(encoding="utf-8")

        self.assertIn("unittest", script)
        self.assertIn("tests/desktop", script)
        self.assertIn("node", script)
        self.assertIn("--check", script)
        self.assertIn("py_compile", script)

    def test_desktop_entrypoint_uses_absolute_package_imports_for_pyinstaller(self):
        script = Path("desktop/app.py").read_text(encoding="utf-8")

        self.assertNotIn("from .core", script)
        self.assertIn("from desktop.core.config", script)

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
