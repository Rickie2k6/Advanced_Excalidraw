from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any


# ============================================================
# DATA MODEL
# ============================================================


@dataclass(frozen=True)
class StrokeBox:
    """
    Geometry of one Excalidraw freedraw stroke.

    x, y, width, height are absolute scene coordinates.
    """

    stroke_id: str

    x: float
    y: float

    width: float
    height: float

    created_by_ip: str | None = None
    contributor_id: str | None = None

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def center_x(self) -> float:
        return (
            self.left +
            self.right
        ) / 2

    @property
    def center_y(self) -> float:
        return (
            self.top +
            self.bottom
        ) / 2


# ============================================================
# BASIC GEOMETRY
# ============================================================


def _horizontal_gap(
    a: StrokeBox,
    b: StrokeBox,
) -> float:
    """
    Horizontal distance between two bounding boxes.

    Returns 0 when they overlap horizontally.
    """

    if a.right < b.left:
        return b.left - a.right

    if b.right < a.left:
        return a.left - b.right

    return 0.0


def _vertical_gap(
    a: StrokeBox,
    b: StrokeBox,
) -> float:
    """
    Vertical distance between two bounding boxes.

    Returns 0 when they overlap vertically.
    """

    if a.bottom < b.top:
        return b.top - a.bottom

    if b.bottom < a.top:
        return a.top - b.bottom

    return 0.0


def _vertical_overlap(
    a: StrokeBox,
    b: StrokeBox,
) -> float:
    """
    Number of scene units overlapping vertically.
    """

    return max(
        0.0,
        min(
            a.bottom,
            b.bottom,
        ) -
        max(
            a.top,
            b.top,
        ),
    )


def _horizontal_overlap(
    a: StrokeBox,
    b: StrokeBox,
) -> float:
    """
    Number of scene units overlapping horizontally.
    """

    return max(
        0.0,
        min(
            a.right,
            b.right,
        ) -
        max(
            a.left,
            b.left,
        ),
    )


def _vertical_overlap_ratio(
    a: StrokeBox,
    b: StrokeBox,
) -> float:
    """
    Vertical overlap relative to the smaller stroke.
    """

    smaller_height = max(
        min(
            a.height,
            b.height,
        ),
        1.0,
    )

    return (
        _vertical_overlap(a, b) /
        smaller_height
    )


def _horizontal_overlap_ratio(
    a: StrokeBox,
    b: StrokeBox,
) -> float:
    """
    Horizontal overlap relative to the smaller stroke.
    """

    smaller_width = max(
        min(
            a.width,
            b.width,
        ),
        1.0,
    )

    return (
        _horizontal_overlap(a, b) /
        smaller_width
    )


# ============================================================
# STROKE PARSING
# ============================================================


