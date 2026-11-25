"""Solve whiteboard problems: one equation of degree 1-6, or a system of equations.

    problem  = parse_problem(r"x^2-5x+6=0")              # LaTeX, one line or a system
    solution = solve_problem(problem)
    solution.steps         # what to write on the board, e.g. ["x^2-5x+6=0", "(x-2)(x-3)=0", "x=2", "x=3"]
    solution.explanations  # one short reason per step (for the chat)
    solution.answer        # "x = 2 or x = 3"
    solution.verified      # every answer substituted back into every original equation

Supported:
  * one variable, polynomial degree 1..6       (factoring, discriminant, numeric roots)
  * linear systems, 2..4 variables            (elimination, then back-substitution)
  * non-linear systems in 2 variables where one equation is linear (substitution),
    other small polynomial systems via SymPy  (answers only)

Only REAL solutions are reported. Irrational answers are written on the board as
decimals with "≈"; the exact form goes in the chat answer.

Board steps only use glyphs the canvas can draw: 0-9 x y z + - = ( ) / ^ . , ≈ Δ
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from math import gcd
from typing import Literal, Optional

import sympy as sp

from app.reasoning.problem_selection import UnsupportedMath, _parse_side, latex_to_text
from app.reasoning.linear_system import (
    LinearEquation, LinearSystem, solve_by_elimination, split_system,
)

MAX_DEGREE = 6
MAX_VARIABLES = 4
DECIMALS = 3
DRAWABLE_VARIABLES = {"x", "y", "z"}


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
@dataclass
class Problem:
    sources: list[str]                   # lines as written
    sides: list[tuple[sp.Expr, sp.Expr]]  # (lhs, rhs) as written
    variables: list[sp.Symbol]

    @property
    def zeros(self) -> list[sp.Expr]:
        """Each equation as expr = 0."""
        return [sp.expand(l - r) for l, r in self.sides]


def parse_problem(latex_or_lines) -> Problem:
    lines = split_system(latex_or_lines) if isinstance(latex_or_lines, str) else list(latex_or_lines)
    if not lines:
        raise UnsupportedMath("No equation found.")
    sources, sides = [], []
    for line in lines:
        text = latex_to_text(line)
        parts = text.split("=")
        if len(parts) != 2:
            raise UnsupportedMath(f"`{line}` needs exactly one '='.")
        lhs, rhs = (_parse_side(p) for p in parts)
        expr = sp.together(lhs - rhs)
        num, den = sp.fraction(expr)
        if den.free_symbols:
            raise UnsupportedMath("Variables in a denominator are not supported yet.")
        if not num.is_polynomial(*num.free_symbols):
            raise UnsupportedMath("Only polynomial equations are supported.")
        sources.append(line)
        sides.append((lhs, rhs))

    variables = sorted(set().union(*((l - r).free_symbols for l, r in sides)), key=str)
    if not variables:
        raise UnsupportedMath("The equation has no variable to solve for.")
    if len(variables) > MAX_VARIABLES:
        raise UnsupportedMath(f"At most {MAX_VARIABLES} variables are supported.")
    if not {str(v) for v in variables} <= DRAWABLE_VARIABLES:
        raise UnsupportedMath("Only the variables x, y and z can be written on the board.")
    if len(sides) == 1 and len(variables) > 1:
        raise UnsupportedMath("One equation with several variables has no single solution.")
    for l, r in sides:
        if sp.Poly(sp.expand(l - r), *variables).total_degree() > MAX_DEGREE:
            raise UnsupportedMath(f"Degree above {MAX_DEGREE} is not supported.")
    return Problem(sources, sides, variables)


# --------------------------------------------------------------------------- #
# Formatting for the board (compact, drawable glyphs only)
# --------------------------------------------------------------------------- #
def fmt(expr, order=None) -> str:
    """SymPy expression -> compact board text: 'x^2-5x+6', '(x-2)(x-3)', '3x/2'."""
    s = sp.sstr(expr, order=order).replace(" ", "").replace("**", "^")
    s = re.sub(r"\)\*\(", ")(", s)
    s = re.sub(r"(?<!\d)\*|\*(?!\d)", "", s)          # 5*x -> 5x, x*y -> xy, 2*(x+1) -> 2(x+1)
    return s


def fmt_num(value) -> str:
    value = sp.nsimplify(value) if not isinstance(value, sp.Float) else value
    if value.is_Rational:
        return fmt(value)
    return f"{float(value):.{DECIMALS}f}".rstrip("0").rstrip(".")


def is_exact_drawable(value) -> bool:
    return sp.nsimplify(value).is_Rational if not isinstance(value, sp.Float) else False


def poly_text(expr, var) -> str:
    """Highest power first: '-x^2+4', not '4-x^2'."""
    return fmt(sp.Poly(expr, var).as_expr(), order="lex")


# --------------------------------------------------------------------------- #
# Result
# --------------------------------------------------------------------------- #
@dataclass
class Solution:
    kind: Literal["solutions", "none", "all"]
    variables: list[str]
    solutions: list[dict[str, sp.Expr]] = field(default_factory=list)   # exact where possible
    steps: list[str] = field(default_factory=list)
    explanations: list[str] = field(default_factory=list)
    verified: bool = False
    note: str = ""          # e.g. "no real solutions (Δ < 0)"

    @property
    def approximate(self) -> bool:
        return any(not is_exact_drawable(v) for s in self.solutions for v in s.values())

    @property
    def answer(self) -> str:
        if self.kind == "none":
            return "no real solution" if "real" in self.note or not self.note else self.note
        if self.kind == "all":
            return "infinitely many solutions"

        def show(v):
            exact = sp.nsimplify(v) if not isinstance(v, sp.Float) else v
            if isinstance(exact, sp.Float):
                return f"≈{fmt_num(exact)}"
            if exact.is_Rational:
                return fmt(exact)
            return f"{sp.sstr(exact)} ≈ {fmt_num(exact)}"

        if len(self.variables) == 1:
            name = self.variables[0]
            parts = []
            for s in self.solutions:
                shown = show(s[name])
                parts.append(f"{name} ≈ {shown[1:]}" if shown.startswith("≈") else f"{name} = {shown}")
            return " or ".join(parts)
        names = ", ".join(self.variables)
        return " or ".join("(" + names + ") = (" + ", ".join(show(s[n]) for n in self.variables) + ")"
                           for s in self.solutions)


class _Steps:
    def __init__(self):
        self.steps, self.notes = [], []

    def add(self, step: str, note: str):
        if not self.steps or self.steps[-1] != step:
            self.steps.append(step)
            self.notes.append(note)


def _root_step(name: str, value) -> str:
    if is_exact_drawable(value):
        return f"{name}={fmt_num(value)}"
    return f"{name}≈{fmt_num(value)}"


def _verify(problem: Problem, solutions: list[dict[str, sp.Expr]]) -> bool:
    for sol in solutions:
        subs = {sp.Symbol(k): v for k, v in sol.items()}
        for zero in problem.zeros:
            value = zero.subs(subs)
            if isinstance(value, sp.Float) or any(isinstance(v, sp.Float) for v in sol.values()):
                if abs(complex(sp.N(value))) > 1e-6:
                    return False
            elif sp.simplify(value) != 0:
                return False
    return True


# --------------------------------------------------------------------------- #
# One variable: polynomial of degree 1..6
# --------------------------------------------------------------------------- #
def _real_roots_of(factor, var) -> list:
    """Real roots of one irreducible factor: exact for degree <= 2, numeric otherwise."""
    poly = sp.Poly(factor, var)
    if poly.degree() <= 2:
        return [r for r in sp.solve(factor, var) if r.is_real]
    return [sp.Float(complex(r).real) for r in poly.nroots(n=15) if abs(complex(r).imag) < 1e-9]


def solve_polynomial(problem: Problem, steps: Optional[_Steps] = None) -> Solution:
    var = problem.variables[0]
    name = str(var)
    s = steps or _Steps()
    lhs, rhs = problem.sides[0]
    zero = sp.expand(lhs - rhs)
    poly = sp.Poly(zero, var)
    degree = poly.degree()

    if degree <= 0:
        kind = "all" if zero == 0 else "none"
        s.add(f"{fmt(zero)}=0", "Simplify: the variable cancels out.")
        return Solution(kind, [name], [], s.steps, s.notes, True)

    if degree == 1:
        a, b = poly.coeff_monomial(var), poly.coeff_monomial(1)
        s.add(f"{fmt(a * var)}={fmt_num(-b)}", f"Move the {name} terms to one side and the numbers to the other.")
        root = sp.nsimplify(-b / a)
        s.add(f"{name}={fmt_num(root)}", f"Divide both sides by {fmt_num(a)}.")
        sols = [{name: root}]
        return Solution("solutions", [name], sols, s.steps, s.notes, _verify(problem, sols))

    s.add(f"{poly_text(zero, var)}=0", "Move every term to one side.")
    multiplier = sp.Integer(1)
    for c in sp.Poly(zero, var).all_coeffs():
        multiplier = sp.ilcm(multiplier, sp.fraction(sp.nsimplify(c))[1])
    if sp.Poly(zero, var).LC() < 0:
        multiplier = -multiplier
    if multiplier != 1:
        zero = sp.expand(zero * multiplier)
        s.add(f"{poly_text(zero, var)}=0", f"Multiply both sides by {fmt(multiplier)}.")
    coeff, factors = sp.factor_list(zero)
    factors = sorted(factors, key=lambda fm: _factor_order(fm[0], var))
    nontrivial = len(factors) > 1 or any(m > 1 for _, m in factors)
    roots: list = []

    if nontrivial:
        s.add(f"{_factored_text(coeff, factors, var)}=0", "Factor.")
        for factor, _ in factors:
            fdeg = sp.Poly(factor, var).degree()
            if fdeg == 1:
                r = sp.solve(factor, var)[0]
                s.add(_root_step(name, r), f"Set {fmt(factor)} = 0.")
                roots.append(r)
            elif fdeg == 2:
                roots.extend(_quadratic(factor, var, s, inside=True))
            else:
                found = _real_roots_of(factor, var)
                for r in found:
                    s.add(_root_step(name, r), f"{fmt(factor)} = 0 has no rational root; solved numerically.")
                roots.extend(found)
    elif degree == 2:
        roots = _quadratic(zero, var, s, inside=False)
    else:
        roots = _real_roots_of(zero, var)
        for r in roots:
            s.add(_root_step(name, r), "No rational roots; solved numerically.")

    unique = []
    for r in roots:
        if not any(sp.simplify(sp.N(r - u, 20)) == 0 or abs(complex(sp.N(r - u))) < 1e-9 for u in unique):
            unique.append(r)
    unique.sort(key=lambda r: float(sp.N(r)))
    sols = [{name: r} for r in unique]
    if not sols:
        return Solution("none", [name], [], s.steps, s.notes, True, note="no real solution")
    return Solution("solutions", [name], sols, s.steps, s.notes, _verify(problem, sols))


def _factor_order(factor, var):
    """Linear factors first, ordered by their root; then higher-degree factors."""
    p = sp.Poly(factor, var)
    if p.degree() == 1:
        return (0, float(-p.coeff_monomial(1) / p.coeff_monomial(var)))
    return (p.degree(), 0.0)


def _factored_text(coeff, factors, var) -> str:
    """2(x-2)(x-3), x(x-1)(x+1)(x^2+1), (x-2)^2."""
    prefix = "" if coeff == 1 else "-" if coeff == -1 else fmt(coeff)
    parts = []
    for factor, multiplicity in factors:
        text = poly_text(factor, var)
        part = text if factor == var else f"({text})"
        parts.append(part + (f"^{multiplicity}" if multiplicity > 1 else ""))
    return prefix + "".join(parts)


def _quadratic(expr, var, s: _Steps, inside: bool) -> list:
    """Quadratic that doesn't factor over the rationals: discriminant + formula."""
    name = str(var)
    p = sp.Poly(expr, var)
    a, b, c = (p.coeff_monomial(var ** 2), p.coeff_monomial(var), p.coeff_monomial(1))
    delta = sp.nsimplify(b ** 2 - 4 * a * c)
    s.add(f"Δ={fmt_num(delta)}",
          f"Discriminant of {poly_text(expr, var)}: Δ = b² − 4ac = ({fmt(b)})² − 4·({fmt(a)})·({fmt(c)}) = {fmt(delta)}.")
    if delta < 0:
        s.notes[-1] += f" Δ < 0, so {poly_text(expr, var)} = 0 has no real solution."
        return []
    roots = sorted(sp.solve(expr, var), key=lambda r: float(sp.N(r)))
    formula = f"{name} = (−b ± √Δ) / 2a = ({fmt(-b)} ± √{fmt(delta)}) / {fmt(2 * a)}"
    for r in roots:
        s.add(_root_step(name, r), formula + ".")
    return roots


