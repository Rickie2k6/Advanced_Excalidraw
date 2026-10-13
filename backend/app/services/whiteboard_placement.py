from typing import Any


PADDING = 20
GAP = 30


def get_element_bbox(element: dict[str, Any]):
    if element.get("isDeleted"):
        return None

    x = element.get("x")
    y = element.get("y")
    width = element.get("width")
    height = element.get("height")

    if None in (x, y, width, height):
        return None

    return {
        "x1": x - PADDING,
        "y1": y - PADDING,
        "x2": x + width + PADDING,
        "y2": y + height + PADDING,
    }


def overlaps(a, b):
    return not (
        a["x2"] <= b["x1"]
        or a["x1"] >= b["x2"]
        or a["y2"] <= b["y1"]
        or a["y1"] >= b["y2"]
    )


def estimate_math_size(expression: str):
    font_size = 28

    width = max(
        80,
        len(expression) * font_size * 0.62,
    )

    height = font_size * 1.5

    return width, height


def find_free_position(
    scene: dict,
    expression: str,
):
    elements = scene.get("elements", [])

    occupied = []

    for element in elements:
        bbox = get_element_bbox(element)

        if bbox:
            occupied.append(bbox)

    width, height = estimate_math_size(expression)

    # Search from upper-left downward
    for y in range(100, 2000, 60):
        for x in range(100, 3000, 100):

            candidate = {
                "x1": x,
                "y1": y,
                "x2": x + width,
                "y2": y + height,
            }

            if all(
                not overlaps(candidate, box)
                for box in occupied
            ):
                return {
                    "x": x,
                    "y": y,
                }

    # Emergency fallback
    return {
        "x": 100,
        "y": 1000,
    }