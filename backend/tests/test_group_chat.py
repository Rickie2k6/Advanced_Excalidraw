"""Group chat tests. The LLM and the agent store are replaced with fakes."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import group_chat as routes
from app.services import group_chat as gc

AGENTS = {
    "a1": gc.Participant("a1", "Ada", "You explain algebra step by step."),
    "a2": gc.Participant("a2", "Rex", "You check answers for mistakes."),
    "a3": gc.Participant("a3", "Mia", "You give short hints."),
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(gc, "resolve_agent", lambda agent_id: AGENTS[agent_id])
    # The fake LLM replies with the agent name it was told to be
    monkeypatch.setattr(gc, "complete",
                        lambda system, prompt: f"{system.split('.')[0].replace('You are ', '')}: hello")
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")  # same as main.py
    return TestClient(app)


def _create(client, ids=("a1", "a2", "a3")):
    r = client.post("/api/group-chats", json={"agent_ids": list(ids), "topic": "x^2 = 9"})
    assert r.status_code == 200
    return r.json()["id"]


def test_agents_take_turns_in_order(client):
    room_id = _create(client)
    r = client.post(f"/api/group-chats/{room_id}/turns", json={"count": 4})
    names = [m["speaker_name"] for m in r.json()["messages"]]
    assert names == ["Ada", "Rex", "Mia", "Ada"]
    assert all(m["text"] == "hello" for m in r.json()["messages"])  # name prefix stripped


def test_human_message_then_replies(client):
    room_id = _create(client)
    r = client.post(f"/api/group-chats/{room_id}/messages", json={"text": "Why is it ±3?", "replies": 2})
    msgs = r.json()["messages"]
    assert [m["role"] for m in msgs] == ["human", "agent", "agent"]
    history = client.get(f"/api/group-chats/{room_id}").json()["messages"]
    assert len(history) == 3


def test_mention_chooses_next_speaker(client):
    room_id = _create(client)
    r = client.post(f"/api/group-chats/{room_id}/messages", json={"text": "@Mia give me a hint", "replies": 1})
    assert r.json()["messages"][1]["speaker_name"] == "Mia"


def test_muted_agent_is_skipped(client):
    room_id = _create(client)
    client.post(f"/api/group-chats/{room_id}/mute", json={"agent_id": "a2", "muted": True})
    r = client.post(f"/api/group-chats/{room_id}/turns", json={"count": 3})
    assert [m["speaker_name"] for m in r.json()["messages"]] == ["Ada", "Mia", "Ada"]


def test_unknown_agent_and_room(client):
    assert client.post("/api/group-chats", json={"agent_ids": ["nope"]}).status_code == 404
    assert client.get("/api/group-chats/missing").status_code == 404