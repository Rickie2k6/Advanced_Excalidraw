"""Group chat endpoints: agents talk to each other, and the human can join in.

POST /api/group-chats                      create a room from existing agent IDs
GET  /api/group-chats/{room_id}            full history
POST /api/group-chats/{room_id}/messages   human message, then N agent replies
POST /api/group-chats/{room_id}/turns      agents talk among themselves for N turns
POST /api/group-chats/{room_id}/mute       mute or unmute one agent

Routes are plain `def` so FastAPI runs the blocking LLM calls in a thread pool.
"""
import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from app.schemas.group_chat import (
    CreateGroupChatIn, GroupChatOut, GroupMessageOut, HumanMessageIn, MuteIn, NewMessagesOut, RunTurnsIn,
)
from app.services import group_chat as gc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/group-chats", tags=["group-chat"])


def _room_or_404(room_id: str) -> gc.Room:
    try:
        return gc.get_room(room_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


def _room_out(room: gc.Room) -> GroupChatOut:
    return GroupChatOut(
        id=room.id,
        topic=room.topic,
        participants=[{"id": p.id, "name": p.name, "avatar_id": p.avatar_id, "muted": p.id in room.muted} for p in room.participants],
        messages=[asdict(m) for m in room.messages],
    )


def _run(room: gc.Room, count: int) -> NewMessagesOut:
    try:
        new = gc.run_turns(room, count)
    except Exception as error:  # LLM/provider errors
        # Log only the error type: provider messages may contain request data.
        logger.error("Group chat turn failed: room_id=%s error_type=%s", room.id, type(error).__name__)
        raise HTTPException(
            status_code=502,
            detail="An agent couldn't reply. Check the backend logs and provider configuration.",
        )
    return NewMessagesOut(messages=[asdict(m) for m in new])


@router.post("", response_model=GroupChatOut)
def create_group_chat(body: CreateGroupChatIn):
    try:
        room = gc.create_room(body.agent_ids, body.topic)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"Agent {e} does not exist.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _room_out(room)


@router.get("/{room_id}", response_model=GroupChatOut)
def get_group_chat(room_id: str):
    return _room_out(_room_or_404(room_id))


@router.post("/{room_id}/messages", response_model=NewMessagesOut)
def send_human_message(room_id: str, body: HumanMessageIn):
    room = _room_or_404(room_id)
    human = gc.add_human_message(room, body.text)
    result = _run(room, body.replies)
    result.messages.insert(0, GroupMessageOut(**asdict(human)))
    return result


@router.post("/{room_id}/turns", response_model=NewMessagesOut)
def run_agent_turns(room_id: str, body: RunTurnsIn):
    return _run(_room_or_404(room_id), body.count)


@router.post("/{room_id}/mute", response_model=GroupChatOut)
def mute_agent(room_id: str, body: MuteIn):
    room = _room_or_404(room_id)
    (room.muted.add if body.muted else room.muted.discard)(body.agent_id)
    return _room_out(room)