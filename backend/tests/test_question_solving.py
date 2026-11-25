"""Solve 'question N' from a worksheet: find its region, solve the system, find empty space.

The layout below copies the worksheet in the screenshot (Examples 1-3, one column),
scaled to a 1300 x 760 page placed at (100, 50) on the canvas.
"""
from fractions import Fraction

import pytest

from app.reasoning.linear_system import parse_system, solve_by_elimination, split_system
from app.reasoning.problem_selection import UnsupportedMath
from app.services.question_region import (
    Box, TextBlock, find_empty_spot, find_question_region, image_box_to_scene,
    place_solution, requested_question_number,
)

OX, OY = 100, 50                 # where the worksheet image sits on the canvas
PAGE = Box(OX, OY, OX + 1300, OY + 760)


def B(x1, y1, x2, y2):
    return Box(OX + x1, OY + y1, OX + x2, OY + y2)


WORKSHEET = [
    TextBlock("Examples", B(0, 25, 1300, 55), "title"),
    TextBlock("Pick One Example To Try", B(900, 60, 1300, 120), "title"),
    TextBlock("Example 1", B(30, 85, 130, 105), "title"),
    TextBlock("Solve the system by using elimination.", B(30, 105, 330, 120)),
    TextBlock(r"\begin{cases}2x+3y=11\\-2x+5y=13\end{cases}", B(400, 140, 560, 185), "formula"),
    TextBlock("Example 2", B(30, 320, 130, 340), "title"),
    TextBlock("Solve the system using elimination.", B(30, 345, 300, 360)),
    TextBlock(r"\begin{cases}-2y+7x=5\\-3y+7x=4\end{cases}", B(420, 375, 540, 415), "formula"),
    TextBlock("Example 3", B(30, 555, 130, 575), "title"),
    TextBlock("Solve the system using elimination.", B(30, 580, 300, 595)),
    TextBlock(r"\begin{cases}8x-4y=-4\\4y=3x+14\end{cases}", B(420, 630, 540, 670), "formula"),
]

SCENE = [
    {"id": "worksheet", "type": "image", "x": OX, "y": OY, "width": 1300, "height": 760},
    # the student's marks next to Example 2 and the "-7x" text box
    {"id": "s1", "type": "freedraw", "x": OX + 380, "y": OY + 390, "width": 40, "height": 20},
    {"id": "s2", "type": "freedraw", "x": OX + 400, "y": OY + 420, "width": 150, "height": 30},
    {"id": "t1", "type": "text", "x": OX + 690, "y": OY + 410, "width": 50, "height": 25},
    {"id": "gone", "type": "text", "x": OX + 600, "y": OY + 380, "width": 300, "height": 150, "isDeleted": True},
]


# ---------- which question ----------
@pytest.mark.parametrize("text,number", [
    ("solve question 2", 2), ("Giải câu 2", 2), ("do example 3 please", 3),
    ("giải bài số 1", 1), ("solve problem #2", 2), ("solve 2x + 3 = 11", None),
])
def test_requested_question_number(text, number):
    assert requested_question_number(text) == number


# ---------- region ----------
def test_region_runs_from_heading_to_next_heading():
    region = find_question_region(WORKSHEET, 2, PAGE)
    assert region.box == Box(PAGE.x1, OY + 320, PAGE.x2, OY + 555)
    assert {b.text for b in region.blocks} >= {"Example 2", r"\begin{cases}-2y+7x=5\\-3y+7x=4\end{cases}"}
    assert not any("Example 3" in b.text or "2x+3y=11" in b.text for b in region.blocks)


def test_last_question_runs_to_page_bottom():
    assert find_question_region(WORKSHEET, 3, PAGE).box.y2 == PAGE.y2


def test_missing_question():
    assert find_question_region(WORKSHEET, 7, PAGE) is None


def test_side_by_side_columns():
    blocks = [TextBlock("Question 1", Box(0, 0, 100, 20)), TextBlock("Question 2", Box(500, 0, 600, 20)),
              TextBlock("Question 3", Box(0, 400, 100, 420))]
    region = find_question_region(blocks, 1, Box(0, 0, 1000, 800))
    assert region.box == Box(0, 0, 500, 400)
    region2 = find_question_region(blocks, 2, Box(0, 0, 1000, 800))
    assert region2.box == Box(500, 0, 1000, 800)     # own column only; nothing below it


def test_image_pixels_to_scene():
    element = {"x": 100, "y": 50, "width": 650, "height": 380}       # image shown at half size
    assert image_box_to_scene([200, 100, 400, 200], element, 1300, 760) == Box(200, 100, 300, 150)


# ---------- empty spot ----------
def test_spot_stays_inside_region_and_avoids_marks():
    region = find_question_region(WORKSHEET, 2, PAGE)
    steps = solve_by_elimination(parse_system(region.blocks[2].text)).steps
    placed = place_solution(region, SCENE, steps, ignore_element_ids=["worksheet"])
    assert placed is not None
    total = Box(placed["x"], placed["y"], placed["x"] + placed["width"], placed["y"] + placed["height"])
    assert total.inside(region.box)
    marks = [Box(OX + 380, OY + 390, OX + 420, OY + 410), Box(OX + 400, OY + 420, OX + 550, OY + 450),
             Box(OX + 690, OY + 410, OX + 740, OY + 435), B(420, 375, 540, 415), B(30, 320, 130, 340)]
    assert not any(total.overlaps(m) for m in marks)
    assert [s for c in placed["columns"] for s in c["steps"]] == steps     # every step placed, in order


