import unittest

from app.services.whiteboard_math import extract_whiteboard_solve_action


class WhiteboardSolveTests(unittest.TestCase):
    def test_solve_this_uses_current_screenshot_when_store_is_empty(self):
        action = extract_whiteboard_solve_action(
            "solve this", [], {"boxes": [{"equation": "2x+1=5"}]},
        )
        self.assertEqual(action["action"], "write_math_steps")
        self.assertEqual(action["steps"], ["2x+1=5", "2x=4", "x=2"])
        self.assertEqual(action["source_stroke_ids"], [])

    def test_grouped_equations_keep_their_scene_anchors(self):
        action = extract_whiteboard_solve_action(
            "solve this",
            [{"equation_id": "eq1", "equation": "3x=9", "stroke_ids": ["stroke1"]}],
            {"boxes": [{"equation": "2x+1=5"}]},
        )
        self.assertEqual(action["steps"][-1], "x=3")
        self.assertEqual(action["source_stroke_ids"], ["stroke1"])
        self.assertEqual(action["source_equation_id"], "eq1")

    def test_multiple_equations_need_solve_all(self):
        analysis = {"boxes": [{"equation": "2x=4"}, {"equation": "3x=9"}]}
        self.assertIsNone(extract_whiteboard_solve_action("solve this", [], analysis))
        action = extract_whiteboard_solve_action("solve all", [], analysis)
        self.assertEqual(action["action"], "write_multiple_math_steps")
        self.assertEqual(len(action["solutions"]), 2)

    def test_solve_these_draws_all_equations_from_either_ocr_source(self):
        equations = [
            {"equation_id": "eq1", "equation": "2x=4", "stroke_ids": ["s1"]},
            {"equation_id": "eq2", "equation": "3x=9", "stroke_ids": ["s2"]},
        ]
        for command in ("solve these", "Solve these equations", "please solve these."):
            for grouped in (True, False):
                with self.subTest(command=command, grouped=grouped):
                    action = extract_whiteboard_solve_action(
                        command, equations if grouped else [],
                        None if grouped else {"boxes": equations},
                    )
                    self.assertEqual(action["action"], "write_multiple_math_steps")
                    self.assertEqual([s["steps"][-1] for s in action["solutions"]],
                                     ["x=2", "x=3"])
                    self.assertEqual(action["solutions"][0]["source_stroke_ids"],
                                     ["s1"] if grouped else [])

    def test_non_solve_requests_empty_and_unsupported_ocr(self):
        for question, analysis in (
            ("describe this", {"boxes": [{"equation": "2x=4"}]}),
            ("solve x=4", {"boxes": [{"equation": "2x=4"}]}),
            ("solve this", None),
            ("solve this", {"boxes": []}),
            ("solve this", {"boxes": [{"equation": "x^2=4"}]}),
        ):
            with self.subTest(question=question, analysis=analysis):
                self.assertIsNone(extract_whiteboard_solve_action(question, [], analysis))

    def test_logged_multiline_latex_creates_drawing_action(self):
        analysis = {"boxes": [
            {"equation": r"\begin{array}{l}x=4\text{∴}x=5\quad2x+1=5\\x+1=3\\2x=4\quad.\end{array}"},
            {"equation": r"\begin{aligned}X=4\ X=S&2X+1=S\\2X&=4\\2x+1&=5\\X&=2\end{aligned}"},
            {"equation": "2-1=6"},
        ]}
        action = extract_whiteboard_solve_action("solve these", [], analysis)
        self.assertEqual(action["action"], "write_multiple_math_steps")
        originals = [s["steps"][0] for s in action["solutions"]]
        self.assertEqual(originals, ["x=4", "x=5", "2x+1=5", "x+1=3", "2x=4", "x=2"])
        self.assertTrue(all(not s["source_stroke_ids"] for s in action["solutions"]))

    def test_multiline_single_equation_and_ambiguous_ocr(self):
        action = extract_whiteboard_solve_action("solve this", [], {
            "boxes": [{"equation": r"\begin{aligned}2x+1&=5\end{aligned}"}],
        })
        self.assertEqual(action["steps"][-1], "x=2")
        for text in (r"\frac{2x}{3}=4", "X=S", "x=1=2", "2-1=6"):
            with self.subTest(text=text):
                self.assertIsNone(extract_whiteboard_solve_action(
                    "solve these", [], {"boxes": [{"equation": text}]},
                ))
