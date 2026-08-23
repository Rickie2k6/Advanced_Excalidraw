import sympy as sp


def format_value(value):
    """
    Convert SymPy values to readable text.

    Examples:
        Integer(3) -> "3"
        Rational(1, 3) -> "1/3"
    """

    if isinstance(value, sp.Basic):
        return str(value)

    return str(value)


def generate_instruction(next_step):
    """
    Convert a verified mathematical operation
    into a short tutoring instruction.

    This function does NOT solve the equation.
    """

    if not next_step:
        return None

    if not next_step.get("valid"):
        return None

    status = next_step.get("status")

    if status == "solved":
        return "This equation is already solved."

    operation = next_step.get("operation")
    value = next_step.get("value")
    goal = next_step.get("goal")

    value_text = format_value(value)

    if operation == "subtract_both_sides":
        return (
            f"Subtract {value_text} from both sides "
            f"to {goal}."
        )

    if operation == "add_both_sides":
        return (
            f"Add {value_text} to both sides "
            f"to {goal}."
        )

    if operation == "divide_both_sides":
        return (
            f"Divide both sides by {value_text} "
            f"to {goal}."
        )

    if operation == "multiply_both_sides":
        return (
            f"Multiply both sides by {value_text} "
            f"to {goal}."
        )

    return "Think about what operation would isolate the variable."