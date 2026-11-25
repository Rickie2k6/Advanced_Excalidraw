"""All layout blocks of a worksheet image: titles, text and formulas, with positions.

analyzer.analyze_whiteboard() keeps only formula blocks. Finding "Example 2"
also needs the title/text blocks, so this module runs the same PaddleOCR-VL
layout pass and keeps every block.

Results are cached per image content, because a full-page pass is slow and the
same worksheet is asked about many times.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
from PIL import Image

from app.core.paths import WHITEBOARD_IMAGES_DIR

CACHE_DIR = WHITEBOARD_IMAGES_DIR.parent / "whiteboard_image_analysis" / "paddle_blocks"
CACHE_VERSION = 2          # 2: line-level OCR when the layout pass is too coarse

# Upscale small worksheet images before line OCR (same idea as equation_ocr.py).
LINE_OCR_TARGET_WIDTH = 1800
LINE_OCR_MAX_SCALE = 3.0

_line_ocr = None
_line_ocr_lock = Lock()


# --------------------------------------------------------------------------- #
# Reading Paddle results (pure, testable)
# --------------------------------------------------------------------------- #
def _as_dict(page: Any) -> Any:
    for attr in ("json", "to_dict"):
        value = getattr(page, attr, None)
        if callable(value):
            try:
                value = value()
            except TypeError:
                continue
        if isinstance(value, dict):
            return value
    if isinstance(page, dict):
        return page
    try:
        return dict(page)
    except (TypeError, ValueError):
        return {}


def _find_block_list(data: Any) -> list:
    """Find the list of layout blocks wherever Paddle nests it."""
    if isinstance(data, dict):
        for key in ("parsing_res_list", "layout_parsing_result", "blocks"):
            if isinstance(data.get(key), list):
                return data[key]
        for value in data.values():
            found = _find_block_list(value)
            if found:
                return found
    elif isinstance(data, list):
        for value in data:
            found = _find_block_list(value)
            if found:
                return found
    return []


def _bbox(raw: Any) -> list[float] | None:
    """[x1, y1, x2, y2] from a box or a polygon of points."""
    if raw is None:
        return None
    values = np.asarray(raw, dtype=float).reshape(-1)
    if values.size == 4:
        x1, y1, x2, y2 = values
    elif values.size >= 6 and values.size % 2 == 0:
        xs, ys = values[0::2], values[1::2]
        x1, y1, x2, y2 = xs.min(), ys.min(), xs.max(), ys.max()
    else:
        return None
    return [float(min(x1, x2)), float(min(y1, y2)), float(max(x1, x2)), float(max(y1, y2))]


def _get(block: Any, *names: str) -> Any:
    for name in names:
        value = block.get(name) if isinstance(block, dict) else getattr(block, name, None)
        if value is not None:
            return value
    return None


def kind_of(label: str) -> str:
    label = (label or "").lower()
    if "formula" in label or "equation" in label:
        return "formula"
    if "title" in label or "header" in label:
        return "title"
    return "text"


def extract_all_blocks(page: Any) -> list[dict]:
    """Every block on one Paddle page: {"label", "kind", "text", "bbox"} in image pixels."""
    blocks = []
    for raw in _find_block_list(_as_dict(page)):
        label = str(_get(raw, "block_label", "label") or "")
        text = _get(raw, "block_content", "content", "text", "rec_text") or ""
        bbox = _bbox(_get(raw, "block_bbox", "bbox", "coordinate", "box"))
        if bbox is None or not str(text).strip():
            continue
        blocks.append({"label": label, "kind": kind_of(label), "text": str(text).strip(), "bbox": bbox})
    return blocks


def _find_key(data: Any, key: str) -> Any:
    """First value stored under `key` anywhere in nested dicts/lists."""
    if isinstance(data, dict):
        if key in data:
            return data[key]
        for value in data.values():
            found = _find_key(value, key)
            if found is not None:
                return found
    elif isinstance(data, list):
        for value in data:
            found = _find_key(value, key)
            if found is not None:
                return found
    return None


def extract_lines(result: Any) -> list[tuple[str, list[float]]]:
    """(text, [x1, y1, x2, y2]) for every text line in one PaddleOCR (PP-OCR) result."""
    data = _as_dict(result)
    texts = _find_key(data, "rec_texts")
    boxes = _find_key(data, "rec_boxes")
    if boxes is None or len(np.asarray(boxes, dtype=float).reshape(-1)) == 0:
        boxes = _find_key(data, "rec_polys")
    if texts is None or boxes is None:
        return []
    lines = []
    for text, box in zip(list(texts), list(boxes)):
        bbox = _bbox(box)
        if bbox is not None and str(text).strip():
            lines.append((str(text).strip(), bbox))
    return lines


def is_coarse(blocks: list[dict]) -> bool:
    """The layout pass merged the page (e.g. one big <table>): headings have no own position."""
    if len(blocks) < 3:
        return True
    return any("table" in b["label"].lower() or b["text"].lstrip().startswith("<table") for b in blocks)


def line_kind(text: str) -> str:
    return "formula" if "=" in text else "text"


# --------------------------------------------------------------------------- #
# Running Paddle
# --------------------------------------------------------------------------- #
def _run_layout(image: Image.Image) -> list[dict]:
    # Same settings as analyzer.analyze_whiteboard(), sharing its model and lock.
    from app.core.config import settings
    from app.services.paddle.analyzer import _inference_lock
    from app.services.paddle.model import get_pipeline

    pipeline = get_pipeline()
    with _inference_lock:
        pages = list(pipeline.predict(
            np.asarray(image.convert("RGB")),
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_layout_detection=True,
            use_chart_recognition=False,
            use_seal_recognition=False,
            use_ocr_for_image_block=False,
            format_block_content=False,
            layout_shape_mode="rect",
            layout_threshold=settings.paddle_layout_threshold,
            merge_layout_blocks=False,
            use_queues=False,
        ))
    blocks = []
    for page in pages:
        blocks.extend(extract_all_blocks(page))
    return blocks


def _get_line_ocr():
    global _line_ocr
    if _line_ocr is None:
        from paddleocr import PaddleOCR   # PP-OCR: text detection + recognition, line by line
        options = dict(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            # On CPU Paddle 3.x turns on oneDNN (MKL-DNN), which fails on PP-OCRv6 with
            # "ConvertPirAttribute2RuntimeAttribute not support ...". Plain CPU kernels work.
            enable_mkldnn=False,
        )
        try:
            _line_ocr = PaddleOCR(**options)
        except TypeError:                 # older paddleocr without that option
            options.pop("enable_mkldnn")
            _line_ocr = PaddleOCR(**options)
    return _line_ocr


def _run_lines(image: Image.Image) -> list[dict]:
    """One block per text line, in ORIGINAL image pixels."""
    image = image.convert("RGB")
    scale = max(1.0, min(LINE_OCR_MAX_SCALE, LINE_OCR_TARGET_WIDTH / max(1, image.width)))
    if scale > 1:
        image = image.resize((round(image.width * scale), round(image.height * scale)),
                             Image.Resampling.LANCZOS)
    with _line_ocr_lock:
        results = list(_get_line_ocr().predict(np.asarray(image)))
    blocks = []
    for result in results:
        for text, (x1, y1, x2, y2) in extract_lines(result):
            blocks.append({"label": "ocr_line", "kind": line_kind(text), "text": text,
                           "bbox": [x1 / scale, y1 / scale, x2 / scale, y2 / scale]})
    blocks.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
    return blocks


def _debug_keys(path: Path) -> str:
    """Describe the raw Paddle output shape when no blocks could be extracted."""
    try:
        from app.services.paddle.model import get_pipeline
        from app.services.paddle.analyzer import _inference_lock
        with Image.open(path) as image, _inference_lock:
            page = next(iter(get_pipeline().predict(np.asarray(image.convert("RGB")), use_layout_detection=True,
                                                    use_queues=False)))
        data = _as_dict(page)
        return f"type={type(page).__name__} keys={list(data)[:20]}"
    except Exception as error:   # debugging only
        return f"unavailable ({error!r})"


def analyze_document_blocks(image_path: str | Path) -> dict:
    """{"image_width", "image_height", "blocks": [...]}, cached by image content."""
    path = Path(image_path)
    data = path.read_bytes()
    digest = hashlib.sha1(data).hexdigest()
    cache = CACHE_DIR / f"{digest}.json"
    try:
        cached = json.loads(cache.read_text(encoding="utf-8"))
        if cached.get("version") == CACHE_VERSION:
            return cached
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    with Image.open(path) as image:
        image = image.convert("RGB")
        blocks, source = _run_layout(image), "layout"
        if is_coarse(blocks):
            # The layout model merged the page (e.g. into one <table>): read line by line instead.
            try:
                lines = _run_lines(image)
            except Exception as error:      # missing model, download problem...
                print("[Document Blocks] line OCR unavailable:", repr(error))
                lines = []
            if lines:
                blocks, source = lines, "ocr_lines"
        result = {
            "version": CACHE_VERSION,
            "image_width": image.width,
            "image_height": image.height,
            "source": source,
            "blocks": blocks,
        }

    print(f"[Document Blocks] {path.name}: {len(result['blocks'])} blocks from {source}")
    for block in result["blocks"]:
        print("   ", block["kind"], block["label"], block["bbox"], block["text"][:60])

    if not result["blocks"]:
        print("[Document Blocks] Paddle returned no blocks; not caching. Raw page keys:",
              _debug_keys(path))
        return result
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    tmp.replace(cache)
    return result