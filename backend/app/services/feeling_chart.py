"""Deterministic face locations for the verified FEELING CHART asset."""

from hashlib import sha256
from pathlib import Path


# Bind the geometry to image content, never to an LLM's description or filename.
CHART_SHA256 = "1a090add7fa04ecb38050e06a35864c77997ecef5e4f843a57e52a90ddcfa0e8"
LAYOUT = (
    ("AFRAID", "SAD", "WORRIED", "HAPPY"),
    ("ASHAMED", "DISTRACTED", "EMBARRASSED", "NERVOUS"),
    ("CONFIDENT", "FRUSTRATED", "GUILTY", "LONELY"),
    ("EXHAUSTED", "SURPRISED", "SHY", "CONFUSED"),
    ("PROUD", "SHOCKED", "ANGRY", "OVERWHELMED"),
)

# Measured face bounds in the 1001 x 1440 source, excluding title and badges.
# The rows are slightly uneven, so use explicit centers rather than divide
# the entire poster into equal cells (which would include the header).
_COLUMN_CENTERS = (155, 383, 605, 833)
_ROW_CENTERS = (226, 491, 742, 991, 1246)


def is_known_feeling_chart(image_path: str) -> bool:
    return sha256(Path(image_path).read_bytes()).hexdigest() == CHART_SHA256


def resolve_feeling_label(label: str | None) -> dict | None:
    """Return source pixel bounds using only a label; indices stay zero-based."""
    if not isinstance(label, str):
        return None
    label = label.strip().upper()
    for row_index, row in enumerate(LAYOUT):
        if label in row:
            col_index = row.index(label)
            x, y = _COLUMN_CENTERS[col_index], _ROW_CENTERS[row_index]
            return {"bbox": [x - 78, y - 78, x + 78, y + 78], "label": label}
    return None
