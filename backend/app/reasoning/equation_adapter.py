import re


def clean_latex_equation(text: str) -> str:
    """
    Convert simple OCR LaTeX into the plain algebra format
    expected by equation_parser.py.

    Example:
        "3x+1&=0" -> "3x+1=0"
    """

    text = text.strip()

    # Alignment marker used by LaTeX aligned environment
    text = text.replace("&", "")

    # Basic spacing commands
    text = text.replace(r"\,", "")
    text = text.replace(r"\;", "")
    text = text.replace(r"\ ", "")

    return text.strip()


def split_aligned_equations(text: str):
    if not text:
        return []

    text = text.strip()

    # --------------------------------------------------
    # Handle LaTeX aligned environment
    #
    # Example:
    # \begin{aligned}
    # 3x+1&=0\\
    # 3x&=-1
    # \end{aligned}
    # --------------------------------------------------
    if r"\begin{aligned}" in text:
        text = text.replace(
            r"\begin{aligned}",
            "",
        )

        text = text.replace(
            r"\end{aligned}",
            "",
        )

    # --------------------------------------------------
    # Handle LaTeX array environment
    #
    # Example:
    # \begin{array}{l}
    # 2x=5\\
    # x=0
    # \end{array}
    # --------------------------------------------------
    elif r"\begin{array}" in text:

        # Remove:
        # \begin{array}{l}
        # \begin{array}{c}
        # etc.
        text = re.sub(
            r"\\begin\{array\}\{[^}]*\}",
            "",
            text,
        )

        text = text.replace(
            r"\end{array}",
            "",
        )

    else:
        return [
            clean_latex_equation(text)
        ]

    # Split LaTeX line breaks: \\
    parts = re.split(
        r"\\\\",
        text,
    )

    equations = []

    for part in parts:
        cleaned = clean_latex_equation(
            part
        )

        if cleaned:
            equations.append(
                cleaned
            )

    return equations


def split_bbox_vertically(bbox, count):
    """
    Temporary MVP solution.

    If OCR grouped several vertically stacked equations
    into one block, estimate one bbox per line.
    """

    if not bbox or count <= 1:
        return [bbox]

    line_height = bbox["height"] / count

    boxes = []

    for index in range(count):
        boxes.append(
            {
                "x": bbox["x"],
                "y": bbox["y"] + index * line_height,
                "width": bbox["width"],
                "height": line_height,
            }
        )

    return boxes


def adapt_equations_json(data):
    """
    Convert raw equations.json into reasoning-ready equations.

    Returns:

    [
        {
            "id": "...",
            "equation": "3x+1=0",
            "bbox": {...}
        },
        ...
    ]
    """

    raw_equations = data.get("equations", {})

    if isinstance(raw_equations, dict):
        raw_equations = list(raw_equations.values())

    result = []

    for item in raw_equations:

        equation_id = item.get("equation_id")
        text = item.get("equation")

        if not text:
            continue

        split_equations = split_aligned_equations(text)

        boxes = split_bbox_vertically(
            item.get("bbox"),
            len(split_equations),
        )

        for index, equation_text in enumerate(split_equations):

            # Ignore obvious OCR noise
            if equation_text in {
                r"\bullet",
                "•",
                ".",
            }:
                continue

            child_id = equation_id

            if len(split_equations) > 1:
                child_id = f"{equation_id}_line_{index + 1}"

            result.append(
                {
                    "id": child_id,
                    "equation": equation_text,
                    "bbox": boxes[index],
                    "parent_equation_id": equation_id,
                    "stroke_ids": item.get("stroke_ids", []),
                    "contributors": item.get("contributors", []),
                    "confidence": item.get("confidence"),
                }
            )

    return result