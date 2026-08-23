import json
import math

from app.reasoning.equation_parser import parse_equation
from app.reasoning.relationship import detect_relationship


def get_bbox(equation):
    """
    Return equation bounding box if available.
    """

    return equation.get("bbox")


def get_center(bbox):
    return (
        bbox["x"] + bbox["width"] / 2,
        bbox["y"] + bbox["height"] / 2,
    )


def spatial_score(source, target):
    """
    Estimate whether target is spatially likely to be
    the next step after source.

    Higher score when:
    - target is below source
    - both equations are roughly in the same column
    - equations are reasonably close
    """

    source_bbox = get_bbox(source)
    target_bbox = get_bbox(target)

    # No position data yet -> neutral score
    if not source_bbox or not target_bbox:
        return 0.5

    x1, y1 = get_center(source_bbox)
    x2, y2 = get_center(target_bbox)

    dx = abs(x2 - x1)
    dy = y2 - y1

    # We normally expect the next equation below
    if dy <= 0:
        return 0.0

    score = 0.0

    # Below source
    score += 0.4

    # Same approximate column
    if dx < 80:
        score += 0.4
    elif dx < 150:
        score += 0.2

    distance = math.sqrt(dx**2 + dy**2)

    # Reasonably close
    if distance < 250:
        score += 0.2
    elif distance < 450:
        score += 0.1

    return min(score, 1.0)


def get_equation_text(equation):
    """
    Support several possible field names.
    """

    for key in ("latex", "equation", "text", "recognized_text"):
        value = equation.get(key)

        if value:
            return value

    return None


def build_equation_graph(equations):
    """
    Build directed relationships between equations.

    Example:
        eq_1: 3x + 1 = 0
        eq_4: 3x = -1

    Produces:
        eq_1 -> eq_4
    """

    edges = []

    for source in equations:
        source_text = get_equation_text(source)

        if not source_text:
            continue

        try:
            source_sympy = parse_equation(source_text)
        except Exception as exc:
            print(
                f"[graph] Could not parse {source.get('id')}: "
                f"{source_text}: {exc}"
            )
            continue

        for target in equations:

            if source.get("id") == target.get("id"):
                continue

            target_text = get_equation_text(target)

            if not target_text:
                continue

            # If position exists, don't connect upward.
            source_bbox = get_bbox(source)
            target_bbox = get_bbox(target)

            if source_bbox and target_bbox:
                source_y = source_bbox["y"]
                target_y = target_bbox["y"]

                if target_y <= source_y:
                    continue

            try:
                target_sympy = parse_equation(target_text)
            except Exception:
                continue

            relationship = detect_relationship(
                source_sympy,
                target_sympy,
            )

            if not relationship["valid"]:
                continue

            spatial = spatial_score(source, target)

            # Math validity is most important.
            confidence = 0.8 + (0.2 * spatial)

            edges.append(
                {
                    "from": source["id"],
                    "to": target["id"],
                    "from_equation": source_text,
                    "to_equation": target_text,
                    "operation": relationship["operation"],
                    "value": str(relationship["value"]),
                    "spatial_score": round(spatial, 3),
                    "confidence": round(confidence, 3),
                }
            )

    return edges


def load_equations(path):
    """
    Load equations.json.

    Supports either:

    [
        {...},
        {...}
    ]

    or:

    {
        "equations": [...]
    }
    """

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return data.get("equations", [])

    raise ValueError("Unsupported equations.json format")