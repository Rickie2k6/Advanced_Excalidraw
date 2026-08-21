from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(
    "/home/student/chuynh/Chatbot/data"
)

EQUATIONS_FILE = (
    DATA_DIR /
    "equations.json"
)


def load_equations() -> list[dict[str, Any]]:
    """
    Load recognized equations from equations.json.

    Only equations with a non-empty OCR result
    are returned.
    """

    if not EQUATIONS_FILE.exists():
        return []

    try:
        data = json.loads(
            EQUATIONS_FILE.read_text(
                encoding="utf-8"
            )
        )

    except (
        json.JSONDecodeError,
        OSError,
    ):
        return []

    equations = data.get(
        "equations",
        {},
    )

    recognized = []

    for equation_id, record in equations.items():

        equation_text = record.get(
            "equation"
        )

        if not equation_text:
            continue

        bbox = record.get(
            "bbox",
            {},
        )

        recognized.append({
            "equation_id":
                equation_id,

            "equation":
                equation_text,

            "stroke_ids":
                record.get(
                    "stroke_ids",
                    [],
                ),

            "contributors":
                record.get(
                    "contributors",
                    [],
                ),

            "bbox":
                bbox,
        })

    # Keep roughly the same reading order
    # as equations appear on the whiteboard.
    recognized.sort(
        key=lambda item: (
            item.get(
                "bbox",
                {},
            ).get(
                "y",
                0,
            ),

            item.get(
                "bbox",
                {},
            ).get(
                "x",
                0,
            ),
        )
    )

    return recognized


def build_equation_context() -> str:
    """
    Convert equations.json into concise text
    that can be supplied to the LLM.
    """

    equations = (
        load_equations()
    )

    if not equations:
        return (
            "There are currently no "
            "recognized equations on "
            "the whiteboard."
        )

    lines = [
        "Recognized equations currently "
        "on the whiteboard:"
    ]

    for index, item in enumerate(
        equations,
        start=1,
    ):

        contributors = (
            item.get(
                "contributors",
                [],
            )
        )

        contributor_text = (
            ", ".join(
                contributors
            )
            if contributors
            else "unknown"
        )

        lines.append(
            (
                f"{index}. "
                f"{item['equation']} "
                f"[equation_id="
                f"{item['equation_id']}; "
                f"contributors="
                f"{contributor_text}]"
            )
        )

    return "\n".join(
        lines
    )