def _parse_strokes(
    strokes_data: dict[str, Any],
) -> list[StrokeBox]:
    """
    Convert strokes.json data into StrokeBox objects.

    Accepts either:

    {
        "strokes": {
            "id": {...}
        }
    }

    or directly:

    {
        "id": {...}
    }
    """

    if "strokes" in strokes_data:
        raw_strokes = strokes_data.get(
            "strokes",
            {},
        )
    else:
        raw_strokes = strokes_data

    strokes: list[StrokeBox] = []

    for stroke_id, record in raw_strokes.items():

        if record.get(
            "is_deleted",
            False,
        ):
            continue

        try:
            stroke = StrokeBox(
                stroke_id=stroke_id,

                x=float(
                    record["x"]
                ),

                y=float(
                    record["y"]
                ),

                width=float(
                    record["width"]
                ),

                height=float(
                    record["height"]
                ),

                contributor_id=(
                    record.get(
                        "contributor_id"
                    )
                ),

                created_by_ip=(
                    record.get(
                        "created_by_ip"
                    )
                ),
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            # Ignore malformed records instead of
            # crashing the grouping pipeline.
            continue

        strokes.append(
            stroke
        )

    return strokes


# ============================================================
# GROUPING RULE
# ============================================================


def _should_group(
    a: StrokeBox,
    b: StrokeBox,
    typical_height: float,
) -> bool:
    """
    Decide whether two strokes probably belong
    to the same mathematical expression.

    Supports:
    - normal left-to-right writing
    - symbols made from multiple strokes
    - fractions
    - superscripts / exponents
    - nearby mathematical characters
    """

    horizontal_gap = _horizontal_gap(
        a,
        b,
    )

    vertical_gap = _vertical_gap(
        a,
        b,
    )

    vertical_overlap = (
        _vertical_overlap_ratio(
            a,
            b,
        )
    )

    horizontal_overlap = (
        _horizontal_overlap_ratio(
            a,
            b,
        )
    )


    # --------------------------------------------------------
    # Thresholds are relative to typical handwriting size.
    # --------------------------------------------------------

    max_horizontal_gap = max(
        70.0,
        typical_height * 2.4,
    )

    max_vertical_gap = max(
        30.0,
        typical_height * 1.2,
    )

    max_diagonal_gap = max(
        70.0,
        typical_height * 1.8,
    )


    # --------------------------------------------------------
    # RULE 1:
    # Normal equation writing:
    #
    # 2 x + 1 = 0
    #
    # Characters share roughly the same vertical level.
    # --------------------------------------------------------

    if (
        vertical_overlap >= 0.15
        and
        horizontal_gap
        <= max_horizontal_gap
    ):
        return True


    # --------------------------------------------------------
    # RULE 2:
    # Vertically-related math structures:
    #
    #     2
    #   x
    #
    # or fractions:
    #
    #   x + 1
    #   -----
    #     2
    # --------------------------------------------------------

    if (
        horizontal_overlap >= 0.15
        and
        vertical_gap
        <= max_vertical_gap
    ):
        return True


    # --------------------------------------------------------
    # RULE 3:
    # Very close strokes in 2D should generally be grouped.
    #
    # Useful for:
    #   =
    #   +
    #   handwritten x
    #   exponent strokes
    # --------------------------------------------------------

    if (
        horizontal_gap
        <= max_diagonal_gap
        and
        vertical_gap
        <= max_diagonal_gap
    ):
        return True


    return False


# ============================================================
# UNION FIND
# ============================================================


class _UnionFind:
    """
    Small disjoint-set implementation used to
    build connected stroke groups.
    """

    def __init__(
        self,
        size: int,
    ):
        self.parent = list(
            range(size)
        )

        self.rank = [
            0
            for _ in range(size)
        ]

    def find(
        self,
        item: int,
    ) -> int:

        if (
            self.parent[item]
            != item
        ):
            self.parent[item] = (
                self.find(
                    self.parent[item]
                )
            )

        return self.parent[item]

    def union(
        self,
        a: int,
        b: int,
    ) -> None:

        root_a = self.find(a)
        root_b = self.find(b)

        if root_a == root_b:
            return

        if (
            self.rank[root_a]
            <
            self.rank[root_b]
        ):
            root_a, root_b = (
                root_b,
                root_a,
            )

        self.parent[root_b] = (
            root_a
        )

        if (
            self.rank[root_a]
            ==
            self.rank[root_b]
        ):
            self.rank[root_a] += 1


# ============================================================
# GROUP BOUNDING BOX
# ============================================================


def _calculate_group_bbox(
    strokes: list[StrokeBox],
) -> dict[str, float]:

    left = min(
        stroke.left
        for stroke in strokes
    )

    top = min(
        stroke.top
        for stroke in strokes
    )

    right = max(
        stroke.right
        for stroke in strokes
    )

    bottom = max(
        stroke.bottom
        for stroke in strokes
    )

    return {
        "x": left,
        "y": top,
        "width": right - left,
        "height": bottom - top,
    }


# ============================================================
# PUBLIC API
# ============================================================


def group_freedraw_strokes(
    strokes_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Group Excalidraw freedraw strokes into
    candidate equation blocks.

    Input:
        contents of strokes.json

    Output example:

    [
        {
            "stroke_ids": [
                "...",
                "..."
            ],
            "bbox": {
                "x": 100,
                "y": 200,
                "width": 300,
                "height": 60
            },
            "contributors": [
                "1.2.3.4"
            ]
        }
    ]
    """

    strokes = _parse_strokes(
        strokes_data
    )

    if not strokes:
        return []


    # Typical handwriting height allows grouping
    # thresholds to automatically scale with the
    # user's drawing size.

    heights = [
        max(
            stroke.height,
            1.0,
        )
        for stroke in strokes
    ]

    typical_height = median(
        heights
    )


    # --------------------------------------------------------
    # Build graph connectivity using Union-Find.
    # --------------------------------------------------------

    union_find = _UnionFind(
        len(strokes)
    )

    for i in range(
        len(strokes)
    ):

        for j in range(
            i + 1,
            len(strokes),
        ):

            if _should_group(
                strokes[i],
                strokes[j],
                typical_height,
            ):
                union_find.union(
                    i,
                    j,
                )


    # --------------------------------------------------------
    # Collect connected components.
    # --------------------------------------------------------

    groups_by_root: dict[
        int,
        list[StrokeBox],
    ] = {}

    for index, stroke in enumerate(
        strokes
    ):

        root = union_find.find(
            index
        )

        groups_by_root.setdefault(
            root,
            [],
        ).append(
            stroke
        )


    result: list[
        dict[str, Any]
    ] = []


    # --------------------------------------------------------
    # Convert components into equation-block records.
    # --------------------------------------------------------

    for group in groups_by_root.values():

        # Sort approximately in reading order.
        ordered = sorted(
            group,
            key=lambda stroke: (
                stroke.center_y,
                stroke.center_x,
            ),
        )

        stroke_ids = [
            stroke.stroke_id
            for stroke in ordered
        ]

        contributors = sorted(
            {
                (
                    stroke.contributor_id
                    or stroke.created_by_ip
                )
                for stroke in group
                if (
                    stroke.contributor_id
                    or stroke.created_by_ip
                )
            }
        )

        bbox = (
            _calculate_group_bbox(
                group
            )
        )

        result.append(
            {
                "stroke_ids":
                    stroke_ids,

                "bbox":
                    bbox,

                "contributors":
                    contributors,
            }
        )


    # Sort equation groups top-to-bottom,
    # then left-to-right.

    result.sort(
        key=lambda group: (
            group["bbox"]["y"],
            group["bbox"]["x"],
        )
    )

    return result