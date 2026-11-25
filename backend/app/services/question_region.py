"""Find "question N" on the board and an empty spot to write the answer.

All boxes are in Excalidraw scene coordinates. Text found inside an inserted
image (OCR, in image pixels) is converted with image_box_to_scene() first.

    region = find_question_region(blocks, 2)
    spot   = find_empty_spot(region, occupied, width, height, anchor=region.content)

Region rule: from the "Example 2" heading down to the next heading below it in
the same column (or the bottom of the page). Headings are read from OCR text,
because Grounding DINO can locate text but cannot read which number it is.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

# "Example 2", "Question 2", "Problem 2", "Exercise 2", "Bài 2", "Câu 2", "Ví dụ 2", "Q2", "2."
HEADING = re.compile(
    r"^\s*(?:(?:example|question|problem|exercise|ex\.?|q|bài|bai|câu|cau|ví\s*dụ|vi\s*du)\s*(\d+)"
    r"|(\d+)\s*[.)])",
    re.IGNORECASE,
)

ASK = re.compile(
    r"(?:example|question|problem|exercise|bài|bai|câu|cau|ví\s*dụ|vi\s*du|số|so|number|#)\s*(\d+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    def grow(self, margin: float) -> "Box":
        return Box(self.x1 - margin, self.y1 - margin, self.x2 + margin, self.y2 + margin)

    def overlaps(self, other: "Box") -> bool:
        return not (self.x2 <= other.x1 or self.x1 >= other.x2 or
                    self.y2 <= other.y1 or self.y1 >= other.y2)

    def inside(self, other: "Box") -> bool:
        return (self.x1 >= other.x1 and self.y1 >= other.y1 and
                self.x2 <= other.x2 and self.y2 <= other.y2)

    def to_dict(self) -> dict:
        return {"x": self.x1, "y": self.y1, "width": self.width, "height": self.height}


@dataclass(frozen=True)
class TextBlock:
    text: str
    box: Box
    kind: str = "text"     # e.g. "title", "text", "formula" from the layout model


@dataclass(frozen=True)
class QuestionRegion:
    number: int
    box: Box                      # the whole area that belongs to the question
    heading: TextBlock
    blocks: tuple                 # text blocks inside the region (heading included)

    @property
    def content(self) -> Optional[Box]:
        """Box around the question's formulas (the system to solve), else around its text."""
        formulas = [b.box for b in self.blocks if b.kind == "formula"] or \
                   [b.box for b in self.blocks if b is not self.heading]
        if not formulas:
            return None
        return Box(min(b.x1 for b in formulas), min(b.y1 for b in formulas),
                   max(b.x2 for b in formulas), max(b.y2 for b in formulas))


# --------------------------------------------------------------------------- #
# Which question did the user ask for?
# --------------------------------------------------------------------------- #
def requested_question_number(question: str) -> Optional[int]:
    """'solve question 2', 'giải câu 2', 'do example 2', 'bài số 2' -> 2."""
    match = ASK.search(question)
    return int(match.group(1)) if match else None


# --------------------------------------------------------------------------- #
# Coordinates
# --------------------------------------------------------------------------- #
def image_box_to_scene(bbox: list[float], image_element: dict,
                       original_width: int, original_height: int) -> Box:
    """[x1, y1, x2, y2] in image pixels -> scene Box (scale 1, angle 0, no crop),
    the same transform as visual_geometry.image_bbox_to_excalidraw without padding."""
    x1, y1, x2, y2 = bbox
    sx = image_element["width"] / original_width
    sy = image_element["height"] / original_height
    ox, oy = image_element["x"], image_element["y"]
    return Box(ox + x1 * sx, oy + y1 * sy, ox + x2 * sx, oy + y2 * sy)


def element_box(element: dict) -> Optional[Box]:
    if element.get("isDeleted"):
        return None
    x, y, w, h = (element.get(k) for k in ("x", "y", "width", "height"))
    if None in (x, y, w, h):
        return None
    # freedraw/line elements can have negative width/height
    return Box(min(x, x + w), min(y, y + h), max(x, x + w), max(y, y + h))


# --------------------------------------------------------------------------- #
# Region
# --------------------------------------------------------------------------- #
_DECORATION = re.compile(r"\\(?:textbf|text|mathbf|mathrm|textit|emph)\s*\{([^{}]*)\}")


def clean_heading_text(text: str) -> str:
    """Strip markdown/LaTeX decoration Paddle may add around a title: '## **Example 1**' -> 'Example 1'."""
    text = _DECORATION.sub(r"\1", text)
    text = text.replace("$", "")
    return re.sub(r"^[\s#*_>\-•·|]+", "", text).replace("**", "").replace("__", "")


def _heading_number(block: TextBlock) -> Optional[int]:
    m = HEADING.match(clean_heading_text(block.text))
    if not m:
        return None
    return int(m.group(1) or m.group(2))


