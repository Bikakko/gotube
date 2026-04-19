import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "st.sh"
PROD_SCRIPT = ROOT / "wk.sh"


class StartScriptTest(unittest.TestCase):
    def test_project_paths_are_relative_to_script_location(self):
        content = SCRIPT.read_text(encoding="utf-8")

        self.assertNotIn('PROJECT_DIR="/root/gotube"', content)
        self.assertNotRegex(content, r'PROJECT_DIR=["\']/')
        self.assertNotRegex(content, r'PROJECT_DIR=["\'][A-Za-z]:')
        self.assertIn('SCRIPT_DIR=', content)
        self.assertRegex(content, re.compile(r'PROJECT_DIR="\$SCRIPT_DIR"'))

    def test_virtualenv_and_pid_paths_are_derived_from_project_dir(self):
        content = SCRIPT.read_text(encoding="utf-8")

        self.assertIn('VENV_DIR="${GOTUBE_VENV_DIR:-$PROJECT_DIR/venv}"', content)
        self.assertIn('PIDFILE="$PROJECT_DIR/.server.pid"', content)


class ProductionStartScriptTest(unittest.TestCase):
    def test_project_paths_are_relative_to_script_location(self):
        content = PROD_SCRIPT.read_text(encoding="utf-8")

        self.assertNotIn('PROJECT_DIR="/root/gotubeweb"', content)
        self.assertNotIn('VENV_DIR="/root/gotube/venv"', content)
        self.assertNotRegex(content, r'PROJECT_DIR=["\']/')
        self.assertNotRegex(content, r'PROJECT_DIR=["\'][A-Za-z]:')
        self.assertIn('SCRIPT_DIR=', content)
        self.assertRegex(content, re.compile(r'PROJECT_DIR="\$SCRIPT_DIR"'))

    def test_virtualenv_log_and_pid_paths_are_derived_from_project_dir(self):
        content = PROD_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('VENV_DIR="${GOTUBE_VENV_DIR:-$PROJECT_DIR/venv}"', content)
        self.assertIn('PIDFILE="$PROJECT_DIR/.server.pid"', content)
        self.assertIn('LOGFILE="$PROJECT_DIR/server.log"', content)

    def test_build_frontend_runs_from_project_dir(self):
        content = PROD_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('cd "$PROJECT_DIR"', content)
        self.assertIn('(cd "$PROJECT_DIR" && node build.js)', content)


if __name__ == "__main__":
    unittest.main()
