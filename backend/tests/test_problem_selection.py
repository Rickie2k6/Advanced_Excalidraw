"""Phase 1: which whiteboard problem to solve, and solving it. No LLM involved."""
import sympy as sp

from app.reasoning.problem_selection import (
    RecognizedEquation, classify, latex_to_text, select_problems, solve_chain,
)

_seq = iter(range(1, 10_000))


def eq(latex, row, col=0, *, source="human", status="done", deleted=False, eid=None, version=1):
    """An equation written on line `row` of column `col` (60 px per line, 400 px per column)."""
    n = next(_seq)
    return RecognizedEquation(eid or f"e{n}", latex, sequence=n, version=version, status=status,
                              source=source, deleted=deleted, x=col * 400, y=row * 60, width=200, height=40)


# ---------- selection ----------
def test_selects_newest_unsolved_problem():
    sel = select_problems([eq("2x + 3 = 11", 0), eq("x - 4 = 1", 0, col=1), eq("3x = 12", 0, col=2)])
    assert sel.status == "selected"
    assert sel.problems[0].original.latex == "3x = 12"


def test_steps_and_answers_are_never_new_problems():
    sel = select_problems([eq("2x + 3 = 11", 0), eq("2x = 8", 1), eq("x = 4", 2)])
    assert sel.status == "all_solved"
    assert len(sel.solved) == 1 and sel.solved[0].final_answer.latex == "x = 4"


def test_skips_solved_problem_and_picks_unsolved_one():
    sel = select_problems([eq("2x + 3 = 11", 0), eq("2x = 8", 1), eq("x = 4", 2),
                           eq("5x - 2 = 13", 4)])
    assert sel.status == "selected"
    assert sel.problems[0].original.latex == "5x - 2 = 13"
    assert [c.original.latex for c in sel.solved] == ["2x + 3 = 11"]


def test_all_solved_reports_answers():
    sel = select_problems([eq("2x + 3 = 11", 0), eq("x = 4", 1), eq("x - 1 = 2", 0, col=1), eq("x = 3", 1, col=1)])
    assert sel.status == "all_solved"
    assert "x = 4" in sel.message and "x = 3" in sel.message


def test_mode_all_returns_every_open_problem_newest_first():
    sel = select_problems([eq("2x = 6", 0), eq("x + 1 = 5", 0, col=1)], mode="all")
    assert [c.original.latex for c in sel.problems] == ["x + 1 = 5", "2x = 6"]


def test_same_answer_but_far_away_is_a_separate_problem():
    sel = select_problems([eq("2x + 3 = 11", 0), eq("x = 4", 1), eq("3x = 12", 0, col=1)])
    assert sel.status == "selected" and sel.problems[0].original.latex == "3x = 12"


# ---------- partially solved ----------
def test_partial_chain_continues_from_last_step():
    sel = select_problems([eq("5x - 2 = 13", 0), eq("5x = 15", 1)])
    chain = sel.problems[0]
    assert chain.status == "partial" and chain.continue_from.latex == "5x = 15"
    sol = solve_chain(chain)
    assert sol.existing_steps == ["5x - 2 = 13", "5x = 15"]
    assert sol.new_steps == ["x = 3"] and sol.verified


def test_wrong_middle_step_is_flagged_and_skipped():
    sel = select_problems([eq("5x - 2 = 13", 0), eq("5x = 11", 1)])
    chain = sel.problems[0]
    assert chain.status == "partial" and chain.continue_from.latex == "5x - 2 = 13"
    sol = solve_chain(chain)
    assert "5x = 11" in sol.wrong_steps[0] and sol.value == 3 and sol.verified


def test_wrong_final_answer_means_unsolved():
    sel = select_problems([eq("2x + 3 = 11", 0), eq("x = 5", 1)])
    assert sel.status == "selected" and sel.problems[0].status == "partial"
    assert solve_chain(sel.problems[0]).value == 4


# ---------- deleted, stale, agent content ----------
def test_deleted_elements_are_ignored():
    sel = select_problems([eq("2x = 6", 0), eq("x + 1 = 5", 0, col=1, deleted=True)])
    assert sel.problems[0].original.latex == "2x = 6"


def test_agent_content_completes_a_chain_but_never_starts_one():
    sel = select_problems([eq("2x = 6", 0), eq("x = 3", 1, source="agent"),
                           eq("7x = 14", 0, col=1, source="agent")])
    assert sel.status == "all_solved"


# ---------- pending, invalid, ambiguous ----------
def test_pending_recognition_waits():
    assert select_problems([eq("2x = 6", 0), eq("", 1, col=1, status="pending")]).status == "pending"


def test_failed_newest_recognition_asks_instead_of_using_older():
    sel = select_problems([eq("2x = 6", 0), eq("??", 0, col=1, status="failed")])
    assert sel.status == "needs_clarification"


def test_function_definition_asks_what_to_find():
    sel = select_problems([eq("y = 2x + 3", 0)])
    assert sel.status == "needs_clarification" and "function" in sel.message


def test_unsupported_newest_equation_asks():
    sel = select_problems([eq("2x = 6", 0), eq("x^2 = 4", 0, col=1)])
    assert sel.status == "needs_clarification" and "linear" in sel.message


def test_latex_commands_are_data_not_code():
    for bad in [r"\input{/etc/passwd} = 1", r"x.__class__ = 1", "__import__('os') = 1"]:
        assert classify(RecognizedEquation("e", bad, 1)).kind == "unsupported"


def test_latex_conversion():
    assert latex_to_text(r"\frac{x}{2} + 3 \cdot 2 = 7") == "((x)/(2)) + 3 * 2 = 7"
    assert classify(RecognizedEquation("e", r"\frac{x}{2} + 1 = 3", 1)).kind == "linear"


# ---------- solving ----------
def test_unique_solution_is_verified_by_substitution():
    sol = solve_chain(select_problems([eq("2x + 3 = 11", 0)]).problems[0])
    assert sol.kind == "unique" and sol.value == 4 and sol.verified
    assert sol.new_steps == ["2 x = 8", "x = 4"]


def test_no_solution():
    sol = solve_chain(select_problems([eq("2x + 1 = 2x + 5", 0)]).problems[0])
    assert sol.kind == "none" and sol.value is None and sol.verified


def test_infinitely_many_solutions():
    sol = solve_chain(select_problems([eq("2(x + 1) = 2x + 2", 0)]).problems[0])
    assert sol.kind == "all" and sol.verified


def test_fraction_answer():
    sol = solve_chain(select_problems([eq("3x = 2", 0)]).problems[0])
    assert sol.value == sp.Rational(2, 3) and sol.verified


def test_source_versions_are_captured():
    chain = select_problems([eq("5x - 2 = 13", 0, eid="a", version=3), eq("5x = 15", 1, eid="b", version=7)]).problems[0]
    assert chain.source_versions() == {"a": 3, "b": 7}