def find_question_region(blocks: Iterable[TextBlock], number: int,
                         page: Optional[Box] = None) -> Optional[QuestionRegion]:
    """Region of question `number`, or None if its heading isn't found.

    `page` is the bounding box of the inserted image (the worksheet page); without it
    the region spans all blocks.
    """
    blocks = list(blocks)
    if not blocks:
        return None
    page = page or Box(min(b.box.x1 for b in blocks), min(b.box.y1 for b in blocks),
                       max(b.box.x2 for b in blocks), max(b.box.y2 for b in blocks))
    headings = [(n, b) for b in blocks if (n := _heading_number(b)) is not None]
    matches = [b for n, b in headings if n == number]
    if not matches:
        return None
    heading = min(matches, key=lambda b: (b.box.y1, b.box.x1))   # topmost if repeated

    # Side-by-side columns: another heading on the same row, to the right, limits the width.
    x1, x2 = page.x1, page.x2
    for _, other in headings:
        if other is heading or not (other.box.y1 < heading.box.y2 and other.box.y2 > heading.box.y1):
            continue
        if other.box.x1 >= heading.box.x2:
            x2 = min(x2, other.box.x1)
        elif other.box.x2 <= heading.box.x1:
            # A question in the right column starts at its own heading: the left
            # column's content extends well past the left heading's text.
            x1 = max(x1, heading.box.x1)

    # The next heading below, in the same column, ends the region.
    below = [b.box.y1 for _, b in headings
             if b is not heading and b.box.y1 >= heading.box.y2 - 1
             and b.box.x1 < x2 and b.box.x2 > x1]
    y2 = min(below, default=page.y2)

    box = Box(x1, heading.box.y1, x2, y2)
    inside = tuple(b for b in blocks if _center_in(b.box, box))
    return QuestionRegion(number, box, heading, inside)


def _center_in(box: Box, region: Box) -> bool:
    cx, cy = (box.x1 + box.x2) / 2, (box.y1 + box.y2) / 2
    return region.x1 <= cx <= region.x2 and region.y1 <= cy <= region.y2


# --------------------------------------------------------------------------- #
# Empty spot
# --------------------------------------------------------------------------- #
# These mirror excalidraw-app/math-freedraw.ts and chatbot-bridge.ts exactly, so the
# space reserved here is the space the canvas will really use.
GLYPH_WIDTH = 12
GLYPH_HEIGHT = 20
CHARACTER_GAP = 8
FRACTION_GAP = 8
FRACTION_PADDING = 5
BASE_MATH_SCALE = 1.5          # chatbot-bridge.ts BASE_MATH_SCALE
STEP_GAP = 35                  # chatbot-bridge.ts STEP_GAP (gap below the previous step)
_FRACTION = re.compile(r"^(.*?)(-?\d+)/(\d+)$")
_EXPONENT = re.compile(r"^(?:\{([+-]?\d+)\}|([+-]?\d+))")


def _layout_text(text: str) -> tuple[float, float]:
    """(width, height) of math-freedraw layoutText(), in glyph units."""
    cursor, raised = 0.0, False
    i = 0
    while i < len(text):
        char = text[i]
        if char == "^":
            match = _EXPONENT.match(text[i + 1:])
            if match:
                exponent_width, _ = _layout_text(match.group(1) or match.group(2))
                cursor += exponent_width * 0.6 + CHARACTER_GAP
                raised = True
                i += 1 + len(match.group(0))
                continue
        cursor += GLYPH_WIDTH if char == " " else GLYPH_WIDTH + CHARACTER_GAP
        i += 1
    width = max(1.0, cursor - CHARACTER_GAP if cursor > 0 else 1.0)
    return width, GLYPH_HEIGHT + (10 if raised else 0)


def measure_math(expression: str, scale: float = 1.0) -> tuple[float, float]:
    """Canvas width/height of one written step (math-freedraw measureMathExpression)."""
    text = re.sub(r"\s+", "", expression)
    match = _FRACTION.match(text)
    if not match:
        w, h = _layout_text(text)
    else:
        prefix, numerator, denominator = match.groups()
        pw, _ = _layout_text(prefix) if prefix else (0.0, 0.0)
        frac = max(_layout_text(numerator)[0], _layout_text(denominator)[0]) + FRACTION_PADDING * 2
        w = pw + (CHARACTER_GAP if prefix else 0) + frac
        h = GLYPH_HEIGHT * 2 + FRACTION_GAP * 2
    render = BASE_MATH_SCALE * scale
    return w * render, h * render


def estimate_steps_size(steps: list[str], scale: float = 1.0) -> tuple[float, float]:
    """Width/height of the solution written as one column of steps."""
    sizes = [measure_math(step, scale) for step in steps]
    width = max(w for w, _ in sizes)
    height = sum(h for _, h in sizes) + STEP_GAP * scale * (len(steps) - 1)
    return width, height


