"""equations.json -> problem selection. PaddleOCR and stroke grouping are stubbed."""
import asyncio
import json
import sys
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---- stub the heavy modules before importing the route ----
GROUPS = []          # what the fake stroke grouper returns
OCR_RESULTS = {}     # bbox["x"] -> latex, or an Exception to raise

grouper = types.ModuleType("app.services.stroke_grouper")
grouper.group_freedraw_strokes = lambda strokes: list(GROUPS)
ocr = types.ModuleType("app.services.equation_ocr")


def _fake_recognize(image_bytes, bbox):
    result = OCR_RESULTS[bbox["x"]]
    if isinstance(result, Exception):
        raise result
    return {"equation": result, "confidence": None}


ocr.recognize_equation = _fake_recognize
sys.modules.setdefault("app.services.stroke_grouper", grouper)
sys.modules.setdefault("app.services.equation_ocr", ocr)

from app.api.routes import equations as route  # noqa: E402
from app.reasoning.problem_selection import Solution  # noqa: E402
from app.services import whiteboard_problems as wp  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(route, "DATA_DIR", tmp_path)
    monkeypatch.setattr(route, "EQUATIONS_FILE", tmp_path / "equations.json")
    monkeypatch.setattr(route, "STROKES_FILE", tmp_path / "strokes.json")
    # Also patch the route's own references, in case another test already imported
    # the real PaddleOCR modules before this file's stubs were installed.
    monkeypatch.setattr(route, "group_freedraw_strokes", grouper.group_freedraw_strokes)
    monkeypatch.setattr(route, "recognize_equation", _fake_recognize)
    GROUPS.clear()
    OCR_RESULTS.clear()
    app = FastAPI()
    app.include_router(route.router, prefix="/api")
    return TestClient(app)


def line(strokes, row, col=0):
    """A stroke group on line `row` (60 px per line) of column `col` (400 px wide)."""
    return {"stroke_ids": strokes, "bbox": {"x": col * 400 + row * 0.001, "y": row * 60, "width": 200, "height": 40}}


def write(client, *lines_and_latex):
    """Simulate the student writing lines one after another: group, then OCR each new one."""
    for group, latex in lines_and_latex:
        GROUPS.append(group)
        OCR_RESULTS[group["bbox"]["x"]] = latex
        groups = client.post("/api/equations/group").json()["equations"]
        eq_id = route.build_equation_id(group["stroke_ids"])
        assert eq_id in groups
        client.post(f"/api/equations/{eq_id}/ocr", files={"image": ("eq.png", b"png", "image/png")})


def next_problem(client, **params):
    return client.get("/api/equations/next-problem", params=params).json()


# ---------- equations.py changes ----------
def test_sequence_survives_regrouping(client):
    write(client, (line(["a"], 0), "2x + 3 = 11"), (line(["b"], 0, col=1), "3x = 12"))
    data = json.loads(route.EQUATIONS_FILE.read_text())
    seqs = {r["equation"]: r["sequence"] for r in data["equations"].values()}
    assert seqs == {"2x + 3 = 11": 1, "3x = 12": 2}
    client.post("/api/equations/group")        # regroup rewrites updated_at
    data = json.loads(route.EQUATIONS_FILE.read_text())
    assert {r["equation"]: r["sequence"] for r in data["equations"].values()} == seqs


def test_failed_ocr_is_recorded(client):
    GROUPS.append(line(["a"], 0))
    OCR_RESULTS[0.0] = RuntimeError("PaddleOCR returned no recognized equation.")
    client.post("/api/equations/group")
    eq_id = route.build_equation_id(["a"])
    r = client.post(f"/api/equations/{eq_id}/ocr", files={"image": ("eq.png", b"png", "image/png")})
    assert r.status_code == 500
    record = json.loads(route.EQUATIONS_FILE.read_text())["equations"][eq_id]
    assert record["ocr_status"] == "failed"


