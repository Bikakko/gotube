import unittest

from fastapi import HTTPException

from server.user_profile import validate_display_name, validate_new_password


class UserProfileValidationTests(unittest.TestCase):
    def test_display_name_accepts_multilingual_letters(self):
        self.assertEqual(validate_display_name("夜空 traveler"), "夜空 traveler")
        self.assertEqual(validate_display_name("さくら"), "さくら")
        self.assertEqual(validate_display_name("민수-01"), "민수-01")

    def test_display_name_normalizes_spaces(self):
        self.assertEqual(validate_display_name("  Alice   Bob  "), "Alice Bob")
        self.assertEqual(validate_display_name("\u3000星空\u3000旅人\u3000"), "星空 旅人")

    def test_display_name_rejects_unsafe_characters(self):
        for value in ["bad<script>", "line\nbreak", "tab\tname", "slash/name"]:
            with self.assertRaises(HTTPException):
                validate_display_name(value)

    def test_password_validation_enforces_length_and_non_blank(self):
        self.assertEqual(validate_new_password("  abc123  "), "abc123")
        with self.assertRaises(HTTPException):
            validate_new_password("123")
        with self.assertRaises(HTTPException):
            validate_new_password("      ")


if __name__ == "__main__":
    unittest.main()
