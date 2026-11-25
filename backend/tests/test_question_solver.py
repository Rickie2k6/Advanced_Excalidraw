"""'solve question N' end to end. Paddle layout analysis and Grounding DINO are mocked."""
import asyncio
import base64

import pytest

from app.reasoning.general_solver import parse_problem
from app.services import question_solver as qs
from app.services.paddle import document_blocks as db
from app.services.question_region import Box, element_box, estimate_steps_size

REAL_LLM_LOCATE = qs._llm_locate      # captured before conftest swaps it out for each test
REAL_ANALYZE = db.analyze_document_blocks   # captured before the fake_paddle fixture replaces it

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


@pytest.mark.parametrize("right_blocked", [False, True])
def test_no_space_writes_complete_solution_outside_worksheet(right_blocked):
    blocker = {"id": "b", "type": "rectangle", "x": 100, "y": 370, "width": 1300, "height": 185}
    obstacles = [blocker]
    if right_blocked:
        obstacles.append({"id": "right", "type": "rectangle", "x": 1400, "y": 370,
                          "width": 350, "height": 600})
    action = run("solve question 2", scene(*obstacles)).action
    assert action["answer"] == "(x, y) = (1, 1)"
    assert action["placement"] == ("below" if right_blocked else "beside")
    assert action["scale"] == 1.0
    column, = action["columns"]
    assert column["steps"] == action["steps"]
    assert column["steps"][-1] == "x=1"
    x, y = column["x"], column["y"]
    width, height = estimate_steps_size(column["steps"], action["scale"])
    solution_box = Box(x, y, x + width, y + height)
    for element in [IMAGE, *obstacles]:
        assert not solution_box.overlaps(element_box(element).grow(15))


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


# ---------- beyond 2x2 linear systems ----------
def _question_2_with(*formulas):
    """Worksheet where question 2 holds `formulas` (one block per line) instead of the 2x2 system."""
    blocks = [b for b in PAGE_BLOCKS if "-2y+7x" not in b["text"]]
    for i, text in enumerate(formulas):
        blocks.append({"kind": "formula", "label": "display_formula", "text": text,
                       "bbox": [840, 750 + 45 * i, 1080, 785 + 45 * i]})
    return blocks


@pytest.mark.parametrize("formulas,answer,kind", [
    ([r"x^{2}-5x+6=0"], "x = 2 or x = 3", "quadratic equation"),
    ([r"x^{3}-6x^{2}+11x-6=0"], "x = 1 or x = 2 or x = 3", "cubic equation"),
    ([r"x^{4}-5x^{2}+4=0"], "x = -2 or x = -1 or x = 1 or x = 2", "degree-4 equation"),
    ([r"\begin{cases}x+y+z=6\\2x-y+z=3\\x+2y-z=2\end{cases}"], "(x, y, z) = (1, 2, 3)",
     "linear system of 3 equations"),
    (["x+y=5", "xy=6"], "(x, y) = (2, 3) or (x, y) = (3, 2)", "non-linear system of 2 equations"),
])
def test_other_problem_types(fake_paddle, formulas, answer, kind):
    fake_paddle["blocks"] = _question_2_with(*formulas)
    action = run("solve question 2", scene()).action
    assert action["problem_type"] == kind
    assert set(action["answer"].split(" or ")) == set(answer.split(" or "))
    assert all(qs.DRAWABLE.match(step) for step in action["steps"])


def test_irrational_roots_are_approximate_on_the_board(fake_paddle):
    fake_paddle["blocks"] = _question_2_with("x^2-3x-1=0")
    action = run("giải câu 2", scene()).action
    assert action["approximate"] is True
    assert "x≈3.303" in action["steps"] and "sqrt(13)" in action["answer"]


def test_no_real_solution_is_still_explained(fake_paddle):
    fake_paddle["blocks"] = _question_2_with("x^2+x+1=0")
    action = run("solve question 2", scene()).action
    assert action["answer"] == "no real solution" and "Δ=-3" in action["steps"]


