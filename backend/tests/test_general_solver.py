"""General solver: degree 1-6 equations, linear systems of any size, non-linear systems."""
import pytest
import sympy as sp

from app.reasoning.general_solver import describe_kind, fmt, parse_problem, solve_problem
from app.reasoning.problem_selection import UnsupportedMath
from app.services.question_solver import DRAWABLE


def solve(source):
    return solve_problem(parse_problem(source))


def values(solution, name="x"):
    return sorted(float(sp.N(s[name])) for s in solution.solutions)


@pytest.mark.parametrize("source,expected", [
    ("2x+3=11", [4]),
    ("x^2-5x+6=0", [2, 3]),
    ("x^2=4x-4", [2]),                                   # double root
    ("2x^2-10x+12=0", [2, 3]),
    (r"\frac{x^{2}}{2}-x-4=0", [-2, 4]),                 # fractions cleared first
    ("-x^2+4=0", [-2, 2]),
    ("x^3-6x^2+11x-6=0", [1, 2, 3]),
    ("x^4-5x^2+4=0", [-2, -1, 1, 2]),
    ("x^5-x=0", [-1, 0, 1]),                             # x^2+1 contributes no real root
    ("x(x-1)(x+2)=0", [-2, 0, 1]),
])
def test_exact_roots(source, expected):
    result = solve(source)
    assert result.kind == "solutions" and result.verified
    assert values(result) == expected
    assert not result.approximate


@pytest.mark.parametrize("source,expected", [
    ("x^2-3x-1=0", [-0.303, 3.303]),
    ("x^3-2=0", [1.26]),
    ("x^3+x+1=0", [-0.682]),
])
def test_irrational_roots_are_approximate(source, expected):
    result = solve(source)
    assert result.verified and result.approximate
    assert [round(v, 3) for v in values(result)] == expected
    answers = [step for step in result.steps if step.startswith(("x=", "x≈"))]
    assert answers and all(step.startswith("x≈") for step in answers)


def test_quadratic_steps():
    assert solve("x^2-5x+6=0").steps == ["x^2-5x+6=0", "(x-2)(x-3)=0", "x=2", "x=3"]
    steps = solve("x^2-3x-1=0").steps
    assert steps[:2] == ["x^2-3x-1=0", "Δ=13"] and steps[2:] == ["x≈-0.303", "x≈3.303"]


def test_no_real_solution():
    result = solve("x^2+x+1=0")
    assert result.kind == "none" and result.answer == "no real solution" and "Δ=-3" in result.steps


def test_linear_three_by_three():
    result = solve(["x+y+z=6", "2x-y+z=3", "x+2y-z=2"])
    assert result.verified and result.solutions == [{"x": 1, "y": 2, "z": 3}]
    assert result.answer == "(x, y, z) = (1, 2, 3)"
    assert result.steps[-3:] == ["z=3", "y=2", "x=1"]


def test_linear_systems_without_a_unique_solution():
    assert solve(["x+y+z=1", "x+y+z=2", "x-y=0"]).kind == "none"
    assert solve(["x+y+z=1", "2x+2y+2z=2", "x-y=0"]).kind == "all"


def test_two_by_two_keeps_elimination_steps():
    result = solve(["-2y+7x=5", "-3y+7x=4"])
    assert result.steps == ["7x-2y=5", "7x-3y=4", "y=1", "7x-2(1)=5", "7x-2=5", "7x=7", "x=1"]


def test_nonlinear_by_substitution():
    result = solve(["x+y=5", "xy=6"])
    assert result.verified and {(s["x"], s["y"]) for s in result.solutions} == {(2, 3), (3, 2)}
    assert "x=5-y" in result.steps and "y(5-y)=6" in result.steps
    assert "x=5-2=3" in result.steps and "(3,2)" in result.steps


def test_nonlinear_circle_and_line():
    result = solve(["x^2+y^2=25", "x+y=7"])
    assert {(s["x"], s["y"]) for s in result.solutions} == {(3, 4), (4, 3)} and result.verified


def test_nonlinear_with_irrational_answers():
    result = solve(["2x+y=3", "x^2+y=4"])
    assert result.verified and result.approximate and len(result.solutions) == 2
    assert "y=3-2x" in result.steps                     # substitutes the variable with coefficient 1


def test_every_step_can_be_drawn():
    for source in ["x^2-3x-1=0", "x^4-5x^2+4=0", ["x+y=5", "xy=6"], ["x+y+z=6", "2x-y+z=3", "x+2y-z=2"],
                   ["2x+y=3", "x^2+y=4"], "x^2+x+1=0", r"\frac{x^{2}}{2}-x-4=0"]:
        assert all(DRAWABLE.match(step) for step in solve(source).steps), source


def test_describe_kind():
    assert describe_kind(parse_problem("x^2=1")) == "quadratic equation"
    assert describe_kind(parse_problem(["x+y=1", "x-y=0"])) == "linear system of 2 equations"
    assert describe_kind(parse_problem(["x+y=1", "xy=0"])) == "non-linear system of 2 equations"


def test_fmt():
    x, y = sp.symbols("x y")
    assert fmt(x**2 - 5*x + 6) == "x^2-5x+6"
    assert fmt((x - 2) * (x - 3)) == "(x-3)(x-2)" or fmt((x - 2) * (x - 3)) == "(x-2)(x-3)"
    assert fmt(sp.Rational(3, 2) * x) == "3x/2"


@pytest.mark.parametrize("bad", [
    "x^7=1",                       # degree above 6
    "x+y=1",                       # one equation, two unknowns
    "a+b=1",                       # letters the canvas can't draw
    "1/x=2",                       # variable in a denominator
    "2=2",                         # nothing to solve for
    r"\sin(x)=1",
])
def test_rejects_unsupported(bad):
    with pytest.raises(UnsupportedMath):
        parse_problem(bad)