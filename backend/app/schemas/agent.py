from typing import Literal
from pydantic import BaseModel, Field


class AgentAction(BaseModel):
    id: str
    type: Literal["write_math"]
    expression: str


class AgentResponse(BaseModel):
    session_id: str
    status: Literal[
        "action_required",
        "completed",
        "failed",
    ]
    action: AgentAction | None = None
    message: str = ""


class AgentStepRequest(BaseModel):
    session_id: str
    action_id: str
    success: bool
    element_ids: list[str] = Field(
        default_factory=list
    )
    error: str | None = None