def find_empty_spot(region: Box, occupied: Iterable[Box], width: float, height: float,
                    anchor: Optional[Box] = None, margin: float = 15, step: float = 10) -> Optional[Box]:
    """Top-left-aligned empty box of `width` x `height` inside `region`.

    Preference: to the right of the anchor (the question's equations), then below
    it, then anywhere in the region; closer to the anchor is better.
    """
    blocked = [b.grow(margin) for b in occupied]
    inner = region.grow(-margin)
    if width > inner.width or height > inner.height:
        return None

    best, best_key = None, None
    y = inner.y1
    while y + height <= inner.y2 + 1e-6:
        x = inner.x1
        while x + width <= inner.x2 + 1e-6:
            cand = Box(x, y, x + width, y + height)
            if not any(cand.overlaps(b) for b in blocked):
                key = _preference(cand, anchor)
                if best_key is None or key < best_key:
                    best, best_key = cand, key
            x += step
        y += step
    return best


def _preference(cand: Box, anchor: Optional[Box]) -> tuple:
    if anchor is None:
        return (0, cand.y1, cand.x1)
    right = cand.x1 >= anchor.x2 and cand.y1 < anchor.y2 and cand.y2 > anchor.y1
    below = cand.y1 >= anchor.y2 and cand.x1 < anchor.x2 + anchor.width and cand.x2 > anchor.x1
    rank = 0 if right else 1 if below else 2
    dx = max(anchor.x1 - cand.x2, 0, cand.x1 - anchor.x2)
    dy = max(anchor.y1 - cand.y2, 0, cand.y1 - anchor.y2)
    # align tops when to the right, so the solution starts level with the equations
    align = abs(cand.y1 - anchor.y1) if right else abs(cand.x1 - anchor.x1)
    return (rank, dx + dy + 0.5 * align)


COLUMN_GAP = 30
# Tried in order until one fits: (text scale, number of columns).
# Smallest sizes are for worksheets shown small on the canvas: at 0.35 the handwriting
# is about as tall as the printed worksheet text.
LAYOUTS = ((1.0, 1), (1.0, 2), (0.8, 1), (0.8, 2), (0.8, 3), (0.65, 2), (0.65, 3), (0.5, 3), (0.5, 4),
           (0.4, 3), (0.4, 4), (0.35, 4), (0.35, 5), (0.3, 5))


def _split(steps: list[str], columns: int) -> list[list[str]]:
    per = -(-len(steps) // columns)
    return [steps[i:i + per] for i in range(0, len(steps), per)]


def place_solution(region: QuestionRegion, scene_elements: Iterable[dict], steps: list[str],
                   ignore_element_ids: Iterable[str] = (), layouts=LAYOUTS) -> Optional[dict]:
    """Choose where to write `steps` inside the question region.

    Occupied: the question's own text/formulas and every scene element overlapping
    the region (student strokes, text, shapes), except `ignore_element_ids` (the
    worksheet image itself). If the solution doesn't fit, it is split into columns
    and/or written smaller.

    Returns {"x", "y", "width", "height", "scale", "columns": [{"x", "y", "steps"}]}.
    """
    ignore = set(ignore_element_ids)
    occupied = [b.box for b in region.blocks]
    for element in scene_elements:
        if element.get("id") in ignore:
            continue
        box = element_box(element)
        if box and box.overlaps(region.box):
            occupied.append(box)

    for scale, count in layouts:
        parts = _split(steps, count)
        sizes = [estimate_steps_size(part, scale) for part in parts]
        width = sum(w for w, _ in sizes) + COLUMN_GAP * scale * (len(parts) - 1)
        height = max(h for _, h in sizes)
        spot = find_empty_spot(region.box, occupied, width, height, anchor=region.content)
        if not spot:
            continue
        columns, x = [], spot.x1
        for part, (w, _) in zip(parts, sizes):
            columns.append({"x": x, "y": spot.y1, "steps": part})
            x += w + COLUMN_GAP * scale
        return {"x": spot.x1, "y": spot.y1, "width": width, "height": height,
                "scale": scale, "columns": columns}
    return None


def place_solution_outside_page(page: Box, anchor: Box, scene_elements: Iterable[dict],
                                steps: list[str]) -> dict:
    """Place a full-size column in open canvas to the right of or below the worksheet."""
    margin = 15
    width, height = estimate_steps_size(steps)
    occupied = [box.grow(margin) for element in scene_elements
                if (box := element_box(element)) is not None]

    right_start = page.x2 + margin
    right_y = anchor.y1
    right_x = right_start
    for box in sorted(occupied, key=lambda box: box.x1):
        if Box(right_x, right_y, right_x + width, right_y + height).overlaps(box):
            right_x = box.x2

    below_start = page.y2 + margin
    below_x = anchor.x1
    below_y = below_start
    for box in sorted(occupied, key=lambda box: box.y1):
        if Box(below_x, below_y, below_x + width, below_y + height).overlaps(box):
            below_y = box.y2

    if right_x - right_start <= below_y - below_start:
        x, y, location = right_x, right_y, "beside"
    else:
        x, y, location = below_x, below_y, "below"
    return {"scale": 1.0, "columns": [{"x": x, "y": y, "steps": steps}], "location": location}
