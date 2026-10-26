import json
from typing import Any


FORMULA_LABELS = {
    "display_formula",
    "inline_formula",

    # Fallback in case another
    # Paddle version uses this label.
    "formula",
}


def _result_to_dict(
    result: Any,
) -> dict:
    """
    EN:
    Convert a PaddleOCR result object into a normal
    Python dictionary.

    VI:
    Chuyển PaddleOCR result object thành dictionary
    Python thông thường để dễ xử lý dữ liệu.
    """
    raw = getattr(
        result,
        "json",
        None,
    )

    if callable(raw):
        raw = raw()

    if raw is None:
        raise ValueError(
            "Paddle result does not "
            "contain a JSON result."
        )

    if isinstance(raw, str):
        raw = json.loads(raw)

    if not isinstance(raw, dict):
        raise TypeError(
            "Unexpected Paddle result "
            f"type: {type(raw)}"
        )

    return raw


def _clean_equation(
    content: Any,
) -> str:
    """
    EN:
    Clean the recognized equation text by removing
    unnecessary outer LaTeX wrappers such as
    \\[...\\], \\(...\\), or $...$.

    VI:
    Làm sạch equation được Paddle nhận dạng bằng cách
    loại bỏ các LaTeX wrapper bên ngoài không cần thiết
    như \\[...\\], \\(...\\), hoặc $...$.
    """
    if content is None:
        return ""

    text = str(content).strip()

    wrappers = [
        ("\\[", "\\]"),
        ("\\(", "\\)"),
        ("$$", "$$"),
        ("$", "$"),
    ]

    for start, end in wrappers:
        if (
            text.startswith(start)
            and text.endswith(end)
            and len(text)
            >= len(start) + len(end)
        ):
            text = text[
                len(start):
                -len(end)
            ].strip()

            break

    return text


def _normalize_bbox(
    bbox: Any,
) -> list[float]:
    """
    EN:
    Convert a Paddle bounding box into a standard
    Python list of floating-point coordinates.

    VI:
    Chuyển bounding box từ Paddle thành list Python
    chứa các tọa độ dạng float.
    """
    if bbox is None:
        return []

    if hasattr(
        bbox,
        "tolist",
    ):
        bbox = bbox.tolist()

    return [
        float(value)
        for value in bbox
    ]


def _safe_int(
    value: Any,
):
    """
    EN:
    Safely convert a value to an integer.
    Return None when conversion is not possible.

    VI:
    Chuyển một giá trị sang integer một cách an toàn.
    Trả về None nếu không thể chuyển đổi.
    """
    if value is None:
        return None

    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def extract_formula_blocks(
    result: Any,
):
    """
    EN:
    Extract formula blocks detected by Paddle layout
    detection from a full whiteboard or document image.

    This function is used by the OLD full-whiteboard
    analysis flow.

    VI:
    Lấy các formula block được Paddle layout detection
    phát hiện từ toàn bộ whiteboard hoặc document.

    Function này được sử dụng cho flow phân tích
    full-whiteboard CŨ.
    """
    raw = _result_to_dict(
        result
    )

    payload = raw.get(
        "res",
        raw,
    )

    blocks = payload.get(
        "parsing_res_list",
        [],
    )

    formulas = []
    all_labels = []

    for block in blocks:
        label = str(
            block.get(
                "block_label",
                "",
            )
        )

        all_labels.append(
            label
        )

        equation = _clean_equation(block.get("block_content", ""))
        # Paddle can classify a handwritten or typed equation as ordinary text.
        # Keep equation candidates from those blocks for downstream validation.
        text_equation = label == "text" and "=" in equation
        if label not in FORMULA_LABELS and not text_equation:
            continue

        formulas.append({
            "label": label,

            "bbox": _normalize_bbox(
                block.get(
                    "block_bbox"
                )
            ),

            "equation": equation,

            "block_id":
                _safe_int(
                    block.get(
                        "block_id"
                    )
                ),

            "block_order":
                _safe_int(
                    block.get(
                        "block_order"
                    )
                ),
        })

    return (
        formulas,
        all_labels,
        len(blocks),
    )


def extract_direct_formula(
    result: Any,
) -> str:
    """
    EN:
    Extract one recognized equation from a cropped
    equation image processed with
    use_layout_detection=False and prompt_label="formula".

    Since each crop from Excalidraw represents exactly
    one equation, only one equation string is returned.

    VI:
    Lấy một phương trình được nhận dạng từ ảnh crop
    của một equation khi Paddle chạy với
    use_layout_detection=False và prompt_label="formula".

    Vì mỗi crop từ Excalidraw đại diện cho đúng một
    phương trình, function chỉ trả về một equation string.
    """
    raw = _result_to_dict(
        result
    )

    payload = raw.get(
        "res",
        raw,
    )

    blocks = payload.get(
        "parsing_res_list",
        [],
    )

    # First, prefer blocks explicitly
    # identified as formulas.
    for block in blocks:
        label = str(
            block.get(
                "block_label",
                "",
            )
        ).lower()

        content = _clean_equation(
            block.get(
                "block_content",
                "",
            )
        )

        if (
            label in FORMULA_LABELS
            and content
        ):
            return content

    # Fallback:
    # when layout detection is disabled,
    # Paddle may return a single full-image block.
    for block in blocks:
        content = _clean_equation(
            block.get(
                "block_content",
                "",
            )
        )

        if content:
            return content

    return ""