# --------------------------------------------------------------------------- #
# Linear systems (any size)
# --------------------------------------------------------------------------- #
def _linear_rows(problem: Problem):
    rows = []
    for zero in problem.zeros:
        poly = sp.Poly(zero, *problem.variables)
        if poly.total_degree() > 1:
            return None
        coeffs = [Fraction(str(sp.nsimplify(poly.coeff_monomial(v)))) for v in problem.variables]
        const = Fraction(str(sp.nsimplify(-poly.coeff_monomial(1))))
        rows.append(coeffs + [const])
    return rows


def _row_text(row, names) -> str:
    expr = sum(sp.Rational(c.numerator, c.denominator) * sp.Symbol(n) for c, n in zip(row[:-1], names))
    rhs = sp.Rational(row[-1].numerator, row[-1].denominator)
    return f"{fmt(expr) if expr != 0 else '0'}={fmt(rhs)}"


def _integerize(row):
    den = 1
    for v in row:
        den = den * v.denominator // gcd(den, v.denominator)
    row = [v * den for v in row]
    g = 0
    for v in row:
        g = gcd(g, int(v))
    if g > 1:
        row = [v / g for v in row]
    first = next((v for v in row[:-1] if v != 0), 1)
    return [-v for v in row] if first < 0 else row


def solve_linear_system(problem: Problem) -> Optional[Solution]:
    rows = _linear_rows(problem)
    if rows is None:
        return None
    names = [str(v) for v in problem.variables]

    # Two equations, two unknowns: keep the nicer elimination steps.
    if len(rows) == 2 and len(names) == 2:
        system = LinearSystem(problem.variables[0], problem.variables[1],
                              *(LinearEquation(r[0], r[1], r[2], src) for r, src in zip(rows, problem.sources)))
        result = solve_by_elimination(system)
        sols = [{k: sp.Rational(v.numerator, v.denominator) for k, v in result.values.items()}] \
            if result.kind == "unique" else []
        kind = "solutions" if result.kind == "unique" else result.kind
        return Solution(kind, names, sols, result.steps, result.explanations,
                        result.verified and (not sols or _verify(problem, sols)))

    s = _Steps()
    for i, row in enumerate(rows, 1):
        s.add(_row_text(row, names), f"Equation ({i}) in standard form.")

    # Forward elimination, one variable at a time.
    remaining = [list(r) for r in rows]
    pivots = []          # (variable index, pivot row)
    for k in range(len(names)):
        with_k = [r for r in remaining if r[k] != 0]
        if not with_k:
            continue
        pivot = min(with_k, key=lambda r: (abs(r[k]) != 1, abs(r[k])))
        remaining.remove(pivot)
        reduced = []
        for r in remaining:
            if r[k] == 0:
                reduced.append(r)
                continue
            new = _integerize([r[i] * pivot[k] - pivot[i] * r[k] for i in range(len(r))])
            s.add(_row_text(new, names), f"Eliminate {names[k]} using {_row_text(pivot, names)}.")
            reduced.append(new)
        pivots.append((k, pivot))
        remaining = reduced

    for r in remaining:                      # leftover rows are 0 = c
        if all(c == 0 for c in r[:-1]):
            if r[-1] != 0:
                false_step = f"0={fmt(sp.Rational(r[-1].numerator, r[-1].denominator))}"
                if false_step in s.steps:
                    s.notes[s.steps.index(false_step)] += " Every variable cancels and the result is false."
                else:
                    s.add(false_step, "Every variable cancels and the result is false.")
                return Solution("none", names, [], s.steps, s.notes, True, note="no solution")
    if len(pivots) < len(names):
        return Solution("all", names, [], s.steps, s.notes, True)

    # Back-substitution, last pivot first.
    values: dict[int, Fraction] = {}
    for k, row in reversed(pivots):
        known = sum(row[i] * values[i] for i in values)
        values[k] = (row[-1] - known) / row[k]
        given = ", ".join(f"{names[i]} = {values[i]}" for i in sorted(values) if i != k)
        note = f"Substitute {given} into {_row_text(row, names)}." if given else f"Solve {_row_text(row, names)}."
        s.add(f"{names[k]}={fmt(sp.Rational(values[k].numerator, values[k].denominator))}", note)

    sol = {names[k]: sp.Rational(v.numerator, v.denominator) for k, v in values.items()}
    sols = [{n: sol[n] for n in names}]
    return Solution("solutions", names, sols, s.steps, s.notes, _verify(problem, sols))


