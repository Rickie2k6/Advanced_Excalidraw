import sympy as sp


def get_variables(eq):
    """Get all variables appearing in both equations sides."""
    return eq.lhs.free_symbols | eq.rhs.free_symbols


def is_constant(expr, variables):
    """True if expr does not contain any equation variables."""
    return len(expr.free_symbols & variables) == 0


def detect_add_subtract(eq1, eq2):
    """
    Detect operations such as:

        3x + 1 = 0
             ↓ subtract 1
        3x = -1
    """

    variables = get_variables(eq1) | get_variables(eq2)

    lhs_change = sp.simplify(eq2.lhs - eq1.lhs)
    rhs_change = sp.simplify(eq2.rhs - eq1.rhs)

    # The same amount must be added to both sides.
    if sp.simplify(lhs_change - rhs_change) != 0:
        return None

    # The change must be a constant.
    if not is_constant(lhs_change, variables):
        return None

    if lhs_change == 0:
        return None

    if lhs_change < 0:
        return {
            "valid": True,
            "operation": "subtract_both_sides",
            "value": sp.simplify(-lhs_change),
        }

    return {
        "valid": True,
        "operation": "add_both_sides",
        "value": sp.simplify(lhs_change),
    }


def detect_multiply_divide(eq1, eq2):
    """
    Detect operations such as:

        3x = -1
          ↓ divide by 3
        x = -1/3
    """

    variables = get_variables(eq1) | get_variables(eq2)

    candidates = []

    if eq1.lhs != 0:
        candidates.append(
            sp.simplify(eq2.lhs / eq1.lhs)
        )

    if eq1.rhs != 0:
        candidates.append(
            sp.simplify(eq2.rhs / eq1.rhs)
        )

    for factor in candidates:

        if factor == 0 or factor == 1:
            continue

        # Factor must not contain x, y, etc.
        if not is_constant(factor, variables):
            continue

        lhs_valid = (
            sp.simplify(
                eq2.lhs - factor * eq1.lhs
            ) == 0
        )

        rhs_valid = (
            sp.simplify(
                eq2.rhs - factor * eq1.rhs
            ) == 0
        )

        if not (lhs_valid and rhs_valid):
            continue

        # Example factor = 1/3 means divide by 3.
        reciprocal = sp.simplify(1 / factor)

        if (
            factor.is_Rational
            and abs(factor) < 1
        ):
            return {
                "valid": True,
                "operation": "divide_both_sides",
                "value": reciprocal,
            }

        return {
            "valid": True,
            "operation": "multiply_both_sides",
            "value": factor,
        }

    return None


def detect_relationship(eq1, eq2):
    """
    Determine whether eq2 is a valid direct transformation
    from eq1.
    """

    result = detect_add_subtract(eq1, eq2)

    if result:
        return result

    result = detect_multiply_divide(eq1, eq2)

    if result:
        return result

    return {
        "valid": False,
        "operation": None,
        "value": None,
    }