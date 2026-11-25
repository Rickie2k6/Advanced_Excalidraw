"""HTTP contracts with mocked OCR, model replies, and object detection."""
import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.api.routes import chat as route


class ChatContractTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(route.router, prefix="/api")
        self.client = TestClient(app)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        defaults = {
            "WHITEBOARD_IMAGES_DIR": Path(self.temp.name),
            "load_equations": [],
            "build_equation_context": "mock equations",
            "analyze_whiteboard": self.analysis(),
            "generate_reply": "Mock answer",
            "analyze_inserted_image": "A chart",
            "extract_visual_target": {"action": "circle", "target_description": "target"},
            "detect_target": [{"bbox": [20, 10, 60, 30], "score": 0.9}],
            "select_visual_candidate": {"bbox": [20, 10, 60, 30]},
            "update_scene": None,
            "update_analysis": None,
        }
        self.mocks = {}
        for name, value in defaults.items():
            replacement = patch.object(route, name, value) if name == "WHITEBOARD_IMAGES_DIR" else patch.object(route, name, return_value=value)
            self.mocks[name] = replacement.start()
            self.addCleanup(replacement.stop)

    @staticmethod
    def analysis():
        return {"timestamp": "2026-11-03T00:00:00Z", "image_width": 200,
                "image_height": 100, "box_count": 1,
                "boxes": [{"id": 1, "label": "formula", "bbox": [0, 0, 40, 20], "equation": "2x+1=5"}],
                "all_block_count": 1, "all_block_labels": ["formula"]}

    @staticmethod
    def png():
        output = io.BytesIO()
        Image.new("RGB", (200, 100), "white").save(output, "PNG")
        return output.getvalue()

    def post(self, question, scene=None, image=True):
        return self.client.post("/api/chat", data={
            "question": question,
            "scene_json": json.dumps(scene or {"elements": [], "files": {}}),
        }, files={"whiteboard": ("board.png", self.png(), "image/png")} if image else None)

    def test_write_does_not_depend_on_ocr_detector_or_llm(self):
        for name in ("analyze_whiteboard", "generate_reply", "detect_target"):
            self.mocks[name].side_effect = RuntimeError("unavailable")
        response = self.post("Write x^2 + 2x + 1")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["visual_action"], {"action": "write_math", "expression": "x^2 + 2x + 1"})
        self.assertIsInstance(response.json()["answer"], str)
        self.mocks["analyze_whiteboard"].assert_not_called()
        self.mocks["generate_reply"].assert_not_called()

    def test_explicit_solve_contract_and_no_partial_expression_match(self):
        response = self.post("Solve 2x+1=5", image=False)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["visual_action"], {"action": "write_math_steps", "steps": ["2x+1=5", "2x=4", "x=2"]})
        for question in ("Solve x^2=4", "Solve 2x=4/3", "Solve 2x=4 and x=3"):
            self.assertIsNone(route.extract_solve_math_action(question))

    def test_grouped_solve_preserves_anchors_without_ocr(self):
        self.mocks["load_equations"].return_value = [
            {"equation_id": "eq1", "equation": "2x+1=5", "stroke_ids": ["s1"], "bbox": {"x": 12}},
            {"equation_id": "eq2", "equation": "3x=9", "stroke_ids": ["s2"]},
        ]
        data = self.post("Solve all equations").json()
        self.assertEqual(data["visual_action"]["action"], "write_multiple_math_steps")
        solutions = data["visual_action"]["solutions"]
        self.assertEqual(solutions[0]["source_stroke_ids"], ["s1"])
        self.assertEqual(solutions[0]["source_bbox"], {"x": 12})
        self.assertEqual(solutions[1]["steps"][-1], "x=3")
        self.mocks["analyze_whiteboard"].assert_not_called()

    def test_screenshot_ocr_solve_contract(self):
        data = self.post("Solve this equation").json()
        self.assertEqual(data["visual_action"]["steps"], ["2x+1=5", "2x=4", "x=2"])
        self.assertEqual(data["visual_action"]["source_stroke_ids"], [])
        self.mocks["generate_reply"].assert_not_called()

    def test_circle_uses_original_image_pixels_and_canvas_geometry(self):
        scene = {
            "elements": [{"id": "im", "type": "image", "fileId": "f", "x": 100, "y": 200, "width": 400, "height": 200}],
            "files": {"f": {"dataURL": "data:image/png;base64," + base64.b64encode(self.png()).decode()}},
        }
        # A screenshot OCR outage must not disable image target detection.
        self.mocks["analyze_whiteboard"].side_effect = RuntimeError("OCR unavailable")
        response = self.post("Circle the target", scene)
        self.assertEqual(response.status_code, 200, response.text)
        action = response.json()["visual_action"]
        self.assertEqual(action["action"], "circle")
        self.assertAlmostEqual(action["x"], 130.4)
        self.assertAlmostEqual(action["y"], 215.2)
        self.assertAlmostEqual(action["width"], 99.2)
        self.assertAlmostEqual(action["height"], 49.6)
        self.mocks["detect_target"].assert_called_once()
        self.mocks["generate_reply"].assert_not_called()

    def test_circle_finds_uploaded_file_in_canonical_storage(self):
        (Path(self.temp.name) / "f.png").write_bytes(self.png())
        scene = {"elements": [{"type": "image", "fileId": "f", "x": 0, "y": 0, "width": 200, "height": 100}]}
        self.assertEqual(self.post("circle target", scene, image=False).json()["visual_action"]["action"], "circle")

    def test_no_circle_action_without_selected_target(self):
        self.mocks["select_visual_candidate"].return_value = None
        scene = {"elements": [{"type": "image", "fileId": "f", "x": 0, "y": 0, "width": 200, "height": 100}],
                 "files": {"f": {"dataURL": "data:image/png;base64," + base64.b64encode(self.png()).decode()}}}
        data = self.post("circle target", scene, image=False).json()
        self.assertIsNone(data["visual_action"])
        self.assertIn("couldn't locate", data["answer"])
        self.mocks["generate_reply"].assert_not_called()

    def test_malformed_scene_is_a_helpful_400_and_no_public_prefix_routes(self):
        for scene_json in ("invalid", "42", '{"elements":[1]}', '{"files":[]}'):
            response = self.client.post("/api/chat", data={"question": "hi", "scene_json": scene_json})
            self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(self.client.post("/talk-sketch/api/chat").status_code, 404)

    def test_main_routes_keep_backend_paths(self):
        from app.main import app
        client = TestClient(app)
        self.assertEqual(client.get("/health").status_code, 200)
        self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(client.post("/api/chat", data={"question": "Write x=2"}).status_code, 200)
        self.assertEqual(client.get("/talk-sketch/health").status_code, 404)