def test_unsupported_equation_explains(fake_paddle, monkeypatch):
    fake_paddle["blocks"] = _question_2_with(r"\sin(x)=1")
    monkeypatch.setattr(qs, "_system_with_dino", lambda candidate: (None, "nothing found"))
    result = run("solve question 2", scene())
    assert result.action is None and "degree 1 to 6" in result.message


# ---------- the LLM reads what Paddle found (positions still from Paddle) ----------
MESSY_BLOCKS = [   # headings Paddle didn't return as plain "Example N"
    {"kind": "text", "label": "text", "text": "Examples Pick One Example To Try", "bbox": [0, 50, 2600, 110]},
    {"kind": "text", "label": "text", "text": "Exampie 1: Solve the system by using elimination.", "bbox": [60, 170, 660, 240]},
    {"kind": "text", "label": "text", "text": r"$\{ 2x + 3y = 11 , -2x + 5y = 13$", "bbox": [800, 280, 1120, 370]},
    {"kind": "text", "label": "text", "text": "Exarnple 2 Solve the system using elimination.", "bbox": [60, 640, 600, 720]},
    {"kind": "text", "label": "text", "text": r"$\{ -2y + 7x = 5 , -3y + 7x = 4$", "bbox": [840, 750, 1080, 830]},
    {"kind": "text", "label": "text", "text": "Exarnple 3", "bbox": [60, 1110, 260, 1150]},
]


def llm_reply(equations, headings=None):
    headings = headings or {1: 1, 2: 3, 3: 5}
    return lambda blocks, number: {"headings": headings, "question_found": number in headings,
                                   "equation_blocks": [4], "equations": equations}


def test_llm_finds_heading_paddle_text_missed(fake_paddle, monkeypatch):
    fake_paddle["blocks"] = MESSY_BLOCKS
    monkeypatch.setattr(qs, "_llm_locate", llm_reply(["7x-2y=5", "7x-3y=4"]))
    action = run("solve example 2", scene()).action
    assert action["answer"] == "(x, y) = (1, 1)"
    assert action["read_as"] == ["7x-2y=5", "7x-3y=4"]          # shown to the user
    region = Box(100, 50 + 640 / 2, 100 + 1300, 50 + 1110 / 2)  # Paddle positions, not the LLM's
    assert action["region"] == region.to_dict()


def test_llm_invented_numbers_are_rejected(fake_paddle, monkeypatch):
    fake_paddle["blocks"] = MESSY_BLOCKS
    monkeypatch.setattr(qs, "_llm_locate", llm_reply(["9x-8y=6", "7x-3y=4"]))   # 9, 8, 6 aren't on the page
    result = run("solve example 2", scene())
    assert result.action is None and "couldn't read" in result.message


def test_llm_says_question_is_missing(fake_paddle, monkeypatch):
    fake_paddle["blocks"] = MESSY_BLOCKS
    monkeypatch.setattr(qs, "_llm_locate", llm_reply([], headings={1: 1, 2: 3, 3: 5}))
    assert "couldn't find question 7" in run("solve question 7", scene()).message


def test_llm_unavailable_falls_back_cleanly(fake_paddle, monkeypatch):
    fake_paddle["blocks"] = MESSY_BLOCKS

    def broken(blocks, number):
        raise RuntimeError("no API key")

    monkeypatch.setattr(qs, "_llm_locate", broken)
    assert "couldn't find question 2" in run("solve question 2", scene()).message


def test_llm_bad_indices_are_ignored(fake_paddle, monkeypatch):
    fake_paddle["blocks"] = MESSY_BLOCKS
    monkeypatch.setattr(qs, "_llm_locate", llm_reply(["7x-2y=5", "7x-3y=4"], headings={2: 99}))
    assert run("solve question 2", scene()).action is None


def test_parse_json_reply_and_grounding():
    assert qs._parse_json_reply('```json\n{"a": 1}\n```') == {"a": 1}
    assert qs._parse_json_reply("Sure! {\"a\": 2} hope it helps") == {"a": 2}
    assert qs._parse_json_reply("not json") is None
    assert qs.grounded(["7x-2y=5", "7x-3y=4"], r"\{ -2y + 7x = 5 , -3y + 7x = 4")
    assert not qs.grounded(["7x-2y=6"], r"-2y + 7x = 5")
    assert qs.grounded(["x^2-5x+6=0"], "x^{2}-5x+6=0")