# ---------- end to end through the preview endpoint ----------
def test_board_with_solved_and_partial_problem(client):
    write(client,
          (line(["a1"], 0), "2x + 3 = 11"), (line(["a2"], 1), "2x = 8"), (line(["a3"], 2), "x = 4"),
          (line(["b1"], 4), "5x - 2 = 13"), (line(["b2"], 5), "5x = 15"))
    out = next_problem(client)
    assert out["status"] == "selected"
    p = out["problems"][0]
    assert p["equation"] == "5x - 2 = 13" and p["status"] == "partial"
    assert p["new_steps"] == ["x = 3"] and p["verified"]
    assert out["already_solved"][0]["answer"] == "x = 4"


def test_everything_solved(client):
    write(client, (line(["a1"], 0), "2x + 3 = 11"), (line(["a2"], 1), "x = 4"))
    assert next_problem(client)["status"] == "all_solved"


def test_paddle_style_latex(client):
    write(client, (line(["a1"], 0), r"\mathrm{2x} + 3 = 11"))
    assert next_problem(client)["problems"][0]["value"] == "4"


def test_unrecognized_newest_writing_asks(client):
    write(client, (line(["a1"], 0), "2x = 6"))
    GROUPS.append(line(["b1"], 0, col=1))
    OCR_RESULTS[400.0] = RuntimeError("no equation")
    client.post("/api/equations/group")
    client.post(f"/api/equations/{route.build_equation_id(['b1'])}/ocr",
                files={"image": ("eq.png", b"png", "image/png")})
    assert next_problem(client)["status"] == "needs_clarification"


def test_pending_then_timeout(client):
    write(client, (line(["a1"], 0), "2x = 6"))
    GROUPS.append(line(["b1"], 0, col=1))
    client.post("/api/equations/group")            # grouped, OCR never called
    records = wp.load_recognized_equations(route.EQUATIONS_FILE)
    assert wp.select_problems(records).status == "pending"          # before the wait ends
    sel = asyncio.run(wp.find_problem_to_solve(equations_file=route.EQUATIONS_FILE, wait_seconds=0))
    assert sel.status == "needs_clarification" and "still being recognized" in sel.message


def test_erased_equation_disappears(client):
    write(client, (line(["a1"], 0), "2x = 6"), (line(["b1"], 0, col=1), "x + 1 = 5"))
    GROUPS.pop()                                   # student erases x + 1 = 5
    client.post("/api/equations/group")
    assert next_problem(client)["problems"][0]["equation"] == "2x = 6"


# ---------- agent-solved ledger ----------
def test_agent_solved_problem_is_not_solved_again(client):
    write(client, (line(["a1"], 0), "2x + 3 = 11"))
    eq_id = route.build_equation_id(["a1"])
    sol = Solution(eq_id, "2x + 3 = 11", "unique", 4, ["2x + 3 = 11"], ["2 x = 8", "x = 4"], True, [])
    wp.record_agent_solution(sol, "task-1", equations_file=route.EQUATIONS_FILE)
    out = next_problem(client)
    assert out["status"] == "all_solved" and out["already_solved"][0]["answer"] == "x = 4"


def test_ledger_ignored_when_equation_changed(client):
    write(client, (line(["a1"], 0), "2x + 3 = 11"))
    eq_id = route.build_equation_id(["a1"])
    sol = Solution(eq_id, "2x + 3 = 9", "unique", 3, [], ["x = 3"], True, [])
    wp.record_agent_solution(sol, "task-1", equations_file=route.EQUATIONS_FILE)
    assert next_problem(client)["status"] == "selected"


def test_legacy_records_without_sequence(tmp_path):
    path = tmp_path / "equations.json"
    path.write_text(json.dumps({"equations": {
        "eq_old": {"equation": "2x = 6", "bbox": {"x": 0, "y": 0, "width": 200, "height": 40},
                   "updated_at": "2026-01-01T00:00:00+00:00"},
        "eq_new": {"equation": "3x = 9", "bbox": {"x": 400, "y": 0, "width": 200, "height": 40},
                   "updated_at": "2026-01-02T00:00:00+00:00"},
    }}))
    records = {r.element_id: r.sequence for r in wp.load_recognized_equations(path)}
    assert records["eq_old"] < records["eq_new"] < 1