"""'solve question 2' -> write the solution in an empty spot near question 2.

    result = await solve_question_request(question, scene)
    if result is not None:
        result.action    # write_math_steps action for the widget, or None
        result.message   # what to tell the user when there is no action

Flow:
  1. read the question number from the message
  2. for every worksheet image on the board, get its layout blocks (Paddle, cached)
     and look for the "Example N" / "Question N" heading
  3. read the equation(s) inside that region
     (Paddle formula blocks; Grounding DINO + Paddle as a fallback)
  4. solve (any degree up to 6, linear or non-linear systems) and verify every
     answer in every original equation
  5. find an empty spot in the region or outside the worksheet and return the action
"""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image
from starlette.concurrency import run_in_threadpool

from app.core.paths import WHITEBOARD_IMAGES_DIR
from app.reasoning.general_solver import Problem, Solution, describe_kind, parse_problem, solve_problem
from app.reasoning.linear_system import split_system
from app.reasoning.problem_selection import UnsupportedMath
from app.services.question_region import (
    Box, QuestionRegion, TextBlock, find_question_region, image_box_to_scene,
    place_solution, place_solution_outside_page, requested_question_number,
)

SOLVE_WORDS = re.compile(
    # "do" is left out on purpose: "what do you think about question 2" isn't a solve request.
    r"\b(solve|solving|answer|work\s*out)\b|giải|làm|tính",
    re.IGNORECASE,
)


@dataclass
class QuestionSolveResult:
    action: Optional[dict] = None
    message: str = ""
    debug: dict = field(default_factory=dict)


@dataclass
class _Candidate:
    region: QuestionRegion
    page: Box
    element: dict
    image_path: Path
    image_size: tuple[int, int]
    raw_blocks: list = field(default_factory=list)       # Paddle blocks, image pixels
    reading: Optional[dict] = None                         # what the LLM read, if it was asked


def is_question_solve_request(question: str) -> Optional[int]:
    """Question number if the message asks to solve a numbered question, else None."""
    number = requested_question_number(question)
    if number is None or not SOLVE_WORDS.search(question):
        return None
    return number


# --------------------------------------------------------------------------- #
# Images on the board
# --------------------------------------------------------------------------- #
_EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


def resolve_image_path(file_id: str, files: dict) -> Optional[Path]:
    """Same lookup as chat.py: scene dataURL first, then saved backend copy."""
    data_url = (files.get(file_id) or {}).get("dataURL")
    if data_url:
        match = re.match(r"data:(image/[^;]+);base64,(.+)", data_url, re.DOTALL)
        if match:
            WHITEBOARD_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            path = WHITEBOARD_IMAGES_DIR / f"{file_id}{_EXTENSIONS.get(match.group(1), '.png')}"
            path.write_bytes(base64.b64decode(match.group(2)))
            return path
    matches = list(WHITEBOARD_IMAGES_DIR.glob(f"{file_id}.*"))
    return matches[0] if matches else None


def _scene_parts(scene) -> tuple[list[dict], dict]:
    if isinstance(scene, dict):
        return scene.get("elements", []) or [], scene.get("files", {}) or {}
    if isinstance(scene, list):
        return scene, {}
    return [], {}


def _image_elements(elements: list[dict]) -> list[dict]:
    return [e for e in elements
            if e.get("type") == "image" and not e.get("isDeleted") and e.get("fileId")]


def _scene_to_image(box: Box, element: dict, size: tuple[int, int]) -> list[float]:
    w, h = size
    sx, sy = w / element["width"], h / element["height"]
    return [max(0, (box.x1 - element["x"]) * sx), max(0, (box.y1 - element["y"]) * sy),
            min(w, (box.x2 - element["x"]) * sx), min(h, (box.y2 - element["y"]) * sy)]


# --------------------------------------------------------------------------- #
# Reading the system inside the region
# --------------------------------------------------------------------------- #
# Characters the canvas can draw (see excalidraw-app/math-freedraw.ts).
DRAWABLE = re.compile(r"^[0-9xyzXYZ+\-=()/^.,≈Δ ]+$")

SUPPORTED = ("one equation of degree 1 to 6 (for example x^2-5x+6=0), or a system of equations "
             "in x, y and z (for example 2x+3y=11, -2x+5y=13)")


def clean_equation_line(text: str) -> str:
    """OCR of a handwritten/printed system often keeps the brace: '{2x + 3y = 11', '|-2x+5y=13'."""
    text = re.sub(r"^[\s{\[|]+", "", text.strip())
    if text.startswith("(") and text.count("(") > text.count(")"):
        text = text[1:]
    return text.rstrip(" }]|,;")


