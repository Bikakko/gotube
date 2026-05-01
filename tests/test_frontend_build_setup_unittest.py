import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = ROOT / '.env.example'
WK_SCRIPT = ROOT / 'wk.sh'
PACKAGE_JSON = ROOT / 'package.json'
BUILD_SCRIPT = ROOT / 'build.js'
ADMIN_HTML = ROOT / 'www' / 'admin' / 'admin.html'
DOWNLOAD_HTML = ROOT / 'www' / 'download.html'
COMMON_JS = ROOT / 'www' / 'common.js'
DOWNLOAD_JS = ROOT / 'www' / 'download.js'
INDEX_JS = ROOT / 'www' / 'index.js'


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

    def test_admin_html_uses_runtime_asset_version_placeholder(self):
        html = ADMIN_HTML.read_text(encoding='utf-8')
        self.assertIn('{{ASSET_VERSION}}', html)
        self.assertNotIn('?v=2.5.0', html)
        self.assertNotIn('?v=2.8.0', html)
        self.assertNotIn('?v=4.1.0', html)

    def test_download_html_uses_runtime_asset_version_placeholder(self):
        html = DOWNLOAD_HTML.read_text(encoding='utf-8')
        self.assertIn('/static/common.js?v={{ASSET_VERSION}}', html)
        self.assertIn('/static/download.js?v={{ASSET_VERSION}}', html)

    def test_frontend_scripts_use_gotube_namespace_boundary(self):
        common = COMMON_JS.read_text(encoding='utf-8')
        download = DOWNLOAD_JS.read_text(encoding='utf-8')
        index = INDEX_JS.read_text(encoding='utf-8')

        self.assertIn('window.GoTube = window.GoTube || {};', common)
        self.assertIn('window.GoTube.session = window.GoTubeSession;', common)
        self.assertIn('const goTube = window.GoTube = window.GoTube || {};', download)
        self.assertIn('const goTube = window.GoTube = window.GoTube || {};', index)


if __name__ == '__main__':
    unittest.main()
