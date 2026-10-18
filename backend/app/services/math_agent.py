
"""Small, deterministic first version of Talk_Sketch's equation solver.

Supports one-variable linear equations with integer coefficients and an
integer solution. The generated steps use only glyphs currently supported by
math-freedraw.ts (digits, x, +, -, =).
"""

import re
from sympy import Eq, Integer, Symbol, solve, simplify

x = Symbol('x')
_TERM = re.compile(r'[+-]?(?:\d*x|\d+)\Z')


def _parse_side(side: str):
    compact = re.sub(r'\s+', '', side).replace('−', '-')
    if not compact:
        raise ValueError('Missing equation side')
    terms = re.findall(r'[+-]?[^+-]+', compact)
    if ''.join(terms) != compact or not all(_TERM.fullmatch(t) for t in terms):
        raise ValueError('Only linear equations with integer coefficients are supported')
    a = b = 0
    for term in terms:
        sign = -1 if term.startswith('-') else 1
        unsigned = term.lstrip('+-')
        if unsigned.endswith('x'):
            digits = unsigned[:-1]
            a += sign * (int(digits) if digits else 1)
        else:
            b += sign * int(unsigned)
    return a, b


def _side(a: int, b: int) -> str:
    parts = []
    if a:
        parts.append(('' if a > 0 else '-') + (str(abs(a)) if abs(a) != 1 else '') + 'x')
    if b:
        parts.append(('+' if b > 0 and parts else '') + str(b))
    return ''.join(parts) or '0'


def solve_linear_steps(expression: str) -> dict:
    """Return a validated write_math_steps action or raise ValueError."""
    compact = re.sub(r'\s+', '', expression).replace('−', '-')
    if compact.count('=') != 1:
        raise ValueError('Provide one equation containing =')
    left, right = compact.split('=')
    a, b = _parse_side(left)
    c, d = _parse_side(right)
    coefficient = a - c
    rhs = d - b
    if coefficient == 0:
        raise ValueError('Equation has no unique solution')
    solutions = solve(Eq(a*x+b, c*x+d), x)
    if len(solutions) != 1 or not solutions[0].is_Rational:
        raise ValueError(
            "This version only supports rational solutions"
        )

    solution = solutions[0]
    steps = [f'{_side(a,b)}={_side(c,d)}']
    middle = f'{_side(coefficient,0)}={rhs}'
    if middle != steps[-1]:
        steps.append(middle)
    if solution.q == 1:
        last = f"x={solution.p}"
    else:
        last = f"x={solution.p}/{solution.q}"
    if last != steps[-1]:
        steps.append(last)
    for step in steps:
        lhs, rhs_text = step.split("=")

        if step == last and solution.q != 1:
            if simplify(
                solution - (Integer(solution.p) / Integer(solution.q))
            ) != 0:
                raise ValueError(
                    "Internal step verification failed"
                )
            continue

        la, lb = _parse_side(lhs)
        ra, rb = _parse_side(rhs_text)

        if simplify(
            (la - ra) * solution + lb - rb
        ) != 0:
            raise ValueError(
                "Internal step verification failed"
            )
    return {'action': 'write_math_steps', 'steps': steps}
