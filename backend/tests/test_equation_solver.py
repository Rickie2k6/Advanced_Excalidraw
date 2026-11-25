"""'solve question N' end to end. Paddle layout analysis and Grounding DINO are mocked."""
import asyncio
import base64

import pytest

from app.reasoning.general_solver import parse_problem
from app.services import question_solver as qs
from app.services.paddle import document_blocks as db
from app.services.question_region import Box

# Worksheet page in IMAGE pixels (2600 x 1520), shown on the canvas at half size.
PAGE_BLOCKS = [
    {"kind": "title", "label": "paragraph_title", "text": "Examples", "bbox": [0, 50, 2600, 110]},
    {"kind": "title", "label": "paragraph_title", "text": "Example 1", "bbox": [60, 170, 260, 210]},
    {"kind": "text", "label": "text", "text": "Solve the system by using elimination.", "bbox": [60, 210, 660, 240]},
    {"kind": "formula", "label": "display_formula", "text": r"\begin{cases}2x+3y=11\\-2x+5y=13\end{cases}",
     "bbox": [800, 280, 1120, 370]},
    {"kind": "title", "label": "paragraph_title", "text": "Example 2", "bbox": [60, 640, 260, 680]},
    {"kind": "text", "label": "text", "text": "Solve the system using elimination.", "bbox": [60, 690, 600, 720]},
    {"kind": "formula", "label": "display_formula",
     "text": r"\left\{\begin{array}{l}-2y+7x=5\\-3y+7x=4\end{array}\right.", "bbox": [840, 750, 1080, 830]},
    {"kind": "title", "label": "paragraph_title", "text": "Example 3", "bbox": [60, 1110, 260, 1150]},
    {"kind": "formula", "label": "display_formula", "text": r"\begin{cases}8x-4y=-4\\4y=3x+14\end{cases}",
     "bbox": [840, 1260, 1080, 1340]},
]

IMAGE = {"id": "sheet", "type": "image", "fileId": "file1", "x": 100, "y": 50, "width": 1300, "height": 760}
PNG = "data:image/png;base64," + base64.b64encode(b"not really a png").decode()


def scene(*extra, blocks=PAGE_BLOCKS):
    return {"elements": [IMAGE, *extra], "files": {"file1": {"dataURL": PNG}}}


@pytest.fixture(autouse=True)
def fake_paddle(tmp_path, monkeypatch):
    monkeypatch.setattr(qs, "WHITEBOARD_IMAGES_DIR", tmp_path)
    state = {"blocks": PAGE_BLOCKS, "calls": 0}

    def analyze(path):
        state["calls"] += 1
        return {"image_width": 2600, "image_height": 1520, "blocks": state["blocks"]}

    monkeypatch.setattr(db, "analyze_document_blocks", analyze)
    return state


def run(question, sc):
    return asyncio.run(qs.solve_question_request(question, sc))


# ---------- which messages are handled ----------
@pytest.mark.parametrize("text", ["solve question 2", "Solve the question 2", "giải câu 2",
                                  "please solve example 2", "làm bài 2"])
def test_recognized_requests(text):
    assert qs.is_question_solve_request(text) == 2


@pytest.mark.parametrize("text", ["what is question 2 about?", "what do you think of question 2", "solve 2x + 3 = 11", "hello", "circle the cat"])
def test_other_messages_are_left_alone(text):
    assert run(text, scene()) is None


# ---------- end to end ----------
def test_solves_question_2_inside_its_region():
    result = run("solve the question 2", scene())
    action = result.action
    assert action["action"] == "write_math_steps"
    assert action["answer"] == "(x, y) = (1, 1)"
    assert action["steps"][-1] == "x=1"
    region = Box(100, 50 + 640 / 2, 100 + 1300, 50 + 1110 / 2)      # Example 2 heading -> Example 3 heading
    assert action["region"] == region.to_dict()
    for column in action["columns"]:
        assert region.x1 <= column["x"] and region.y1 <= column["y"] <= region.y2
    assert [s for c in action["columns"] for s in c["steps"]] == action["steps"]