# --------------------------------------------------------------------------- #
# Non-linear systems
# --------------------------------------------------------------------------- #
def solve_nonlinear_system(problem: Problem) -> Solution:
    names = [str(v) for v in problem.variables]
    s = _Steps()
    for i, (l, r) in enumerate(problem.sides, 1):
        s.add(f"{fmt(sp.expand(l))}={fmt(sp.expand(r))}", f"Equation ({i}).")

    # Substitution: an equation that is linear in some variable with a constant coefficient.
    if len(names) == 2 and len(problem.sides) == 2:
        options = []
        for i, zero in enumerate(problem.zeros):
            for var in problem.variables:
                if sp.Poly(zero, var).degree() != 1:
                    continue
                coeff = sp.Poly(zero, var).coeff_monomial(var)
                if coeff.free_symbols or coeff == 0:
                    continue
                # coefficient ±1 first (no fractions), then whole numbers, then the rest
                options.append(((abs(coeff) != 1, not coeff.is_integer), i, var))
        for _, i, var in sorted(options, key=lambda o: o[0]):
            zero = problem.zeros[i]
            if True:
                other_var = next(v for v in problem.variables if v != var)
                expr_for = sp.expand(sp.solve(zero, var)[0])
                s.add(f"{var}={fmt(expr_for)}", f"From equation ({i + 1}), write {var} in terms of {other_var}.")
                other = problem.zeros[1 - i]
                substituted = sp.expand(other.subs(var, expr_for))
                ol, orr = problem.sides[1 - i]
                shown = sp.UnevaluatedExpr(expr_for)
                s.add(f"{fmt(ol.subs(var, shown))}={fmt(orr.subs(var, shown))}",
                      f"Substitute {var} = {fmt(expr_for)} into equation ({2 - i}).")
                single = Problem([f"{fmt(substituted)}=0"], [(substituted, sp.Integer(0))], [other_var])
                inner = solve_polynomial(single, s)
                if inner.kind != "solutions":
                    return Solution(inner.kind, names, [], s.steps, s.notes, True, note=inner.note)
                sols = []
                for root in inner.solutions:     # already sorted smallest first
                    value = root[str(other_var)]
                    v_value = (sp.Float(sp.N(expr_for.subs(other_var, value))) if isinstance(value, sp.Float)
                               else sp.simplify(expr_for.subs(other_var, value)))
                    if is_exact_drawable(value) and is_exact_drawable(v_value):
                        # x=5-2=3: shows which y each x comes from
                        shown = fmt(expr_for.subs(other_var, sp.UnevaluatedExpr(value)))
                        s.add(f"{var}={shown}={fmt_num(v_value)}", f"Substitute {other_var} = {fmt_num(value)} back.")
                    else:
                        s.add(_root_step(str(var), v_value), f"Substitute {other_var} ≈ {fmt_num(value)} back.")
                    sols.append({str(var): v_value, str(other_var): value})
                sols = [{n: sol[n] for n in names} for sol in sols]
                if len(sols) > 1 and all(is_exact_drawable(v) for sol in sols for v in sol.values()):
                    for sol in sols:
                        s.add("(" + ",".join(fmt_num(sol[n]) for n in names) + ")",
                              f"Solution ({', '.join(names)}).")
                return Solution("solutions", names, sols, s.steps, s.notes, _verify(problem, sols))

    # General small polynomial systems: answers from SymPy, real only.
    found = sp.solve(problem.zeros, problem.variables, dict=True)
    sols = []
    for f in found:
        if len(f) != len(names) or not all(v.is_real for v in f.values()):
            continue
        sols.append({str(k): v for k, v in f.items()})
    if not sols:
        return Solution("none", names, [], s.steps, s.notes, True, note="no real solution")
    for sol in sols:
        for n in names:
            s.add(_root_step(n, sol[n]), "Solve the system.")
    sols = [{n: sol[n] for n in names} for sol in sols]
    return Solution("solutions", names, sols, s.steps, s.notes, _verify(problem, sols))


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def solve_problem(problem: Problem) -> Solution:
    if len(problem.sides) == 1:
        return solve_polynomial(problem)
    linear = solve_linear_system(problem)
    if linear is not None:
        return linear
    return solve_nonlinear_system(problem)


def describe_kind(problem: Problem) -> str:
    if len(problem.sides) == 1:
        degree = sp.Poly(problem.zeros[0], problem.variables[0]).degree()
        return {1: "linear equation", 2: "quadratic equation", 3: "cubic equation"}.get(
            degree, f"degree-{degree} equation")
    linear = _linear_rows(problem) is not None
    return f"{'linear' if linear else 'non-linear'} system of {len(problem.sides)} equations"