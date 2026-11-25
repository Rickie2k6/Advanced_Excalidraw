"""Solve a system of two linear equations in two variables by elimination.

    system = parse_system(r"\\begin{cases}-2y+7x=5\\\\-3y+7x=4\\end{cases}")
    result = solve_by_elimination(system)
    result.steps        # ["7x-2y=5", "7x-3y=4", "y=1", "7x-2(1)=5", "7x=7", "x=1"]
    result.explanations # one short reason per step, for the chat answer

Steps use the same compact style as math_agent.py ("7x-2y=5"). They need the
glyphs 0-9, x, y, +, -, =, ( ) and, for fractional answers, /.
LaTeX is converted with problem_selection.latex_to_text (whitelisted), so it is
treated as data and never executed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from math import lcm
from typing import Literal, Optional

import sympy as sp

from app.reasoning.problem_selection import UnsupportedMath, _parse_side, latex_to_text

ENVIRONMENTS = r"cases|array|aligned|align\*?|gathered|matrix"


@dataclass
class LinearEquation:
    """a*u + b*v = c"""
    a: Fraction
    b: Fraction
    c: Fraction
    source: str                 # the line as written


@dataclass
class LinearSystem:
    u: sp.Symbol                # first variable (alphabetical: x)
    v: sp.Symbol                # second variable (y)
    first: LinearEquation
    second: LinearEquation


@dataclass
class SystemSolution:
    kind: Literal["unique", "none", "all"]
    values: dict[str, Fraction] = field(default_factory=dict)   # {"x": 1, "y": 1}
    steps: list[str] = field(default_factory=list)
    explanations: list[str] = field(default_factory=list)
    verified: bool = False

    @property
    def answer(self) -> str:
        if self.kind == "none":
            return "no solution"
        if self.kind == "all":
            return "infinitely many solutions"
        names = list(self.values)
        return f"({', '.join(names)}) = ({', '.join(_num(self.values[n]) for n in names)})"


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def split_system(latex: str) -> list[str]:
    """Split a LaTeX system (cases/array/aligned or plain lines) into equation lines."""
    s = latex.strip().strip("$").strip()
    s = re.sub(rf"\\begin\{{(?:{ENVIRONMENTS})\}}(?:\{{[^{{}}]*\}})?", "", s)
    s = re.sub(rf"\\end\{{(?:{ENVIRONMENTS})\}}", "", s)
    s = re.sub(r"\\left\s*(?:\\\{|\.|\()", "", s)
    s = re.sub(r"\\right\s*(?:\\\}|\.|\))", "", s)
    s = s.replace("&", "")
    lines = [line.strip().strip("{}").strip() for line in re.split(r"\\\\|\n|;", s)]
    return [line for line in lines if line]


def _to_fraction(value: sp.Expr) -> Fraction:
    value = sp.nsimplify(value)
    if not value.is_Rational:
        raise UnsupportedMath("Only rational coefficients are supported.")
    return Fraction(int(value.p), int(value.q))


def parse_system(latex_or_lines) -> LinearSystem:
    lines = split_system(latex_or_lines) if isinstance(latex_or_lines, str) else list(latex_or_lines)
    if len(lines) != 2:
        raise UnsupportedMath(f"Expected a system of 2 equations, found {len(lines)}.")

    parsed = []
    for line in lines:
        text = latex_to_text(line)
        sides = text.split("=")
        if len(sides) != 2:
            raise UnsupportedMath(f"`{line}` needs exactly one '='.")
        lhs, rhs = (_parse_side(t) for t in sides)
        parsed.append((line, sp.expand(lhs - rhs)))

    symbols = sorted(set().union(*(e.free_symbols for _, e in parsed)), key=str)
    if len(symbols) != 2:
        raise UnsupportedMath("Expected exactly two variables, such as x and y.")
    u, v = symbols

    equations = []
    for line, expr in parsed:
        poly = sp.Poly(expr, u, v)
        if poly.total_degree() > 1:
            raise UnsupportedMath(f"`{line}` is not linear.")
        a, b = expr.coeff(u, 1).subs(v, 0), expr.coeff(v, 1).subs(u, 0)
        const = expr.subs({u: 0, v: 0})
        equations.append(LinearEquation(_to_fraction(a), _to_fraction(b), _to_fraction(-const), line))
    return LinearSystem(u, v, *equations)


# --------------------------------------------------------------------------- #
# Formatting (compact style used by math_agent.py)
# --------------------------------------------------------------------------- #
def _num(n: Fraction) -> str:
    return str(n.numerator) if n.denominator == 1 else f"{n.numerator}/{n.denominator}"


def _term(coef: Fraction, name: str, first: bool) -> str:
    if coef == 0:
        return ""
    sign = "-" if coef < 0 else ("" if first else "+")
    size = abs(coef)
    if size == 1:
        body = name
    elif size.denominator == 1:
        body = f"{size.numerator}{name}"
    else:
        body = f"({_num(size)}){name}"
    return sign + body


def _side(terms: list[tuple[Fraction, str]], constant: Fraction = Fraction(0)) -> str:
    out = ""
    for coef, name in terms:
        out += _term(coef, name, not out)
    if constant or not out:
        out += ("" if not out or constant < 0 else "+") + _num(constant)
    return out


def _eq(a: Fraction, b: Fraction, c: Fraction, u: str, v: str) -> str:
    return f"{_side([(a, u), (b, v)])}={_num(c)}"


# --------------------------------------------------------------------------- #
# Elimination
# --------------------------------------------------------------------------- #
def _scale_to_integers(eq: LinearEquation) -> int:
    return lcm(eq.a.denominator, eq.b.denominator, eq.c.denominator)


def _multipliers(p: Fraction, q: Fraction) -> tuple[int, int]:
    """Smallest positive integers m, n with |m*p| == |n*q|."""
    p, q = abs(int(p)), abs(int(q))
    common = lcm(p, q)
    return common // p, common // q


def solve_by_elimination(system: LinearSystem) -> SystemSolution:
    u, v = str(system.u), str(system.v)
    e1, e2 = system.first, system.second
    steps, notes = [], []

    def add(step: str, note: str):
        if not steps or steps[-1] != step:
            steps.append(step)
            notes.append(note)

    # 1. Write both equations in standard form a·x + b·y = c.
    for label, eq in (("(1)", e1), ("(2)", e2)):
        add(_eq(eq.a, eq.b, eq.c, u, v), f"Equation {label} in the form ax + by = c.")

    # 2. Clear fractions so the multipliers are whole numbers.
    rows = []
    for label, eq in (("(1)", e1), ("(2)", e2)):
        k = _scale_to_integers(eq)
        a, b, c = eq.a * k, eq.b * k, eq.c * k
        if k != 1:
            add(_eq(a, b, c, u, v), f"Multiply equation {label} by {k} to clear fractions.")
        rows.append([a, b, c])
    (a1, b1, c1), (a2, b2, c2) = rows

    # Degenerate systems (a variable missing from both equations) are handled by sympy below.
    candidates = []
    if a1 and a2:
        candidates.append(("u", *_multipliers(a1, a2)))
    if b1 and b2:
        candidates.append(("v", *_multipliers(b1, b2)))
    if not candidates:
        return _fallback(system, steps, notes)

    # 3. Eliminate the variable that needs the smallest multipliers (equal or opposite first).
    target, m, n = min(candidates, key=lambda t: (t[1] * t[2], t[0] != "v"))
    if m != 1:
        a1, b1, c1 = a1 * m, b1 * m, c1 * m
        add(_eq(a1, b1, c1, u, v), f"Multiply equation (1) by {m}.")
    if n != 1:
        a2, b2, c2 = a2 * n, b2 * n, c2 * n
        add(_eq(a2, b2, c2, u, v), f"Multiply equation (2) by {n}.")

    eliminated = (a1, a2) if target == "u" else (b1, b2)
    subtract = (eliminated[0] > 0) == (eliminated[1] > 0)
    sign = -1 if subtract else 1
    ra, rb, rc = a1 + sign * a2, b1 + sign * b2, c1 + sign * c2
    keep_name, keep_coef = (v, rb) if target == "u" else (u, ra)
    gone = u if target == "u" else v
    how = "Subtract equation (2) from equation (1)" if subtract else "Add the two equations"

    # 4. One equation, one variable.
    if keep_coef == 0:
        kind = "all" if rc == 0 else "none"
        add(f"0={_num(rc)}", f"{how}: both variables cancel.")
        return SystemSolution(kind, steps=steps, explanations=notes,
                              verified=_check_kind(system, kind))
    if keep_coef != 1:
        add(f"{_side([(keep_coef, keep_name)])}={_num(rc)}", f"{how} to eliminate {gone}.")
        add(f"{keep_name}={_num(rc / keep_coef)}", f"Divide both sides by {_num(keep_coef)}.")
    else:
        add(f"{keep_name}={_num(rc)}", f"{how} to eliminate {gone}.")
    known = rc / keep_coef

    # 5. Substitute back. Prefer equation (1), and an equation without fractions.
    def usable(eq):
        return (eq.a if target == "u" else eq.b) != 0

    def whole(eq):
        return all(n.denominator == 1 for n in (eq.a, eq.b, eq.c))

    base = min((e for e in (e1, e2) if usable(e)), key=lambda e: (not whole(e), e is not e1))
    label = "(1)" if base is e1 else "(2)"
    other_coef = base.a if target == "u" else base.b      # coefficient of the variable still unknown
    known_coef = base.b if target == "u" else base.a      # coefficient of the variable just found
    product = known_coef * known

    # Keep the written order of the equation: x term first, then y term.
    unknown_term = _term(other_coef, gone, True)
    if known_coef:
        size = "" if abs(known_coef) == 1 else _num(abs(known_coef))
        known_part = f"{size}({_num(known)})"
        if gone == u:      # x is unknown: 7x-2(1)
            substituted = unknown_term + ("-" if known_coef < 0 else "+") + known_part
            multiplied = _side([(other_coef, gone)], product)
        else:              # y is unknown: 8(2)-4y
            substituted = ("-" if known_coef < 0 else "") + known_part + _term(other_coef, gone, False)
            multiplied = _num(product) + _term(other_coef, gone, False)
    else:
        substituted = multiplied = unknown_term
    add(f"{substituted}={_num(base.c)}", f"Substitute {keep_name} = {_num(known)} into equation {label}.")
    if product:
        add(f"{multiplied}={_num(base.c)}", "Multiply.")

    def move_note():
        return (f"Subtract {_num(product)} from both sides." if product > 0
                else f"Add {_num(-product)} to both sides.")

    rest = base.c - product
    if other_coef != 1:
        if product:
            add(f"{_side([(other_coef, gone)])}={_num(rest)}", move_note())
        add(f"{gone}={_num(rest / other_coef)}", f"Divide both sides by {_num(other_coef)}.")
    else:
        add(f"{gone}={_num(rest)}", move_note() if product else "Simplify.")
    other_value = rest / other_coef

    values = {gone: other_value, keep_name: known}
    values = {u: values[u], v: values[v]}
    return SystemSolution("unique", values, steps, notes, _check_unique(system, values))


def _fallback(system: LinearSystem, steps, notes) -> SystemSolution:
    sol = sp.linsolve([sp.Eq(e.a * system.u + e.b * system.v, e.c) for e in (system.first, system.second)],
                      system.u, system.v)
    if not sol:
        return SystemSolution("none", steps=steps, explanations=notes, verified=True)
    (pair,) = sol
    if any(p.free_symbols for p in pair):
        return SystemSolution("all", steps=steps, explanations=notes, verified=True)
    values = {str(system.u): _to_fraction(pair[0]), str(system.v): _to_fraction(pair[1])}
    for name, val in values.items():
        steps.append(f"{name}={_num(val)}")
        notes.append("Solve.")
    return SystemSolution("unique", values, steps, notes, _check_unique(system, values))


def _check_unique(system: LinearSystem, values: dict[str, Fraction]) -> bool:
    """Substitute the answer into BOTH original equations."""
    x, y = values[str(system.u)], values[str(system.v)]
    return all(e.a * x + e.b * y == e.c for e in (system.first, system.second))


def _check_kind(system: LinearSystem, kind: str) -> bool:
    sol = sp.linsolve([sp.Eq(e.a * system.u + e.b * system.v, e.c) for e in (system.first, system.second)],
                      system.u, system.v)
    if kind == "none":
        return not sol
    return bool(sol) and any(p.free_symbols for p in next(iter(sol)))