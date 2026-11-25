"""Connect the whiteboard recognition pipeline to problem selection.

equations.json (written by api/routes/equations.py)
    -> RecognizedEquation records
    -> reasoning/problem_selection.select_problems()

Also keeps a small ledger (data/agent_solutions.json) of problems agents have
already solved, because agent output on the canvas may not be recognized as
handwriting and would otherwise look unsolved.

Limitation: equations.json is one file for the whole server, not per room, so
problems are not isolated between whiteboard sessions yet.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from app.reasoning.problem_selection import (
    RecognizedEquation, Selection, Solution, select_problems, solve_chain,
)

RECOGNITION_WAIT_SECONDS = 20
POLL_SECONDS = 1.0


def _default_equations_file() -> Path:
    # Imported lazily: the equations route pulls in PaddleOCR.
    from app.api.routes.equations import EQUATIONS_FILE
    return EQUATIONS_FILE


def _ledger_file(equations_file: Path) -> Path:
    return equations_file.parent / "agent_solutions.json"


def _read_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


# --------------------------------------------------------------------------- #
# equations.json -> RecognizedEquation
# --------------------------------------------------------------------------- #
def load_recognized_equations(equations_file: Optional[Path] = None) -> list[RecognizedEquation]:
    path = equations_file or _default_equations_file()
    records = _read_json(path, {"equations": {}}).get("equations", {})
    if isinstance(records, list):          # older list format
        records = {r.get("equation_id", str(i)): r for i, r in enumerate(records)}

    # Recognized records from before `sequence` existed: ordered by time, before all new ones.
    # Not-yet-recognized (pending/failed) records: treated as the newest content on the board.
    def _time(r):
        return r.get("recognized_at") or r.get("updated_at") or ""

    no_seq = [r for r in records.values() if r.get("sequence") is None]
    legacy = sorted((r for r in no_seq if (r.get("equation") or "").strip()
                     and r.get("ocr_status") != "failed"), key=_time)
    unrecognized = sorted((r for r in no_seq if r not in legacy), key=_time)
    top = max((r["sequence"] for r in records.values() if r.get("sequence") is not None), default=0)
    fallback_seq = {id(r): i - len(legacy) for i, r in enumerate(legacy)}
    fallback_seq.update({id(r): top + 1 + i for i, r in enumerate(unrecognized)})

    result = []
    for equation_id, r in records.items():
        latex = (r.get("equation") or "").strip()
        if r.get("ocr_status") == "failed":
            status = "failed"
        elif latex:
            status = "done"
        else:
            status = "pending"
        bbox = r.get("bbox") or {}
        result.append(RecognizedEquation(
            element_id=r.get("equation_id", equation_id),
            latex=latex,
            sequence=r["sequence"] if r.get("sequence") is not None else fallback_seq[id(r)],
            version=0,   # the equation ID already changes whenever its strokes change
            status=status,
            source="agent" if r.get("source") == "agent" else "human",
            x=bbox.get("x"), y=bbox.get("y"), width=bbox.get("width"), height=bbox.get("height"),
        ))
    return result


# --------------------------------------------------------------------------- #
# Ledger of agent-solved problems
# --------------------------------------------------------------------------- #
def load_solved_ledger(equations_file: Optional[Path] = None) -> dict[str, dict]:
    path = _ledger_file(equations_file or _default_equations_file())
    return _read_json(path, {"solved": {}}).get("solved", {})


def record_agent_solution(solution: Solution, task_id: str,
                          equations_file: Optional[Path] = None) -> None:
    """Call only after the canvas confirmed the solution was written."""
    path = _ledger_file(equations_file or _default_equations_file())
    data = _read_json(path, {"solved": {}})
    answer = {"unique": f"x = {solution.value}", "none": "no solution",
              "all": "infinitely many solutions"}[solution.kind]
    if solution.new_steps and solution.kind == "unique":
        answer = solution.new_steps[-1]
    data.setdefault("solved", {})[solution.problem_id] = {
        "latex": solution.original_latex,
        "answer": answer,
        "task_id": task_id,
        "solved_at": datetime.now(timezone.utc).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


# --------------------------------------------------------------------------- #
# Main entry point for agents
# --------------------------------------------------------------------------- #
async def find_problem_to_solve(mode: Literal["newest", "all"] = "newest",
                                equations_file: Optional[Path] = None,
                                wait_seconds: float = RECOGNITION_WAIT_SECONDS) -> Selection:
    """Wait for recognition to finish (up to `wait_seconds`), then select.

    If recognition is still pending after the wait, those records are treated as
    failed: if one is the newest content, the human is asked; older ones are ignored.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + wait_seconds
    while True:
        records = load_recognized_equations(equations_file)
        ledger = load_solved_ledger(equations_file)
        selection = select_problems(records, mode, solved_by_agent=ledger)
        if selection.status != "pending":
            return selection
        if loop.time() >= deadline:
            timed_out = [
                RecognizedEquation(**{**r.__dict__, "status": "failed"}) if r.status == "pending" else r
                for r in records
            ]
            result = select_problems(timed_out, mode, solved_by_agent=ledger)
            if result.status == "needs_clarification":
                result.message = ("Part of the board is still being recognized after "
                                  f"{int(wait_seconds)} seconds. " + result.message)
            return result
        await asyncio.sleep(POLL_SECONDS)


def describe_selection(selection: Selection) -> dict:
    """JSON-safe summary (used by the preview endpoint and later by agents)."""
    out = {"status": selection.status, "message": selection.message, "problems": [],
           "already_solved": [{"equation_id": c.problem_id, "equation": c.original.latex,
                               "answer": c.answer_text} for c in selection.solved]}
    for chain in selection.problems:
        sol = solve_chain(chain)
        out["problems"].append({
            "equation_id": chain.problem_id,
            "equation": chain.original.latex,
            "status": chain.status,
            "continue_from": chain.continue_from.latex if chain.continue_from else None,
            "existing_steps": sol.existing_steps,
            "new_steps": sol.new_steps,
            "wrong_steps": sol.wrong_steps,
            "result": sol.kind,
            "value": str(sol.value) if sol.value is not None else None,
            "verified": sol.verified,
        })
    return out