import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class VisualLabTests(unittest.TestCase):
    def test_visual_lab_pages_exist(self):
        html_a = read_text("www/visual-lab-a.html")
        html_b = read_text("www/visual-lab-b.html")

        self.assertIn('data-visual-theme="a"', html_a)
        self.assertIn('data-visual-theme="b"', html_b)
        self.assertIn("/static/visual-lab.css", html_a)
        self.assertIn("/static/visual-lab.js", html_b)
        self.assertIn('class="lab-sky"', html_b)
        self.assertIn('class="lab-clouds"', html_b)
        self.assertIn('class="lab-stars"', html_b)
        self.assertIn('class="lab-moon"', html_b)

    def test_visual_lab_assets_define_two_visual_routes(self):
        css = read_text("www/visual-lab.css")
        js = read_text("www/visual-lab.js")

        self.assertIn('body[data-visual-theme="a"]', css)
        self.assertIn('body[data-visual-theme="b"]', css)
        self.assertIn(".lab-sky", css)
        self.assertIn('fetch("/api/gallery/albums")', js)
        self.assertIn("lab-card", js)
        self.assertIn("openModal", js)
        self.assertIn("startMoonSky", js)
        self.assertIn('moonImage.src = "/static/moon.png"', js)
        self.assertIn("@keyframes moon-cloud-a", css)
        self.assertIn("@keyframes moon-star-twinkle", css)


if __name__ == "__main__":
    unittest.main()
