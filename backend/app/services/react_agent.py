"""Agent creation and action–observation orchestration.

Loads the adapted chatbot agent from the server's ReAct folder.

Development storage:
- Agents are stored in memory.
- Use one backend worker.
- Restarting the backend removes agents and avatar assignments.
"""

import asyncio
import importlib.util
import logging
import random

from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import uuid4

from starlette.concurrency import run_in_threadpool

from app.services.llm_service import decide_agent_action


logger = logging.getLogger(__name__)

MAX_STEPS = 8
MAX_HISTORY_ITEMS = 40

HUMAN_AVATARS = [
    f"human-{number:02d}"
    for number in range(1, 13)
]

REACT_MODULE_PATH = Path(
    "/home/student/chuynh/ReAct/ReAct/chatbot_agent.py"
)


def load_react_module() -> ModuleType:
    """Load next_action() from the adapted ReAct module."""
    if not REACT_MODULE_PATH.is_file():
        raise RuntimeError(
            f"ReAct module not found: {REACT_MODULE_PATH}. "
            "Create chatbot_agent.py before starting the backend."
        )

    spec = importlib.util.spec_from_file_location(
        "talk_sketch_react",
        REACT_MODULE_PATH,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Cannot load ReAct module: {REACT_MODULE_PATH}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not callable(getattr(module, "next_action", None)):
        raise RuntimeError(
            "ReAct chatbot_agent.py must define "
            "next_action(context, decide)."
        )

    return module


react_module = load_react_module()


@dataclass
class Agent:
    name: str
    instructions: str
    source_text: str

    avatar_id: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)

    history: list[dict[str, Any]] = field(default_factory=list)
    scene: dict[str, Any] = field(default_factory=dict)

    pending: dict[str, Any] | None = None

    steps: int = 0
    active: bool = False

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    result_cache: dict[str, dict[str, Any]] = field(
        default_factory=dict
    )


# Imported by app/api/routes/agents.py.
agents: dict[str, Agent] = {}


def choose_avatar() -> str:
    """Randomly choose an unused avatar, or reuse one if exhausted."""
    used = {
        agent.avatar_id
        for agent in agents.values()
        if agent.avatar_id
    }

    available = [
        avatar_id
        for avatar_id in HUMAN_AVATARS
        if avatar_id not in used
    ]

    return random.choice(available or HUMAN_AVATARS)


def create_agent(
    name: str,
    instructions: str,
    source_text: str,
) -> Agent:
    """Create independent agent state and assign a human avatar."""
    name = name.strip()
    instructions = instructions.strip()

    if not name:
        raise ValueError("Agent name cannot be empty.")

    if not instructions:
        raise ValueError("Agent instructions cannot be empty.")

    if not source_text.strip():
        raise ValueError("Agent source text cannot be empty.")

    agent = Agent(
        name=name,
        instructions=instructions,
        source_text=source_text,
        avatar_id=choose_avatar(),
    )

    agents[agent.id] = agent

    logger.info(
        "Created agent id=%s avatar_id=%s",
        agent.id,
        agent.avatar_id,
    )

    return agent


def response(
    agent: Agent,
    status: str,
    *,
    action: dict[str, Any] | None = None,
    message: str = "",
) -> dict[str, Any]:
    """Build a response compatible with AgentResponse."""
    return {
        "session_id": agent.id,
        "status": status,
        "action": action,
        "message": message,
    }


def fail(
    agent: Agent,
    message: str,
) -> dict[str, Any]:
    agent.active = False
    agent.pending = None

    return response(
        agent,
        "failed",
        message=message,
    )


async def advance(agent: Agent) -> dict[str, Any]:
    """Select the next action or complete the current run.

    The caller must hold agent.lock.

    Canvas actions pause the run until the browser reports
    execution feedback through the results endpoint.
    """
    if agent.pending is not None:
        return response(
            agent,
            "action_required",
            action=agent.pending,
            message="Waiting for the canvas action result.",
        )

    if not agent.active:
        return response(
            agent,
            "failed",
            message="No agent run is active.",
        )

    if agent.steps >= MAX_STEPS:
        return fail(
            agent,
            "Agent reached its action limit.",
        )

    context = {
        "agent_name": agent.name,
        "instructions": agent.instructions,
        "source_document": agent.source_text,
        "scene": agent.scene,
        "history": agent.history[-MAX_HISTORY_ITEMS:],
    }

    try:
        decision = await run_in_threadpool(
            react_module.next_action,
            context,
            decide_agent_action,
        )

        if not isinstance(decision, dict):
            raise ValueError("Agent decision must be an object.")

        action_type = decision.get("type")

        if action_type == "finish":
            message = decision.get("message")

            if not isinstance(message, str) or not message.strip():
                raise ValueError("Completion message is missing.")

            message = message.strip()

            agent.steps += 1
            agent.active = False

            agent.history.append({
                "role": "assistant",
                "message": message,
            })

            return response(
                agent,
                "completed",
                message=message,
            )

        if action_type != "write_math":
            raise ValueError("Unsupported agent action.")

        expression = decision.get("expression")

        if (
            not isinstance(expression, str)
            or not expression.strip()
            or len(expression) > 8000
        ):
            raise ValueError("Invalid math expression.")

        action = {
            "id": uuid4().hex,
            "type": "write_math",
            "expression": expression.strip(),
        }

        agent.steps += 1
        agent.pending = action

        agent.history.append({
            "role": "action",
            "action": action,
        })

        return response(
            agent,
            "action_required",
            action=action,
            message="Writing math on the canvas.",
        )

    except Exception as error:
        logger.error(
            "Agent step failed: agent_id=%s error_type=%s",
            agent.id,
            type(error).__name__,
        )

        return fail(
            agent,
            "The agent could not generate a valid next action. "
            "Check the backend logs and provider configuration.",
        )