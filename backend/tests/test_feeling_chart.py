"""Regression coverage for SAD being circled as EMBARRASSED."""

from pathlib import Path
import unittest

from app.services.feeling_chart import LAYOUT, is_known_feeling_chart, resolve_feeling_label
from app.services.visual_geometry import image_bbox_to_excalidraw


class FeelingChartTests(unittest.TestCase):
    def test_sad_is_first_row_second_column(self):
        sad = resolve_feeling_label(" sad ")
        self.assertEqual(sad["label"], "SAD")
        self.assertEqual(sad["bbox"], [305, 148, 461, 304])
        embarrassed = resolve_feeling_label("EMBARRASSED")
        self.assertEqual(embarrassed["bbox"], [527, 413, 683, 569])

    def test_every_label_has_unique_bounds(self):
        bounds = {tuple(resolve_feeling_label(label)["bbox"])
                  for row in LAYOUT for label in row}
        self.assertEqual(len(bounds), 20)
        for label in (None, "", "not a feeling", 1):
            self.assertIsNone(resolve_feeling_label(label))

    def test_scene_offset_and_resize_preserve_sad_center(self):
        result = image_bbox_to_excalidraw(
            resolve_feeling_label("SAD")["bbox"],
            {"x": -100, "y": 300, "width": 500.5, "height": 720},
            1001, 1440,
        )
        self.assertAlmostEqual(result["x"] + result["width"] / 2, 91.5)
        self.assertAlmostEqual(result["y"] + result["height"] / 2, 413)

    def test_geometry_only_applies_to_verified_asset(self):
        root = Path(__file__).resolve().parents[2]
        self.assertTrue(is_known_feeling_chart(str(
            root / "data/whiteboard_images/e3b9d61b3e3f6f2253f31acf61e514f4ac850944.jpg")))
        self.assertFalse(is_known_feeling_chart(__file__))
