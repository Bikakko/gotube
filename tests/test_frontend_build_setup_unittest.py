import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = ROOT / '.env.example'
WK_SCRIPT = ROOT / 'wk.sh'
PACKAGE_JSON = ROOT / 'package.json'
BUILD_SCRIPT = ROOT / 'build.js'


class FrontendBuildSetupTests(unittest.TestCase):
    def test_env_example_enables_production_frontend_build_output(self):
        content = ENV_EXAMPLE.read_text(encoding='utf-8')
        self.assertIn('GOTUBE_BUILD_FRONTEND=1', content)
        self.assertIn('GOTUBE_WWW_DIR=www_dist', content)

    def test_production_script_uses_timestamped_access_log_format(self):
        content = WK_SCRIPT.read_text(encoding='utf-8')
        self.assertIn('--access-logformat', content)
        self.assertIn('%(t)s', content)

    def test_frontend_build_files_exist(self):
        self.assertTrue(PACKAGE_JSON.exists())
        self.assertTrue(BUILD_SCRIPT.exists())

    def test_package_json_declares_minification_dependencies(self):
        package = json.loads(PACKAGE_JSON.read_text(encoding='utf-8'))
        deps = package.get('devDependencies', {})
        for name in ['terser', 'clean-css', 'html-minifier-terser']:
            self.assertIn(name, deps)

    def test_build_script_targets_www_dist(self):
        content = BUILD_SCRIPT.read_text(encoding='utf-8')
        self.assertIn('www_dist', content)
        self.assertIn('html-minifier-terser', content)
        self.assertIn('terser', content)
        self.assertIn('new CleanCSS', content)


if __name__ == '__main__':
    unittest.main()