def test_avoids_student_marks_in_the_region():
    marks = {"id": "m", "type": "freedraw", "x": 600, "y": 410, "width": 500, "height": 120}
    action = run("solve question 2", scene(marks)).action
    m = Box(600, 410, 1100, 530)
    for column in action["columns"]:
        assert not (m.x1 - 15 < column["x"] < m.x2 + 15 and m.y1 - 15 < column["y"] < m.y2 + 15)


def test_each_question_gets_its_own_answer():
    assert run("solve question 1", scene()).action["answer"] == "(x, y) = (1, 3)"
    assert run("solve question 3", scene()).action["answer"] == "(x, y) = (2, 5)"


def test_page_analysis_is_reused_within_a_request(fake_paddle):
    second = dict(IMAGE, id="sheet-copy", x=2000)        # same file shown twice
    result = run("solve question 2", {"elements": [IMAGE, second], "files": {"file1": {"dataURL": PNG}}})
    assert fake_paddle["calls"] == 1
    assert "2 different pages" in result.message


def test_missing_question():
    result = run("solve question 9", scene())
    assert result.action is None and "couldn't find question 9" in result.message


def test_no_worksheet():
    result = run("solve question 2", {"elements": [], "files": {}})
    assert result.action is None and "worksheet" in result.message


def test_two_one_line_formula_blocks_are_combined(fake_paddle):
    fake_paddle["blocks"] = [b for b in PAGE_BLOCKS if "-2y+7x" not in b["text"]] + [
        {"kind": "formula", "label": "display_formula", "text": "-2y+7x=5", "bbox": [840, 750, 1080, 785]},
        {"kind": "formula", "label": "display_formula", "text": "-3y+7x=4", "bbox": [840, 795, 1080, 830]},
    ]
    assert run("solve question 2", scene()).action["answer"] == "(x, y) = (1, 1)"


def test_dino_fallback_when_paddle_has_no_formula(fake_paddle, monkeypatch):
    fake_paddle["blocks"] = [b for b in PAGE_BLOCKS if "-2y+7x" not in b["text"]]
    monkeypatch.setattr(qs, "_system_with_dino",
                        lambda candidate: (parse_problem(["7x-2y=5", "7x-3y=4"]), "dino"))
    assert run("solve question 2", scene()).action["answer"] == "(x, y) = (1, 1)"


def test_unreadable_question_explains_instead_of_writing(fake_paddle, monkeypatch):
    fake_paddle["blocks"] = [b for b in PAGE_BLOCKS if "-2y+7x" not in b["text"]]
    monkeypatch.setattr(qs, "_system_with_dino", lambda candidate: (None, "nothing found"))
    result = run("solve question 2", scene())
    assert result.action is None and "couldn't read" in result.message


def test_no_space_keeps_question_identity_in_canvas_action():
    blocker = {"id": "b", "type": "rectangle", "x": 100, "y": 370, "width": 1300, "height": 185}
    action = run("solve question 2", scene(blocker)).action
    assert action["action"] == "write_math_steps"
    assert action["question_number"] == 2
    assert action["source_equation_id"] == "question-2"
    assert action["answer"] == "(x, y) = (1, 1)"


# ---------- reading Paddle output ----------
def test_extract_all_blocks_from_paddle_json():
    class Page:
        json = {"res": {"parsing_res_list": [
            {"block_label": "paragraph_title", "block_content": "Example 2", "block_bbox": [60, 640, 260, 680]},
            {"block_label": "display_formula", "block_content": "x+y=2", "block_bbox": [[1, 2], [9, 2], [9, 8], [1, 8]]},
            {"block_label": "text", "block_content": "  ", "block_bbox": [0, 0, 1, 1]},
        ]}}
    blocks = db.extract_all_blocks(Page())
    assert [(b["kind"], b["text"]) for b in blocks] == [("title", "Example 2"), ("formula", "x+y=2")]
    assert blocks[1]["bbox"] == [1.0, 2.0, 9.0, 8.0]
