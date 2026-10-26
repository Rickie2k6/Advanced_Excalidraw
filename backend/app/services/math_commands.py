"""Extract formula content from explicit write commands before rendering."""

import re


_WRITE_COMMAND = re.compile(
    r"^\s*(?:please\s+)?"
    r"(?:write\b(?:\s+(?:math\b|(?:the\s+)?equation\b))?"
    r"|math\b"
    r"|(?:viết|ghi)\b(?:\s+(?:giúp|hộ)\s+(?:tôi|mình))?"
    r"(?:\s+(?:phương\s+trình|công\s+thức))?)"
    r"(?:\s*[:：]\s*|\s+|$)"
    r"(?P<expression>.*?)"
    r"(?:\s+on\s+(?:the\s+)?whiteboard|\s+lên\s+bảng)?\s*$",
    re.IGNORECASE,
)


def extract_write_math_action(question: str) -> dict | None:
    match = _WRITE_COMMAND.fullmatch(question.strip().rstrip("."))
    if not match:
        return None
    expression = match.group("expression").strip().rstrip(".").strip()
    if not expression:
        return None
    return {"action": "write_math", "expression": expression}
