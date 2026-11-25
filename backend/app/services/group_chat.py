"""Group chat between created agents and the human.

All participants share one message history (a "room"). On each turn we pick
one agent, give the LLM that agent's identity plus the whole conversation,
and append its reply. Human messages go into the same history, so the agents
see them on their next turn.

Agents come from react_agent.agents (created via POST /api/agents).
Replies are generated through llm_service.generate_group_message(), which
uses the same provider order (OpenAI / Claude) as the rest of the chatbot.

Storage is in memory, like react_agent: use one backend worker, and
restarting the backend removes all group chats.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

MAX_KNOWLEDGE_CHARS = 4000   # how much of the agent's source text goes into its prompt
MAX_HISTORY_MESSAGES = 40    # only the most recent messages are sent to the LLM


# --------------------------------------------------------------------------- #
# Connections to the existing project
# --------------------------------------------------------------------------- #
@dataclass
class Participant:
    id: str
    name: str
    instructions: str
    knowledge: str = ""      # Agent.source_text (the uploaded text file)
    avatar_id: str = ""      # Agent.avatar_id, e.g. "human-03"


def resolve_agent(agent_id: str) -> Participant:
    """Return a participant for an agent created via POST /api/agents."""
    # Imported here so this module (and its tests) don't load the ReAct module at import time.
    from app.services.react_agent import agents

    agent = agents.get(agent_id)
    if agent is None:
        raise KeyError(agent_id)
    return Participant(
        id=agent.id,
        name=agent.name,
        instructions=agent.instructions,
        knowledge=agent.source_text,
        avatar_id=agent.avatar_id,
    )


def complete(system: str, prompt: str) -> str:
    """Generate one chat message with the configured LLM provider."""
    from app.services.llm_service import generate_group_message

    return generate_group_message(system, prompt)


# --------------------------------------------------------------------------- #
# Room state
# --------------------------------------------------------------------------- #
@dataclass
class ChatMessage:
    id: str
    role: str                # "agent" or "human"
    speaker_id: str
    speaker_name: str
    text: str


@dataclass
class Room:
    id: str
    topic: str
    participants: list[Participant]
    muted: set[str] = field(default_factory=set)
    messages: list[ChatMessage] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock, repr=False)

    def active(self) -> list[Participant]:
        return [p for p in self.participants if p.id not in self.muted]


_rooms: dict[str, Room] = {}


def create_room(agent_ids: list[str], topic: str = "",
                participants: Optional[list[Participant]] = None) -> Room:
    people = participants if participants is not None else [resolve_agent(a) for a in agent_ids]
    if not people:
        raise ValueError("A group chat needs at least one agent.")
    room = Room(id=uuid.uuid4().hex[:12], topic=topic, participants=people)
    _rooms[room.id] = room
    return room


def get_room(room_id: str) -> Room:
    try:
        return _rooms[room_id]
    except KeyError:
        raise KeyError(f"Group chat {room_id} does not exist.")


def add_human_message(room: Room, text: str) -> ChatMessage:
    msg = ChatMessage(uuid.uuid4().hex[:12], "human", "human", "Human", text.strip())
    room.messages.append(msg)
    return msg


# --------------------------------------------------------------------------- #
# Turn logic
# --------------------------------------------------------------------------- #
def pick_next(room: Room) -> Optional[Participant]:
    """@Name in the last message wins; otherwise agents take turns in order."""
    active = room.active()
    if not active:
        return None
    last = room.messages[-1] if room.messages else None
    if last:
        for p in active:
            if p.id != last.speaker_id and re.search(rf"@{re.escape(p.name)}\b", last.text, re.I):
                return p
    last_agent = next((m for m in reversed(room.messages) if m.role == "agent"), None)
    if last_agent is None:
        return active[0]
    ids = [p.id for p in active]
    idx = ids.index(last_agent.speaker_id) if last_agent.speaker_id in ids else -1
    return active[(idx + 1) % len(active)]


def _build_prompt(room: Room, agent: Participant) -> tuple[str, str]:
    others = ", ".join(p.name for p in room.active() if p.id != agent.id) or "nobody else"
    system = (
        f"You are {agent.name}.\n{agent.instructions}\n\n"
        + (f"Reference material you know:\n{agent.knowledge[:MAX_KNOWLEDGE_CHARS]}\n\n" if agent.knowledge else "")
        + f"You are in a group chat with other agents ({others}) and a student who appears as 'Human'.\n"
        + (f"Topic: {room.topic}\n" if room.topic else "")
        + "Write ONLY your own next message, 1-4 sentences, in character. React to what others just said "
          "and address them by name. If the Human asked something, answer them first. "
          "Never prefix your message with your name and never write lines for other participants."
    )
    history = room.messages[-MAX_HISTORY_MESSAGES:]
    transcript = "\n".join(f"{m.speaker_name}: {m.text}" for m in history) or "(The chat is empty. Start it.)"
    return system, f"Chat so far:\n{transcript}\n\nWrite your next message as {agent.name}."


def run_turns(room: Room, count: int) -> list[ChatMessage]:
    """Let agents speak `count` times. Returns only the new messages."""
    new: list[ChatMessage] = []
    with room.lock:   # one conversation step at a time per room
        for _ in range(max(0, count)):
            agent = pick_next(room)
            if agent is None:
                break
            system, prompt = _build_prompt(room, agent)
            text = complete(system, prompt).strip()
            text = re.sub(rf"^\**{re.escape(agent.name)}\**\s*:\s*", "", text, flags=re.I)
            msg = ChatMessage(uuid.uuid4().hex[:12], "agent", agent.id, agent.name, text)
            room.messages.append(msg)
            new.append(msg)
    return new