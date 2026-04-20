import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "st.sh"
PROD_SCRIPT = ROOT / "wk.sh"
ENV_EXAMPLE = ROOT / ".env.example"
RUNTIME_SCRIPT = ROOT / "scripts" / "gotube_runtime.sh"


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

        self.assertIn('source "$PROJECT_DIR/scripts/gotube_runtime.sh"', content)
        self.assertIn("runtime_load_common_config", content)
        self.assertIn('GOTUBE_PID_FILE', content)

    def test_development_script_supports_init_and_doctor_commands(self):
        content = SCRIPT.read_text(encoding="utf-8")

        self.assertIn('echo "  $0 init', content)
        self.assertIn('echo "  $0 doctor', content)
        self.assertIn('case "${1:-start}" in', content)
        self.assertRegex(content, re.compile(r'\n\s*init\)'))
        self.assertRegex(content, re.compile(r'\n\s*doctor\)'))


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

        self.assertIn('source "$PROJECT_DIR/scripts/gotube_runtime.sh"', content)
        self.assertIn("runtime_load_common_config", content)
        self.assertIn('GOTUBE_PID_FILE', content)
        self.assertIn('GOTUBE_LOG_FILE', content)

    def test_build_frontend_runs_from_project_dir(self):
        content = RUNTIME_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('(cd "$PROJECT_DIR" && node build.js)', content)
        self.assertIn('(cd "$PROJECT_DIR" && npm install --silent)', content)

    def test_production_script_supports_init_and_doctor_commands(self):
        content = PROD_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('echo "  $0 init', content)
        self.assertIn('echo "  $0 doctor', content)
        self.assertRegex(content, re.compile(r'\n\s*init\)'))
        self.assertRegex(content, re.compile(r'\n\s*doctor\)'))


class EnvExampleStartupConfigTest(unittest.TestCase):
    def test_env_example_documents_runtime_startup_switches(self):
        content = ENV_EXAMPLE.read_text(encoding="utf-8")

        self.assertIn("GOTUBE_HOST=0.0.0.0", content)
        self.assertIn("GOTUBE_VENV_DIR=./venv", content)
        self.assertIn("GOTUBE_PID_FILE=./.server.pid", content)
        self.assertIn("GOTUBE_LOG_FILE=./server.log", content)
        self.assertIn("GOTUBE_WORKERS=1", content)
        self.assertRegex(content, re.compile(r"GOTUBE_BUILD_FRONTEND=\d"))
        self.assertIn("GOTUBE_AUTO_INIT_VENV=1", content)
        self.assertIn("GOTUBE_AUTO_INSTALL_DEPS=1", content)


if __name__ == "__main__":
    unittest.main()
