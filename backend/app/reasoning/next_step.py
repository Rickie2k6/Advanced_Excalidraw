import sympy as sp


def get_single_variable(eq):
    """
    Return the variable if the equation contains exactly one variable.

    Example:
        3x = -1
        -> x
    """

    variables = eq.lhs.free_symbols | eq.rhs.free_symbols

    if len(variables) != 1:
        return None

    return next(iter(variables))


def generate_next_step(eq):
    """
    Generate the next instructional algebra step
    for a simple one-variable linear equation.

    Examples:

        3x + 1 = 0
            ->
        subtract 1 from both sides

        3x = -1
            ->
        divide both sides by 3
    """

    x = get_single_variable(eq)

    if x is None:
        return {
            "valid": False,
            "reason": "Equation must contain exactly one variable.",
        }

    lhs = sp.expand(eq.lhs)
    rhs = sp.expand(eq.rhs)

    # --------------------------------------------------
    # Already solved:
    #
    # x = number
    # --------------------------------------------------

    if lhs == x and x not in rhs.free_symbols:
        return {
            "valid": True,
            "status": "solved",
            "operation": None,
            "value": None,
            "goal": None,
        }

    # --------------------------------------------------
    # MVP:
    # Handle equations where variable is on left side.
    #
    # ax + b = c
    # --------------------------------------------------

    coefficient = sp.simplify(lhs.coeff(x))
    constant = sp.simplify(lhs - coefficient * x)

    # Example:
    #
    # 3x + 1 = 0
    #
    # Remove constant first.
    if constant != 0:

        if constant > 0:
            return {
                "valid": True,
                "status": "needs_step",
                "operation": "subtract_both_sides",
                "value": constant,
                "goal": f"isolate the {x} term",
            }

        return {
            "valid": True,
            "status": "needs_step",
            "operation": "add_both_sides",
            "value": sp.simplify(-constant),
            "goal": f"isolate the {x} term",
        }

    # Example:
    #
    # 3x = -1
    #
    # Divide by coefficient.
    if coefficient != 1 and coefficient != 0:

        return {
            "valid": True,
            "status": "needs_step",
            "operation": "divide_both_sides",
            "value": coefficient,
            "goal": f"isolate {x}",
        }

    return {
        "valid": False,
        "reason": "No supported next step found.",
    }