def test_prefers_right_of_the_equations():
    region = Box(0, 0, 1000, 300)
    anchor = Box(400, 50, 520, 100)
    spot = find_empty_spot(region, [anchor], 150, 120, anchor=anchor)
    assert spot.x1 >= anchor.x2 and spot.y1 < anchor.y2


def test_no_space_returns_none():
    region = Box(0, 0, 300, 100)
    assert find_empty_spot(region, [Box(0, 0, 300, 100)], 50, 20) is None


# ---------- solving ----------
@pytest.mark.parametrize("source,answer", [
    (r"\begin{cases}2x+3y=11\\-2x+5y=13\end{cases}", {"x": 1, "y": 3}),
    (r"\left\{\begin{array}{l}-2y+7x=5\\-3y+7x=4\end{array}\right.", {"x": 1, "y": 1}),
    (["8x-4y=-4", "4y=3x+14"], {"x": 2, "y": 5}),
    (["3x+2y=7", "2x+3y=8"], {"x": 1, "y": 2}),
    (["x/2+y=3", "x-y=0"], {"x": 2, "y": 2}),
    (["2x+3y=1", "x-y=3"], {"x": 2, "y": -1}),
    (["3x+y=1", "x+2y=1"], {"x": Fraction(1, 5), "y": Fraction(2, 5)}),
])
def test_unique_solutions_are_verified(source, answer):
    result = solve_by_elimination(parse_system(source))
    assert result.kind == "unique" and result.values == answer and result.verified
    assert len(result.steps) == len(result.explanations)


def test_example_2_steps():
    result = solve_by_elimination(parse_system(["-2y+7x=5", "-3y+7x=4"]))
    assert result.steps == ["7x-2y=5", "7x-3y=4", "y=1", "7x-2(1)=5", "7x-2=5", "7x=7", "x=1"]
    assert result.answer == "(x, y) = (1, 1)"


def test_no_solution_and_infinitely_many():
    assert solve_by_elimination(parse_system(["x+y=2", "x+y=5"])).kind == "none"
    assert solve_by_elimination(parse_system(["x+y=2", "2x+2y=4"])).kind == "all"


def test_split_system_formats():
    assert split_system(r"\begin{cases}2x+3y=11\\-2x+5y=13\end{cases}") == ["2x+3y=11", "-2x+5y=13"]
    assert split_system("2x+3y=11\n-2x+5y=13") == ["2x+3y=11", "-2x+5y=13"]
    assert split_system(r"\begin{aligned}x+y&=2\\x-y&=0\end{aligned}") == ["x+y=2", "x-y=0"]


@pytest.mark.parametrize("bad", [["x+y=2"], ["x^2+y=2", "x-y=0"], ["xy=2", "x-y=0"],
                                 ["x+y+z=1", "x-y=0"], [r"\input{a}=1", "x=1"]])
def test_rejects_unsupported(bad):
    with pytest.raises(UnsupportedMath):
        parse_system(bad)


# ---------- any number of questions ----------
def _stack(numbers, label="Example", x=0, top=0, gap=200):
    return [TextBlock(f"{label} {n}", Box(x, top + i * gap, x + 100, top + i * gap + 20))
            for i, n in enumerate(numbers)]


def test_many_questions_in_one_column():
    blocks = _stack(range(1, 12))                       # Example 1 ... Example 11
    page = Box(0, 0, 1000, 11 * 200)
    for n in range(1, 12):
        region = find_question_region(blocks, n, page)
        assert region.box.y1 == (n - 1) * 200
        assert region.box.y2 == (n * 200 if n < 11 else page.y2)
    # "Example 1" must not match "Example 10" or "Example 11"
    assert find_question_region(blocks, 1, page).heading.text == "Example 1"


def test_grid_of_eight_questions_two_columns():
    # 1 3 5 7 on the left, 2 4 6 8 on the right
    blocks = _stack([1, 3, 5, 7], "Question", x=0) + _stack([2, 4, 6, 8], "Question", x=500)
    page = Box(0, 0, 1000, 800)
    assert find_question_region(blocks, 6, page).box == Box(500, 400, 1000, 600)
    assert find_question_region(blocks, 7, page).box == Box(0, 600, 500, 800)
    assert find_question_region(blocks, 8, page).box == Box(500, 600, 1000, 800)


def test_out_of_order_numbers_still_use_position():
    blocks = _stack([4, 9, 5])                           # numbering doesn't need to be sequential
    region = find_question_region(blocks, 9, Box(0, 0, 1000, 600))
    assert region.box.y1 == 200 and region.box.y2 == 400


def test_right_column_region_excludes_left_column_content():
    blocks = _stack([1, 3], "Question", x=0) + _stack([2, 4], "Question", x=500)
    blocks.append(TextBlock(r"\begin{cases}x+y=2\\x-y=0\end{cases}", Box(150, 250, 450, 300), "formula"))
    region = find_question_region(blocks, 4, Box(0, 0, 1000, 400))
    assert all("cases" not in b.text for b in region.blocks)
    assert any("cases" in b.text for b in find_question_region(blocks, 3, Box(0, 0, 1000, 400)).blocks)