def problem_from_blocks(region: QuestionRegion):
    """Read the problem inside the region. Returns (Problem, source_text) or (None, reason).

    Tries, for formula blocks and then for text blocks containing '=':
      * a single block (one equation, or a whole system written as cases/array)
      * all the blocks together, top to bottom (a system written line by line)
    """
    ordered = sorted((b for b in region.blocks if b is not region.heading),
                     key=lambda b: (b.box.y1, b.box.x1))
    formulas = [b for b in ordered if b.kind == "formula"]
    texts = [b for b in ordered if b.kind != "formula" and "=" in b.text]
    last_error = "No equations were found in this question."

    for group in (formulas, texts):
        attempts = []
        if len(group) > 1:
            lines = [clean_equation_line(line) for b in group for line in split_system(b.text)]
            attempts.append((lines, "\n".join(lines)))
        for b in group:
            attempts.append((b.text, b.text))
            cleaned = clean_equation_line(b.text)
            if cleaned != b.text:
                attempts.append((cleaned, cleaned))
        for source, shown in attempts:
            try:
                return parse_problem(source), shown
            except UnsupportedMath as error:
                last_error = str(error)
    return None, last_error


def _system_with_dino(candidate: _Candidate):
    """Fallback: Grounding DINO finds the equations in the region, Paddle reads them."""
    from app.services.detector import detect_target
    from app.services.paddle.analyzer import analyze_equation_images

    with Image.open(candidate.image_path) as img:
        page = img.convert("RGB")
    rx1, ry1, rx2, ry2 = _scene_to_image(candidate.region.box, candidate.element, candidate.image_size)
    crop = page.crop((int(rx1), int(ry1), int(rx2), int(ry2)))
    tmp = candidate.image_path.with_name(f"{candidate.image_path.stem}_q{candidate.region.number}.png")
    crop.save(tmp)
    try:
        detections = detect_target(str(tmp), "system of equations. math equation.")
    finally:
        tmp.unlink(missing_ok=True)
    if not detections:
        return None, "Grounding DINO found no equations in this question."
    best = max(detections, key=lambda d: d["score"])
    x1, y1, x2, y2 = best["bbox"]
    equation_crop = crop.crop((int(x1), int(y1), int(x2), int(y2)))
    result = analyze_equation_images([equation_crop], [{"id": 1, "bbox": [x1, y1, x2 - x1, y2 - y1]}])
    latex = (result.get("boxes") or [{}])[0].get("equation") or ""
    try:
        return parse_problem(latex), latex
    except UnsupportedMath as error:
        return None, f"Read `{latex}`, but {error}"


# --------------------------------------------------------------------------- #
# ChatGPT/Claude: understand what Paddle read (never positions, never solving)
# --------------------------------------------------------------------------- #
LLM_SYSTEM = """You help a whiteboard tutor read a worksheet page.
You receive the text blocks that OCR found on the page, each with an index.
Your job is only to UNDERSTAND the text:
  1. Find every numbered question/example heading on the page (e.g. "Example 2",
     "## Question 3", "Bài 4", "2."), even if OCR added symbols or merged it with
     other text. Give its question number and the index of the block containing it.
  2. Copy the equation(s) that the requested question asks to solve, as plain text:
     one equation per item, ^ for powers, no LaTeX, e.g. "7x-2y=5". Copy the
     numbers exactly as written. You may only fix obvious OCR formatting.
Never solve anything. Never invent equations or numbers that are not in the blocks.
If the requested question is not on the page, set question_found to false.
Reply with JSON only."""


def _plain(text: str) -> str:
    """Table HTML from the layout model -> plain text the LLM can read."""
    text = re.sub(r"</t[dh]>|</tr>|<br\s*/?>", "\n", text)
    return re.sub(r"<[^>]+>", "", text).replace("\\n", "\n")


def _llm_prompt(blocks: list[dict], number: int) -> str:
    listing = "\n".join(
        f"[{i}] {b['kind']} at {[round(v) for v in b['bbox']]}: {json.dumps(_plain(b['text'])[:1500], ensure_ascii=False)}"
        for i, b in enumerate(blocks))
    return (f"Requested question: {number}\n\nOCR blocks (index, layout kind, position in pixels, text):\n"
            f"{listing}\n\nReply with this JSON:\n"
            '{"headings": [{"number": 1, "block": 0}], "question_found": true, '
            '"equation_blocks": [5], "equations": ["7x-2y=5", "7x-3y=4"]}')


def _parse_json_reply(raw: str) -> Optional[dict]:
    raw = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.MULTILINE).strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        data = json.loads(match.group(0) if match else raw)
    except (json.JSONDecodeError, AttributeError):
        return None
    return data if isinstance(data, dict) else None


