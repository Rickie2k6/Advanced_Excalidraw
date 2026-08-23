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

    if "=" not in equation:
        raise ValueError(f"Not an equation: {equation}")

    lhs_text, rhs_text = equation.split("=", 1)

    lhs = parse_side(lhs_text)
    rhs = parse_side(rhs_text)

    return sp.Eq(lhs, rhs)