def test_llm_reply_is_validated(monkeypatch):
    import app.services.llm_service as llm
    reply = ('```json\n{"headings": [{"number": 2, "block": 3}, {"number": 3, "block": 99}, {"number": "x"}],'
             ' "question_found": true, "equation_blocks": [4, 42], "equations": ["7x-2y=5", " ", "7x-3y=4"]}\n```')
    monkeypatch.setattr(llm, "locate_question", lambda prompt, system: reply)
    result = REAL_LLM_LOCATE(MESSY_BLOCKS, 2)
    assert result == {"headings": {2: 3}, "equations": ["7x-2y=5", "7x-3y=4"],
                      "equation_blocks": [4], "question_found": True}


# ---------- worksheet merged into one <table> by the layout model: line-level OCR ----------
# The user's real board: a 674x426 worksheet image whose layout pass returned one table block.
REAL_IMAGE = {"id": "CUap", "type": "image", "fileId": "real", "x": 508, "y": 213, "width": 674, "height": 426}
REAL_LINES = [
    ("Examples", [10, 15, 80, 28]), ("Pick One Example To Try", [450, 30, 645, 55]),
    ("Example 1", [12, 40, 60, 50]), ("Solve the system by using elimination.", [12, 50, 160, 58]),
    ("{2x + 3y = 11", [200, 72, 262, 82]), ("-2x + 5y = 13", [204, 82, 262, 92]),
    ("Example 2", [12, 155, 60, 165]), ("Solve the system using elimination.", [12, 166, 150, 174]),
    ("{-2y + 7x = 5", [210, 185, 262, 195]), ("-3y + 7x = 4", [212, 195, 262, 205]),
    ("Example 3", [12, 275, 60, 285]), ("Solve the system using elimination.", [12, 286, 150, 294]),
    ("{8x - 4y = -4", [210, 300, 262, 310]), ("4y = 3x + 14", [212, 312, 262, 322]),
    ("Lesson 6.3 Solve Systems with Elimination", [10, 380, 160, 390]), ("Page 3 of 13", [600, 380, 650, 388]),
]
REAL_BLOCKS = [{"label": "ocr_line", "kind": db.line_kind(t), "text": t, "bbox": b} for t, b in REAL_LINES]


def real_scene():
    return {"elements": [REAL_IMAGE], "files": {"real": {"dataURL": PNG}}}


@pytest.mark.parametrize("number,answer", [(1, "(x, y) = (1, 3)"), (2, "(x, y) = (1, 1)"), (3, "(x, y) = (2, 5)")])
def test_small_real_worksheet_read_line_by_line(monkeypatch, number, answer):
    monkeypatch.setattr(db, "analyze_document_blocks",
                        lambda path: {"image_width": 670, "image_height": 420, "blocks": REAL_BLOCKS})
    action = run(f"solve example {number}", real_scene()).action
    assert action["answer"] == answer
    r = action["region"]
    region = Box(r["x"], r["y"], r["x"] + r["width"], r["y"] + r["height"])
    equations_right_edge = REAL_IMAGE["x"] + 262 * 674 / 670
    for column in action["columns"]:
        assert region.x1 <= column["x"] and region.y1 <= column["y"] <= region.y2
        assert column["x"] > equations_right_edge            # written beside the system, not over it


def test_clean_equation_line():
    assert qs.clean_equation_line("{2x + 3y = 11") == "2x + 3y = 11"
    assert qs.clean_equation_line("|-2x+5y=13") == "-2x+5y=13"
    assert qs.clean_equation_line("(8x - 4y = -4") == "8x - 4y = -4"
    assert qs.clean_equation_line("2(x+1)=4") == "2(x+1)=4"


def test_coarse_layout_is_detected():
    table = [{"label": "table", "kind": "text", "text": "<table><tr><td>Example 1</td></tr></table>",
              "bbox": [7, 21, 660, 410]}]
    assert db.is_coarse(table)
    assert db.is_coarse(REAL_BLOCKS[:2])
    assert not db.is_coarse(REAL_BLOCKS)


