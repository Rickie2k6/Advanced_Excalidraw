from pydantic import BaseModel, Field


class CreateGroupChatIn(BaseModel):
    agent_ids: list[str] = Field(..., min_length=1, description="IDs returned by POST /api/agents")
    topic: str = ""


class HumanMessageIn(BaseModel):
    text: str = Field(..., min_length=1)
    replies: int = Field(3, ge=0, le=10, description="How many agent replies to generate after the message")


class RunTurnsIn(BaseModel):
    count: int = Field(1, ge=1, le=12)


class MuteIn(BaseModel):
    agent_id: str
    muted: bool = True


class ParticipantOut(BaseModel):
    id: str
    name: str
    avatar_id: str = ""
    muted: bool


class GroupMessageOut(BaseModel):
    id: str
    role: str
    speaker_id: str
    speaker_name: str
    text: str


class GroupChatOut(BaseModel):
    id: str
    topic: str
    participants: list[ParticipantOut]
    messages: list[GroupMessageOut]


class NewMessagesOut(BaseModel):
    messages: list[GroupMessageOut]