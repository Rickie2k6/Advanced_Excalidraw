"""API routes for creating and running math-writing agents."""

import json

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel, Field

from app.schemas.agent import AgentResponse, AgentStepRequest
from app.services.react_agent import (
    advance,
    agents,
    create_agent,
)


router = APIRouter(prefix="/agents", tags=["agents"])

MAX_FILE_BYTES = 100_000
MAX_SCENE_BYTES = 250_000


class AgentMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    scene: dict = Field(default_factory=dict)


def get_agent(agent_id: str):
    agent = agents.get(agent_id)

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail="Agent not found.",
        )

    return agent


def validate_scene(scene: dict):
    elements = scene.get("elements", [])

    if (
        not isinstance(elements, list)
        or any(not isinstance(item, dict) for item in elements)
    ):
        raise HTTPException(
            status_code=422,
            detail="Scene must contain a list of element objects.",
        )

    size = len(json.dumps(scene).encode("utf-8"))

    if size > MAX_SCENE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Scene is too large.",
        )


@router.post("")
async def create(
    name: str = Form(...),
    instructions: str = Form(...),
    file: UploadFile = File(...),
):
    """Create an agent with an automatically assigned avatar."""
    try:
        name = name.strip()
        instructions = instructions.strip()

        if not name or len(name) > 100:
            raise HTTPException(
                status_code=422,
                detail="Name must contain 1–100 characters.",
            )

        if not instructions or len(instructions) > 8000:
            raise HTTPException(
                status_code=422,
                detail="Instructions must contain 1–8000 characters.",
            )

        if not (file.filename or "").lower().endswith(".txt"):
            raise HTTPException(
                status_code=415,
                detail="This version supports UTF-8 .txt files only.",
            )

        content = await file.read(MAX_FILE_BYTES + 1)

        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="File exceeds 100 KB.",
            )

        try:
            source_text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=422,
                detail="File must use UTF-8 encoding.",
            )

        if not source_text.strip():
            raise HTTPException(
                status_code=422,
                detail="Source file is empty.",
            )

        agent = create_agent(
            name=name,
            instructions=instructions,
            source_text=source_text,
        )

        return {
            "agent_id": agent.id,
            "name": agent.name,
            "avatar_id": agent.avatar_id,
            "status": "ready",
            "message": (
                f"Hi, I am {agent.name}. "
                "I’m ready to help you with your uploaded file."
            ),
        }

    finally:
        await file.close()


@router.post(
    "/{agent_id}/messages",
    response_model=AgentResponse,
)
async def message(
    agent_id: str,
    body: AgentMessageRequest,
):
    """Start an agent turn and return its first action or answer."""
    agent = get_agent(agent_id)

    text = body.message.strip()

    if not text:
        raise HTTPException(
            status_code=422,
            detail="Message cannot be empty.",
        )

    validate_scene(body.scene)

    async with agent.lock:
        if agent.active:
            raise HTTPException(
                status_code=409,
                detail="Finish the pending agent action first.",
            )

        agent.active = True
        agent.steps = 0
        agent.scene = body.scene
        agent.history = agent.history[-40:]

        agent.history.append({
            "role": "user",
            "message": text,
        })

        return await advance(agent)


@router.post(
    "/{agent_id}/results",
    response_model=AgentResponse,
)
async def result(
    agent_id: str,
    body: AgentStepRequest,
):
    """Record browser execution feedback and advance the agent."""
    agent = get_agent(agent_id)

    if body.session_id != agent_id:
        raise HTTPException(
            status_code=422,
            detail="Session ID does not match agent.",
        )

    async with agent.lock:
        # Repeated acknowledgements return the cached response.
        if body.action_id in agent.result_cache:
            return agent.result_cache[body.action_id]

        pending = agent.pending

        if not pending or pending["id"] != body.action_id:
            raise HTTPException(
                status_code=409,
                detail="Action is not pending.",
            )

        if len(body.element_ids) > 100:
            raise HTTPException(
                status_code=422,
                detail="Too many element IDs.",
            )

        if body.success and not body.element_ids:
            raise HTTPException(
                status_code=422,
                detail="Successful math writing must return element IDs.",
            )

        agent.history.append({
            "role": "observation",
            "action_id": body.action_id,
            "success": body.success,
            "element_ids": body.element_ids,
            "error": (body.error or "")[:2000],
        })

        agent.pending = None

        next_response = await advance(agent)

        agent.result_cache[body.action_id] = next_response

        if len(agent.result_cache) > 32:
            oldest = next(iter(agent.result_cache))
            del agent.result_cache[oldest]

        return next_response