def test_extract_lines_from_pp_ocr_result():
    import numpy as np

    class Result:
        json = {"res": {"rec_texts": ["Example 2", "-2y + 7x = 5", " "],
                        "rec_boxes": np.array([[12, 155, 60, 165], [210, 185, 262, 195], [0, 0, 1, 1]])}}
    assert db.extract_lines(Result()) == [("Example 2", [12.0, 155.0, 60.0, 165.0]),
                                          ("-2y + 7x = 5", [210.0, 185.0, 262.0, 195.0])]

    class Polys:
        json = {"res": {"rec_texts": ["x+y=2"], "rec_boxes": [],
                        "rec_polys": [[[1, 2], [9, 2], [9, 8], [1, 8]]]}}
    assert db.extract_lines(Polys()) == [("x+y=2", [1.0, 2.0, 9.0, 8.0])]


def test_document_blocks_switches_to_line_ocr(tmp_path, monkeypatch):
    from PIL import Image
    path = tmp_path / "sheet.png"
    Image.new("RGB", (670, 420), "white").save(path)
    monkeypatch.setattr(db, "CACHE_DIR", tmp_path / "cache")
    table = [{"label": "table", "kind": "text", "text": "<table>...</table>", "bbox": [7, 21, 660, 410]}]
    monkeypatch.setattr(db, "_run_layout", lambda image: table)
    monkeypatch.setattr(db, "_run_lines", lambda image: REAL_BLOCKS)
    result = REAL_ANALYZE(path)
    assert result["source"] == "ocr_lines" and len(result["blocks"]) == len(REAL_BLOCKS)
    monkeypatch.setattr(db, "_run_lines", lambda image: (_ for _ in ()).throw(AssertionError("cache not used")))
    assert REAL_ANALYZE(path)["source"] == "ocr_lines"     # second call comes from the cache


def test_llm_sees_plain_text_of_a_table_block():
    prompt = qs._llm_prompt([{"kind": "text", "bbox": [0, 0, 1, 1],
                              "text": "<table><tr><td>Example 1\\nSolve</td><td>x</td></tr></table>" + "y" * 600
                                      + "<td>Example 2</td>"}], 2)
    assert "Example 2" in prompt and "<td>" not in prompt

# ---------- page still one block: answer in the chat instead of failing ----------
TABLE_ONLY = [
    {"kind": "title", "label": "paragraph_title", "text": "Examples", "bbox": [21, 25, 138, 52]},
    {"kind": "text", "label": "table", "bbox": [7, 57, 1439, 850],
     "text": "<table><tr><td>Example 1\\nSolve the system by using elimination.</td></tr>"
             "<tr><td>Example 2\\nSolve the system using elimination. -2y+7x=5 -3y+7x=4</td></tr>"
             "<tr><td>Example 3</td></tr></table>"},
]


def test_answer_in_chat_when_the_page_is_one_block(fake_paddle, monkeypatch):
    fake_paddle["blocks"] = TABLE_ONLY
    monkeypatch.setattr(qs, "_llm_locate", llm_reply(["7x-2y=5", "7x-3y=4"], headings={1: 1, 2: 1, 3: 1}))
    result = run("solve example 2", scene())
    assert result.action is None
    assert "(x, y) = (1, 1)" in result.message and "read as 7x-2y=5, 7x-3y=4" in result.message
    assert "didn't write on the board" in result.message


def test_chat_answer_still_rejects_invented_equations(fake_paddle, monkeypatch):
    fake_paddle["blocks"] = TABLE_ONLY
    monkeypatch.setattr(qs, "_llm_locate", llm_reply(["9x-8y=6", "7x-3y=4"], headings={1: 1, 2: 1, 3: 1}))
    assert "couldn't find question 2" in run("solve example 2", scene()).message


def test_line_ocr_runs_without_onednn(monkeypatch):
    import sys
    import types
    created = {}

    class FakePaddleOCR:
        def __init__(self, **options):
            created.update(options)

    monkeypatch.setitem(sys.modules, "paddleocr", types.SimpleNamespace(PaddleOCR=FakePaddleOCR))
    monkeypatch.setattr(db, "_line_ocr", None)
    db._get_line_ocr()
    assert created["enable_mkldnn"] is False
