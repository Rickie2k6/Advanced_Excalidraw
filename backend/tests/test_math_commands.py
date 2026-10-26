import unittest

from app.services.math_commands import extract_write_math_action


class MathCommandTests(unittest.TestCase):
    def test_command_prefixes_are_excluded_from_expression(self):
        cases = {
            "write math x=4": "x=4",
            " WRITE MATH: x = 4 ": "x = 4",
            "write math: x=4 on the whiteboard": "x=4",
            "write x + 1 = 2": "x + 1 = 2",
            "please write the equation x=5 on whiteboard.": "x=5",
            "write equation: x=5": "x=5",
            "math: x=4": "x=4",
            "viết phương trình x=4 lên bảng": "x=4",
            "viết giúp tôi x=4": "x=4",
            "ghi phương trình x²+1=0": "x²+1=0",
            "viết công thức: 2x + 3 = 7": "2x + 3 = 7",
            "write x=0.5": "x=0.5",
        }
        for command, expression in cases.items():
            with self.subTest(command=command):
                self.assertEqual(extract_write_math_action(command), {
                    "action": "write_math", "expression": expression,
                })

    def test_empty_or_non_commands_do_not_create_actions(self):
        for command in ("", "write", "write math", "write math:", "math:",
                        "viết phương trình", "rewrite x=4", "what does write mean?",
                        "solve x=4", "mathematics x=4"):
            with self.subTest(command=command):
                self.assertIsNone(extract_write_math_action(command))
