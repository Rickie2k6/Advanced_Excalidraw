from app.reasoning.graph import build_equation_graph
from app.reasoning.frontier import find_frontiers
from app.reasoning.equation_parser import parse_equation
from app.reasoning.next_step import generate_next_step
from app.reasoning.instruction import generate_instruction
from app.reasoning.equation_validation import (
    is_complete_equation,
)

def get_equation_text(equation):
    for key in (
        "latex",
        "equation",
        "text",
        "recognized_text",
    ):
        value = equation.get(key)

        if value:
            return value

    return None




def analyze_equations(equations):
    """
    Full reasoning pipeline:

    equations
        -> relationship graph
        -> frontier
        -> next step
        -> tutoring instruction
    """

    # 1. Build relationships between equations.
    edges = build_equation_graph(
        equations
    )

    # 2. Find the latest equation in each chain.
    # Standalone equations are also considered frontiers.
    frontiers = find_frontiers(
        equations,
        edges,
    )

    hints = []

    # 3. Generate one hint for each frontier.
    for frontier in frontiers:

        equation_text = get_equation_text(
            frontier
        )

        if not equation_text:
            continue

        equation_text = equation_text.strip()

        # --------------------------------------------
        # Skip OCR groups that are not complete
        # equations.
        # --------------------------------------------

        if not is_complete_equation(
            equation_text
        ):
            print(
                "[pipeline] Skipping invalid "
                f"equation {frontier.get('id')}: "
                f"{equation_text}"
            )

            continue

        try:
            parsed_equation = parse_equation(
                equation_text
            )

        except Exception as exc:
            print(
                f"[pipeline] Failed to parse "
                f"{frontier.get('id')}: {exc}"
            )

            continue

        # 4. Determine the verified next
        # mathematical step.
        next_step = generate_next_step(
            parsed_equation
        )

        # 5. Convert the mathematical step
        # into a tutoring instruction.
        instruction = generate_instruction(
            next_step
        )

        if not instruction:
            continue

        # 6. Convert possible SymPy values
        # into JSON-safe values.
        json_next_step = dict(
            next_step
        )

        if (
            json_next_step.get("value")
            is not None
        ):
            json_next_step["value"] = str(
                json_next_step["value"]
            )

        # 7. Attach hint to the equation's bbox.
        hints.append(
            {
                "anchor_equation_id":
                    frontier["id"],

                "equation":
                    equation_text,

                "bbox":
                    frontier.get("bbox"),

                "next_step":
                    json_next_step,

                "instruction":
                    instruction,
            }
        )

    return {
        "edges":
            edges,

        "frontiers": [
            frontier["id"]
            for frontier in frontiers
        ],

        "hints":
            hints,
    }