def _llm_locate(blocks: list[dict], number: int) -> Optional[dict]:
    """Ask the configured LLM (same provider as the rest of the chatbot) to read the page.

    Returns {"headings": {number: block_index}, "equations": [...], "equation_blocks": [...],
    "question_found": bool} with every index checked, or None if the LLM is unavailable.
    """
    from app.services.llm_service import locate_question

    data = _parse_json_reply(locate_question(_llm_prompt(blocks, number), LLM_SYSTEM))
    if data is None:
        print("[Question Solver] LLM reply was not JSON")
        return None
    valid = range(len(blocks))
    headings = {}
    for item in data.get("headings") or []:
        try:
            n, i = int(item["number"]), int(item["block"])
        except (KeyError, TypeError, ValueError):
            continue
        if i in valid:
            headings[n] = i
    equations = [str(e).strip() for e in data.get("equations") or [] if str(e).strip()]
    equation_blocks = [int(i) for i in data.get("equation_blocks") or []
                       if isinstance(i, (int, str)) and str(i).isdigit() and int(i) in valid]
    result = {"headings": headings, "equations": equations, "equation_blocks": equation_blocks,
              "question_found": bool(data.get("question_found", number in headings))}
    print("[Question Solver] LLM read:", result)
    return result


def _numbers(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?", text)


def grounded(equations: list[str], source_text: str) -> bool:
    """Every number the LLM wrote must appear in what OCR actually read (no invented equations)."""
    available = _numbers(source_text)
    for equation in equations:
        for n in _numbers(equation):
            if n in available:
                available.remove(n)
            elif n not in ("0", "1"):      # implicit coefficients / "=0" forms
                return False
    return bool(equations)


async def _answer_without_region(llm_cache: dict, analyzed: dict, number: int) -> Optional[QuestionSolveResult]:
    """The question's equations were read (by the LLM, checked against the OCR text) but its
    area on the page couldn't be located: answer in the chat instead of writing on the board."""
    for (file_id, n), reading in llm_cache.items():
        if n != number or not reading or not reading["question_found"] or not reading["equations"]:
            continue
        page_text = " ".join(_plain(b["text"]) for b in analyzed.get(file_id, {}).get("blocks", []))
        if not grounded(reading["equations"], page_text):
            print("[Question Solver] LLM equations not found in the OCR text; ignored:", reading["equations"])
            continue
        try:
            problem = parse_problem(reading["equations"])
            solution = await run_in_threadpool(solve_problem, problem)
        except Exception as error:
            print("[Question Solver] fallback solve failed:", repr(error))
            continue
        if not solution.verified:
            continue
        read_as = ", ".join(reading["equations"])
        steps = "; ".join(solution.steps)
        print("[Question Solver] answered in chat only:", {"question": number, "answer": solution.answer})
        return QuestionSolveResult(message=(
            f"Question {number} (read as {read_as}): {solution.answer}. "
            f"Steps: {steps}. I couldn't find where question {number} sits on the page, "
            "so I didn't write on the board."))
    return None


async def _llm_reading(cache: dict, file_id: str, raw_blocks: list[dict], number: int) -> Optional[dict]:
    key = (file_id, number)
    if key not in cache:
        try:
            cache[key] = await run_in_threadpool(_llm_locate, raw_blocks, number)
        except Exception as error:      # no API key, provider down, etc.: carry on without it
            print("[Question Solver] LLM reading unavailable:", repr(error))
            cache[key] = None
    return cache[key]


def _relabel(blocks: list[TextBlock], headings: dict[int, int]) -> list[TextBlock]:
    """Give the blocks the LLM identified as headings a clean 'Question N' text."""
    by_index = {i: n for n, i in headings.items()}
    return [TextBlock(f"Question {by_index[i]}", b.box, "title") if i in by_index else b
            for i, b in enumerate(blocks)]


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
async def solve_question_request(question: str, scene) -> Optional[QuestionSolveResult]:
    """None if the message isn't 'solve question N'. Otherwise an action or a message."""
    number = is_question_solve_request(question)
    if number is None:
        return None

    from app.services.paddle.document_blocks import analyze_document_blocks

    elements, files = _scene_parts(scene)
    images = _image_elements(elements)
    if not images:
        return QuestionSolveResult(message=(
            f"I couldn't find a worksheet on the whiteboard to look for question {number}. "
            "Insert the worksheet image and try again."))

    candidates: list[_Candidate] = []
    analyzed: dict[str, dict] = {}
    llm_cache: dict = {}
    for element in images:
        file_id = element["fileId"]
        if element.get("angle") or element.get("crop"):
            print(f"[Question Solver] Skipping rotated/cropped image {element.get('id')}")
            continue
        path = resolve_image_path(file_id, files)
        if path is None:
            continue
        if file_id not in analyzed:
            analyzed[file_id] = await run_in_threadpool(analyze_document_blocks, str(path))
        doc = analyzed[file_id]
        size = (doc["image_width"], doc["image_height"])
        blocks = [TextBlock(b["text"], image_box_to_scene(b["bbox"], element, *size), b["kind"])
                  for b in doc["blocks"]]
        page = Box(element["x"], element["y"], element["x"] + element["width"], element["y"] + element["height"])
        region = find_question_region(blocks, number, page)
        reading = None
        if region is None and doc["blocks"]:
            # The heading wasn't recognised from the raw OCR text: let the LLM read the page.
            reading = await _llm_reading(llm_cache, file_id, doc["blocks"], number)
            if reading and reading["question_found"] and number in reading["headings"]:
                region = find_question_region(_relabel(blocks, reading["headings"]), number, page)
        if region is not None:
            candidates.append(_Candidate(region, page, element, path, size, doc["blocks"], reading))

    if not candidates:
        fallback = await _answer_without_region(llm_cache, analyzed, number)
        if fallback is not None:
            return fallback
        for file_id, doc in analyzed.items():
            print(f"[Question Solver] question {number} not found in {file_id}. "
                  f"Paddle read {len(doc['blocks'])} blocks:")
            for block in doc["blocks"][:60]:
                print("   ", block["kind"], [round(v) for v in block["bbox"]], repr(block["text"][:80]))
        return QuestionSolveResult(message=(
            f"I couldn't find question {number} on the worksheet. "
            "Check that its heading (for example \"Example 2\") is visible on the board."))
    if len(candidates) > 1:
        return QuestionSolveResult(message=(
            f"I found question {number} on {len(candidates)} different pages. "
            "Please remove the extra copy or tell me which page you mean."))

    candidate = candidates[0]
    region = candidate.region
    problem, source = problem_from_blocks(region)
    read_by_llm = False
    if problem is None and candidate.raw_blocks:
        reading = candidate.reading or await _llm_reading(
            llm_cache, candidate.element["fileId"], candidate.raw_blocks, number)
        if reading and reading["equations"]:
            region_text = " ".join(b.text for b in region.blocks)
            if not grounded(reading["equations"], region_text):
                print("[Question Solver] LLM equations not found in the OCR text; ignored:", reading["equations"])
            else:
                try:
                    problem, source = parse_problem(reading["equations"]), "\n".join(reading["equations"])
                    read_by_llm = True
                except UnsupportedMath as error:
                    source = f"{', '.join(reading['equations'])}: {error}"
    if problem is None:
        try:
            problem, source = await run_in_threadpool(_system_with_dino, candidate)
        except Exception as error:   # detector/model problems shouldn't crash the chat
            print("[Question Solver] DINO fallback failed:", repr(error))
            problem = None
    if problem is None:
        return QuestionSolveResult(message=(
            f"I found question {number}, but I couldn't read an equation I can solve in it "
            f"({source}). I can solve {SUPPORTED}."))

    try:
        solution: Solution = await run_in_threadpool(solve_problem, problem)
    except Exception as error:
        print("[Question Solver] solver failed:", repr(error))
        return QuestionSolveResult(message=(
            f"I read question {number} as `{source}`, but I couldn't solve it. I can solve {SUPPORTED}."))
    if not solution.verified:
        return QuestionSolveResult(message=(
            f"I read question {number} as `{source}`, but my answer didn't check out, "
            "so I didn't write it. The equations may have been misread."))
    undrawable = [step for step in solution.steps if not DRAWABLE.match(step)]
    if undrawable:
        return QuestionSolveResult(message=(
            f"Question {number}: {solution.answer}. I couldn't write the steps on the board "
            f"because `{undrawable[0]}` uses symbols the canvas can't draw yet."))

    placement = place_solution(region, elements, solution.steps,
                               ignore_element_ids=[candidate.element.get("id")])
    if placement is None:
        placement = place_solution_outside_page(
            candidate.page, region.content or region.heading.box, elements, solution.steps,
        )

    action = {
        "action": "write_math_steps",
        "steps": solution.steps,
        "columns": placement["columns"],
        "scale": placement["scale"],
        "question_number": number,
        "answer": solution.answer,
        "read_as": problem.sources if read_by_llm else [],
        "problem_type": describe_kind(problem),
        "approximate": solution.approximate,
        "explanations": solution.explanations,
        "region": region.box.to_dict(),
        "source_equation_id": f"question-{number}",
    }
    if "location" in placement:
        action["placement"] = placement["location"]
    print("[Question Solver]", {k: action[k] for k in ("question_number", "answer", "steps", "columns")})
    return QuestionSolveResult(action=action, debug={"source": source})
