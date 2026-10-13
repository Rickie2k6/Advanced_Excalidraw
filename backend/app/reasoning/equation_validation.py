def is_complete_equation(
    equation_text: str | None,
) -> bool:
    if not equation_text:
        return False

    equation_text = equation_text.strip()

    if "=" not in equation_text:
        return False

    lhs_text, rhs_text = equation_text.split(
        "=",
        1,
    )

    if not lhs_text.strip():
        return False

    if not rhs_text.strip():
        return False

    return True