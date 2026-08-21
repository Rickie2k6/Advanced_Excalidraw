from typing import Optional

from pydantic import BaseModel


class EquationBox(BaseModel):
    id: int

    label: str

    bbox: list[float]

    equation: str

    block_id: Optional[int] = None

    block_order: Optional[int] = None


class AnalysisResult(BaseModel):
    timestamp: str

    image_width: int
    image_height: int

    box_count: int

    boxes: list[EquationBox]

    all_block_count: int

    all_block_labels: list[str]


class ChatResponse(BaseModel):
    question: str

    answer: str

    analysis: AnalysisResult | None = None