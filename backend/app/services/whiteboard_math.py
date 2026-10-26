"""Build drawing actions from recognized equations and current screenshot OCR."""

import re

from app.services.math_agent import solve_linear_steps


def extract_ocr_equations(analysis: dict) -> list[dict]:
    """Split OCR layout markup without guessing or repairing math symbols."""
    equations = []
    seen = set()
    for box in analysis.get("boxes", []):
        text = box.get("equation") or ""
        # OCR text blocks can contain several separately delimited formulas.
        # The outer-wrapper cleaner may remove only the first/last dollar signs,
        # leaving delimiters attached to individual equations.
        text = re.sub(r"(?<!\\)\$+", "\n", text)
        text = re.sub(r"\\[\[\]() ]", "\n", text)
        # Only unwrap known layout environments. Unknown math commands stay
        # intact so the validated solver rejects them instead of solving a fragment.
        text = re.sub(r"\\begin\{array\}\{[lcr| ]+\}", "", text)
        text = re.sub(r"\\(?:begin|end)\{(?:aligned|align\*?|gathered|gather\*?|array)\}", "", text)
        text = re.sub(r"\\text\{\s*∴\s*\}", "\n", text)
        text = re.sub(r"\\(?:qquad|quad)(?![A-Za-z])", "\n", text)
        text = text.replace("\\\\", "\n").replace("\\ ", "\n")
        text = text.replace("&", "").replace("X", "x")
        for line in text.splitlines():
            expression = line.strip().rstrip(".").strip()
            key = re.sub(r"\s+", "", expression)
            if not key or key in seen:
                continue
            seen.add(key)
            equations.append({"equation": expression})
    return equations


def extract_whiteboard_solve_action(
    question: str, equations: list[dict], analysis: dict | None = None,
) -> dict | None:
    """
    Solve recognized handwritten equations on the whiteboard.

    - "Solve this equation": solve only when exactly one
      valid equation exists.
    - "Solve all equations" or "solve these": solve every valid equation.
    Screenshot boxes have no scene stroke IDs; placement uses the existing
    automatic layout rather than treating screenshot pixels as scene coordinates.
    """

    question_lower = question.strip().lower()

    solve_intent = bool(
        re.search(r"\b(solve|giải)\b", question_lower)
    )

    if not solve_intent:
        return None

    # Explicit equations are handled separately.
    if "=" in question:
        return None

    solve_all = bool(
        re.search(
            r"\b(all|every|each|these|tất cả|toàn bộ)\b",
            question_lower,
        )
    )

    # Prefer equation-group OCR with scene stroke anchors. If it has no
    # recognized equations, use this request's full-whiteboard OCR instead.
    if not equations and analysis:
        equations = extract_ocr_equations(analysis)
    solutions = []

    for equation in equations:
        expression = equation.get("equation", "").strip()

        if "=" not in expression:
            continue

        try:
            result = solve_linear_steps(expression)
        except ValueError:
            continue

        solutions.append({
            **result,
            "source_equation_id": equation.get("equation_id"),
            "source_stroke_ids": equation.get("stroke_ids", []),
            "source_bbox": equation.get("bbox", {}),
        })

    if not solutions:
        return None

    if solve_all:
        return {
            "action": "write_multiple_math_steps",
            "solutions": solutions,
        }

    # Keep existing single-equation behavior.
    if len(solutions) == 1:
        return solutions[0]

    # Multiple equations exist, but user did not
    # explicitly request solving all of them.
    return None
