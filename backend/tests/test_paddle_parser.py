from types import SimpleNamespace
import unittest

from app.services.paddle.parser import extract_formula_blocks
from app.services.whiteboard_math import extract_whiteboard_solve_action


class TextEquationTests(unittest.TestCase):
    def parse(self, blocks):
        return extract_formula_blocks(SimpleNamespace(json={
            "res": {"parsing_res_list": blocks},
        }))

    def test_text_classification_still_creates_whiteboard_solutions(self):
        formulas, labels, count = self.parse([{
            "block_label": "text", "block_content": "2x+1=5\nx+1=3",
            "block_bbox": [0, 0, 100, 100],
        }])
        self.assertEqual(labels, ["text"])
        self.assertEqual(count, 1)
        action = extract_whiteboard_solve_action("solve these", [], {"boxes": formulas})
        self.assertEqual(action["action"], "write_multiple_math_steps")
        self.assertEqual([s["steps"][-1] for s in action["solutions"]], ["x=2", "x=2"])

    def test_normal_text_and_images_are_excluded(self):
        formulas, _, _ = self.parse([
            {"block_label": "text", "block_content": "Hello world"},
            {"block_label": "image", "block_content": "x=4"},
            {"block_label": "display_formula", "block_content": "$x=4$"},
        ])
        self.assertEqual([f["equation"] for f in formulas], ["x=4"])

    def test_prose_with_equals_does_not_create_math_action(self):
        formulas, _, _ = self.parse([{
            "block_label": "text", "block_content": "the answer = unknown",
        }])
        self.assertIsNone(extract_whiteboard_solve_action("solve these", [], {"boxes": formulas}))

    def test_logged_dollar_delimited_equations_produce_both_drawings(self):
        for content in ("x+1=6 $\n\n $ 2x=0", "$x+1=6 $\n\n $ 2x=0$",
                        "$x+1=6$ $2x=0$", r"\[x+1=6\] \(2x=0\)"):
            with self.subTest(content=content):
                formulas, _, _ = self.parse([{
                    "block_label": "text", "block_content": content,
                }])
                action = extract_whiteboard_solve_action("solve these", [], {"boxes": formulas})
                self.assertEqual(action["action"], "write_multiple_math_steps")
                self.assertEqual([s["steps"] for s in action["solutions"]], [
                    ["x+1=6", "x=5"], ["2x=0", "x=0"],
                ])
