def format_analysis(
    analysis: dict,
) -> str:
    box_count = analysis[
        "box_count"
    ]

    if box_count == 0:
        labels = analysis.get(
            "all_block_labels",
            [],
        )

        return (
            "PaddleOCR detected "
            "0 equation boxes.\n\n"
            "Detected layout labels: "
            f"{labels}"
        )

    lines = [
        (
            "PaddleOCR detected "
            f"{box_count} "
            "equation box"
            f"{'es' if box_count != 1 else ''}."
        ),
        "",
    ]

    for box in analysis[
        "boxes"
    ]:
        equation = (
            box["equation"]
            or "[empty recognition]"
        )

        lines.append(
            f"Box {box['id']}: "
            f"{equation}"
        )

    return "\n".join(
        lines
    )