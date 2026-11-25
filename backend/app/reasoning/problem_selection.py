"""Choose which whiteboard problem to solve, and solve it with SymPy.

Phase 1 of docs/multi_agent_spec.md. Pure logic, no LLM and no I/O:

    records  = [...RecognizedEquation from the recognition pipeline...]
    result   = select_problems(records)              # which problem(s) to work on
    solution = solve_chain(result.problems[0])      # steps to write + verified answer

Rules implemented:
  * Equations are grouped into problem chains. An equation written just below a
    chain and with the same solution set is a solution step; a final answer is
    the variable isolated (x = 4).
  * Solved problems (chain contains a correct final answer) are skipped.
  * Partially solved problems are continued from the last correct step; wrong
    steps are reported, never continued from.
  * Steps and final answers are never selected as new problems. Content written
    by agents can complete a chain but never starts a new problem.
  * The newest human content must be understood; otherwise ask instead of
    silently solving an older problem.
  * LaTeX is treated as data: it is converted with a whitelist before SymPy
    parses it, so embedded commands are never executed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Optional

import sympy as sp
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

# --------------------------------------------------------------------------- #
# Input from the recognition pipeline
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RecognizedEquation:
    """One recognition result for one scene element (or group of elements)."""
    element_id: str
    latex: str
    sequence: int                   # recognition order: larger = newer
    version: int = 0                # Excalidraw element version when recognized
    status: str = "done"            # "done" | "pending" | "failed"
    source: str = "human"           # "human" | "agent" (from element customData)
    deleted: bool = False
    x: Optional[float] = None       # scene bounding box, if known
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None

    @property
    def has_box(self) -> bool:
        return None not in (self.x, self.y, self.width, self.height)


# --------------------------------------------------------------------------- #
# Safe LaTeX -> SymPy
# --------------------------------------------------------------------------- #
class UnsupportedMath(ValueError):
    """The LaTeX is valid data but not something this solver supports."""


_ALLOWED = re.compile(r"^[0-9A-Za-z+\-*/().= ]*$")
_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_LOCALS = {c: sp.Symbol(c) for c in _LETTERS}   # stops E, I, S, N... becoming SymPy objects
_GLOBALS = {"Integer": sp.Integer, "Float": sp.Float, "Rational": sp.Rational, "Symbol": sp.Symbol}
_TRANSFORMS = standard_transformations + (implicit_multiplication_application,)


def _replace_frac(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        m = re.match(r"\\[dt]?frac", s[i:])
        if not m:
            out.append(s[i]); i += 1; continue
        i += m.end()
        parts = []
        for _ in range(2):
            if i >= len(s) or s[i] != "{":
                raise UnsupportedMath("Malformed fraction.")
            depth, j = 0, i
            while j < len(s):
                depth += {"{": 1, "}": -1}.get(s[j], 0)
                if depth == 0:
                    break
                j += 1
            if depth:
                raise UnsupportedMath("Unbalanced braces.")
            parts.append(_replace_frac(s[i + 1:j]))
            i = j + 1
        out.append(f"(({parts[0]})/({parts[1]}))")
    return "".join(out)


def latex_to_text(latex: str) -> str:
    s = latex.strip().strip("$").strip()
    s = s.replace("\u2212", "-").replace("\u00d7", "*").replace("\u00b7", "*").replace("\u00f7", "/")
    s = re.sub(r"\\(displaystyle|textstyle)\s*", "", s)
    s = re.sub(r"\\(mathrm|mathit|mathbf|boldsymbol)\s*\{([^{}]*)\}", r"\2", s)
    s = re.sub(r"\\(left|right)\s*", "", s)
    s = re.sub(r"\\[,;:! ]|~", " ", s)
    s = re.sub(r"\\(cdot|times)", "*", s)
    s = s.replace("\\div", "/")
    s = _replace_frac(s)
    s = re.sub(r"\^\{([^{}]*)\}", r"**(\1)", s)
    s = s.replace("^", "**").replace("{", "(").replace("}", ")")
    if "\\" in s:
        raise UnsupportedMath("Contains LaTeX commands this solver does not support.")
    if not _ALLOWED.match(s.replace("**", "*")):
        raise UnsupportedMath("Contains symbols this solver does not support.")
    if re.search(r"(?<!\d)\.|\.(?!\d)", s):
        raise UnsupportedMath("Unexpected '.'.")
    s = re.sub(r"(?<=[A-Za-z])(?=[A-Za-z])", "*", s)    # xy -> x*y, every name is one letter
    return s


def _parse_side(text: str) -> sp.Expr:
    if not text.strip():
        raise UnsupportedMath("One side of the equation is empty.")
    try:
        return parse_expr(text, local_dict=dict(_LOCALS), global_dict=dict(_GLOBALS),
                          transformations=_TRANSFORMS, evaluate=True)
    except Exception:
        raise UnsupportedMath("Could not read this expression.")


# --------------------------------------------------------------------------- #
# Classified equations
# --------------------------------------------------------------------------- #
Kind = Literal["linear", "constant", "function", "unsupported"]
SolutionSet = tuple   # ("unique", value) | ("none",) | ("all",)


@dataclass
class Equation:
    record: RecognizedEquation
    kind: Kind
    lhs: Optional[sp.Expr] = None
    rhs: Optional[sp.Expr] = None
    var: Optional[sp.Symbol] = None
    reason: str = ""

    @property
    def latex(self) -> str:
        return self.record.latex


def classify(record: RecognizedEquation) -> Equation:
    try:
        text = latex_to_text(record.latex)
        sides = text.split("=")
        if len(sides) != 2:
            raise UnsupportedMath("Expected exactly one '='.")
        lhs, rhs = (_parse_side(t) for t in sides)
    except UnsupportedMath as e:
        return Equation(record, "unsupported", reason=str(e))

    symbols = sorted((lhs - rhs).free_symbols | lhs.free_symbols | rhs.free_symbols, key=str)
    if not symbols:
        return Equation(record, "constant", lhs, rhs)
    if len(symbols) == 2 and (lhs in symbols or rhs in symbols):
        return Equation(record, "function", lhs, rhs,
                        reason="This looks like a function definition, not an equation to solve.")
    if len(symbols) > 1:
        return Equation(record, "unsupported", lhs, rhs,
                        reason="Only single-variable equations are supported.")
    var = symbols[0]
    expr = sp.together(sp.expand(lhs - rhs))
    num, den = sp.fraction(expr)
    if var in den.free_symbols or not sp.Poly(num, var).degree() <= 1:
        return Equation(record, "unsupported", lhs, rhs, var,
                        reason="Only linear equations are supported.")
    return Equation(record, "linear", lhs, rhs, var)


def solution_set(eq: Equation, var: sp.Symbol) -> SolutionSet:
    """Solution set of `eq` in `var`. Constant equations are all/none."""
    expr = sp.expand(eq.lhs - eq.rhs)
    a, b = expr.coeff(var, 1), expr.coeff(var, 0)
    if a != 0:
        return ("unique", sp.nsimplify(-b / a))
    return ("all",) if sp.simplify(b) == 0 else ("none",)


def is_final_answer(eq: Equation, var: sp.Symbol) -> bool:
    """x = 4, 4 = x, or a constant equation (0 = 5, 0 = 0) closing a no/all chain."""
    if eq.kind == "constant":
        return True
    return eq.kind == "linear" and (
        (eq.lhs == var and not eq.rhs.free_symbols) or (eq.rhs == var and not eq.lhs.free_symbols)
    )


def _near_below(new: RecognizedEquation, last: RecognizedEquation) -> bool:
    """`new` sits just below `last` and roughly in the same column."""
    if not (new.has_box and last.has_box):
        return True    # no layout data: rely on maths only
    gap = new.y - (last.y + last.height)
    line = max(last.height, new.height)
    starts_below = new.y > last.y + 0.5 * last.height
    overlaps = new.x < last.x + 1.5 * last.width and new.x + new.width > last.x - 0.5 * last.width
    return starts_below and gap <= 2.5 * line and overlaps


# --------------------------------------------------------------------------- #
# Problem chains
# --------------------------------------------------------------------------- #
ChainStatus = Literal["unsolved", "partial", "solved"]


@dataclass
class WrongStep:
    equation: Equation
    explanation: str


@dataclass
class ProblemChain:
    original: Equation
    steps: list[Equation] = field(default_factory=list)
    status: ChainStatus = "unsolved"
    wrong_steps: list[WrongStep] = field(default_factory=list)
    continue_from: Optional[Equation] = None     # last correct equation in the chain
    final_answer: Optional[Equation] = None      # correct final answer, if solved on the board
    agent_answer: Optional[str] = None           # answer an agent wrote in an earlier task

    @property
    def answer_text(self) -> str:
        return self.final_answer.latex if self.final_answer else (self.agent_answer or "")

    @property
    def problem_id(self) -> str:
        return self.original.record.element_id

    @property
    def var(self) -> sp.Symbol:
        return self.original.var

    @property
    def last(self) -> Equation:
        return self.steps[-1] if self.steps else self.original

    @property
    def newest_sequence(self) -> int:
        return max(e.record.sequence for e in [self.original, *self.steps])

    def source_versions(self) -> dict[str, int]:
        """Element IDs and versions to capture with the task (source-changed check)."""
        return {e.record.element_id: e.record.version for e in [self.original, *self.steps]}


def _describe(s: SolutionSet, var) -> str:
    if s[0] == "unique":
        return f"{var} = {s[1]}"
    return "no solution" if s[0] == "none" else "infinitely many solutions"


def _analyse(chain: ProblemChain) -> None:
    var, target = chain.var, solution_set(chain.original, chain.var)
    chain.continue_from = chain.original
    for step in chain.steps:
        got = solution_set(step, var)
        if got == target:
            if not chain.wrong_steps:
                chain.continue_from = step
            if is_final_answer(step, var) and chain.final_answer is None:
                chain.final_answer = step
        else:
            chain.wrong_steps.append(WrongStep(step,
                f"`{step.latex}` gives {_describe(got, var)}, but `{chain.original.latex}` "
                f"gives {_describe(target, var)}."))
    if is_final_answer(chain.original, var):
        chain.final_answer = chain.original
    if chain.final_answer is not None:
        chain.status = "solved"      # wrong steps, if any, are still reported
    else:
        chain.status = "partial" if chain.steps else "unsolved"


def _same_problem(eq: Equation, chain: ProblemChain) -> bool:
    return solution_set(eq, chain.var) == solution_set(chain.original, chain.var)


def _closed(chain: ProblemChain) -> bool:
    """The chain already ends in a correct final answer."""
    return any(is_final_answer(e, chain.var) and _same_problem(e, chain)
               for e in [chain.original, *chain.steps])


def build_chains(equations: list[Equation]) -> list[ProblemChain]:
    """Group usable equations (ordered by sequence) into problem chains.

    With layout data, an equation just below a chain belongs to it, even when it
    is wrong (that is how wrong steps are found). Without layout data, only an
    equivalent equation joins a chain. A chain that already has a correct final
    answer only accepts equivalent equations, so a new problem written under a
    finished one starts a new chain.
    """
    chains: list[ProblemChain] = []
    for eq in equations:
        home = None
        for chain in sorted(chains, key=lambda c: c.newest_sequence, reverse=True):
            if eq.var not in (None, chain.var):
                continue
            has_layout = eq.record.has_box and chain.last.record.has_box
            if _closed(chain) or not has_layout:
                fits = _same_problem(eq, chain) and (not has_layout or _near_below(eq.record, chain.last.record))
            else:
                fits = _near_below(eq.record, chain.last.record)
            if fits:
                home = chain
                break
        if home is not None:
            home.steps.append(eq)
        elif eq.kind == "linear" and eq.record.source == "human":
            chains.append(ProblemChain(original=eq))
        # agent-written or stray constant equations never start a problem
    for chain in chains:
        _analyse(chain)
    return chains


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #
SelectionStatus = Literal["selected", "all_solved", "pending", "needs_clarification", "nothing_found"]


@dataclass
class Selection:
    status: SelectionStatus
    problems: list[ProblemChain] = field(default_factory=list)   # to solve, newest first
    solved: list[ProblemChain] = field(default_factory=list)     # skipped, already solved
    message: str = ""
    unclear: Optional[RecognizedEquation] = None


def select_problems(records: list[RecognizedEquation], mode: Literal["newest", "all"] = "newest",
                    solved_by_agent: Optional[dict[str, dict]] = None) -> Selection:
    """`solved_by_agent` maps equation_id -> {"latex": ..., "answer": ...} for problems an
    agent already solved. Agent output may not be recognized from the board, so this
    ledger is what stops the same problem being solved again."""
    solved_by_agent = solved_by_agent or {}
    live = [r for r in records if not r.deleted]
    if any(r.status == "pending" for r in live):
        return Selection("pending", message="New whiteboard content is still being recognized.")

    ordered = sorted((r for r in live if r.status == "done"), key=lambda r: r.sequence)
    equations = [classify(r) for r in ordered]

    newest_human = max((r for r in live if r.source == "human"), key=lambda r: r.sequence, default=None)
    if newest_human is not None:
        if newest_human.status == "failed":
            return Selection("needs_clarification", unclear=newest_human,
                             message="The newest writing on the board could not be recognized. Please rewrite it or tell me which equation to solve.")
        newest_eq = next(e for e in equations if e.record is newest_human)
        if newest_eq.kind == "function":
            return Selection("needs_clarification", unclear=newest_human,
                             message=f"`{newest_eq.latex}` is a function definition. What should I find (for example, x when y = 11)?")
        if newest_eq.kind == "unsupported":
            return Selection("needs_clarification", unclear=newest_human,
                             message=f"I can't solve `{newest_eq.latex}`: {newest_eq.reason} Which equation should I solve?")

    chains = build_chains([e for e in equations if e.kind in ("linear", "constant")])
    for chain in chains:
        entry = solved_by_agent.get(chain.problem_id)
        if entry and entry.get("latex") == chain.original.latex and chain.status != "solved":
            chain.status, chain.agent_answer = "solved", entry.get("answer", "")
    if not chains:
        return Selection("nothing_found", message="I couldn't find a linear equation on the whiteboard.")

    open_chains = sorted((c for c in chains if c.status != "solved"),
                         key=lambda c: c.newest_sequence, reverse=True)
    solved = [c for c in chains if c.status == "solved"]
    if not open_chains:
        listed = "; ".join(f"`{c.original.latex}` → `{c.answer_text}`" for c in solved)
        return Selection("all_solved", solved=solved,
                         message=f"Every equation on the board is already solved: {listed}.")
    picked = open_chains if mode == "all" else open_chains[:1]
    return Selection("selected", problems=picked, solved=solved)


# --------------------------------------------------------------------------- #
# Solving
# --------------------------------------------------------------------------- #
@dataclass
class Solution:
    problem_id: str
    original_latex: str
    kind: Literal["unique", "none", "all"]
    value: Optional[sp.Expr]
    existing_steps: list[str]        # already on the board and correct
    new_steps: list[str]             # what the agent should write, in order
    verified: bool
    wrong_steps: list[str]           # explanations to show the human


def _eq_latex(lhs, rhs) -> str:
    return f"{sp.latex(lhs)} = {sp.latex(rhs)}"


def solve_chain(chain: ProblemChain) -> Solution:
    var, start = chain.var, chain.continue_from or chain.original
    wrong = {id(w.equation) for w in chain.wrong_steps}
    upto = chain.steps.index(start) + 1 if start in chain.steps else 0
    existing = [chain.original.latex] + [e.latex for e in chain.steps[:upto] if id(e) not in wrong]

    l, r = sp.expand(start.lhs), sp.expand(start.rhs)
    a1, b1 = l.coeff(var, 1), l.coeff(var, 0)
    a2, b2 = r.coeff(var, 1), r.coeff(var, 0)
    a, b = sp.nsimplify(a1 - a2), sp.nsimplify(b2 - b1)

    candidates = []
    if (l, r) != (start.lhs, start.rhs):
        candidates.append((l, r))                          # expand brackets
    candidates.append((a * var, b))                        # collect x terms left, numbers right
    if a != 0:
        value = sp.nsimplify(b / a)
        candidates.append((var, value))
        kind = "unique"
    else:
        value = None
        kind = "all" if b == 0 else "none"

    steps, previous = [], (start.lhs, start.rhs)
    for lhs, rhs in candidates:
        if sp.simplify(lhs - previous[0]) == 0 and sp.simplify(rhs - previous[1]) == 0:
            continue
        steps.append(_eq_latex(lhs, rhs))
        previous = (lhs, rhs)

    if kind == "unique":   # substitution check against the ORIGINAL problem
        o = chain.original
        verified = sp.simplify(o.lhs.subs(var, value) - o.rhs.subs(var, value)) == 0
    else:
        verified = solution_set(chain.original, var) == ((kind,))

    return Solution(chain.problem_id, chain.original.latex, kind, value, existing, steps,
                    bool(verified), [w.explanation for w in chain.wrong_steps])