import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
)

transformations = (
    standard_transformations
    + (implicit_multiplication_application,)
)


def parse_side(text: str):
    text = text.strip()

    if not text:
        raise ValueError(
            "Equation side is empty."
        )

    return parse_expr(
        text,
        transformations=transformations,
        evaluate=False,
    )


def parse_equation(equation: str):
    """
    Example:
        "3x + 1 = 0"

    Returns:
        Eq(3*x + 1, 0)
    """

    if not equation:
        raise ValueError(
            "Equation is empty."
        )

    equation = equation.strip()

    if "=" not in equation:
        raise ValueError(
            f"Not an equation: {equation}"
        )

    lhs_text, rhs_text = equation.split(
        "=",
        1,
    )

    lhs_text = lhs_text.strip()
    rhs_text = rhs_text.strip()

    if not lhs_text:
        raise ValueError(
            f"Missing left-hand side: {equation}"
        )

    if not rhs_text:
        raise ValueError(
            f"Missing right-hand side: {equation}"
        )

    lhs = parse_side(
        lhs_text
    )

    rhs = parse_side(
        rhs_text
    )

    return sp.Eq(
        lhs,
        rhs,
    )