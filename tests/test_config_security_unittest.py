import unittest

from server.config import validate_hidden_path


class ConfigSecurityTests(unittest.TestCase):
    def test_validate_hidden_path_accepts_safe_segment(self):
        self.assertEqual(validate_hidden_path("safe-path_123"), "safe-path_123")

    def test_validate_hidden_path_rejects_invalid_characters(self):
        for value in ["", "with/slash", "..", " space ", "semi;colon", "中文"]:
            with self.assertRaises(ValueError, msg=value):
                validate_hidden_path(value)


if __name__ == "__main__":
    unittest.main()
