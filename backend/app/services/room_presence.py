from __future__ import annotations

import asyncio
import json
import time
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from typing import Any


# ============================================================
# CONFIG
# ============================================================


DATA_DIR = Path(
    "/home/student/chuynh/Chatbot/data"
)

STROKES_FILE = (
    DATA_DIR /
    "strokes.json"
)

EQUATIONS_FILE = (
    DATA_DIR /
    "equations.json"
)


# If a browser stops sending heartbeat for this
# many seconds, consider that session disconnected.
SESSION_TIMEOUT_SECONDS = 30.0


# How often the backend checks for dead sessions.
CLEANUP_INTERVAL_SECONDS = 10.0


# ============================================================
# IN-MEMORY ROOM STATE
# ============================================================


# One room only for now.
#
# session_id:
# {
#     "session_id": "...",
#     "client_ip": "...",
#     "joined_at": "...",
#     "last_seen": 12345.67,
#     "last_seen_at": "..."
# }
_active_sessions: dict[
    str,
    dict[str, Any],
] = {}


# Protect:
# - active session state
# - last-user reset
#
# This prevents a join and leave/reset from
# modifying room state at exactly the same time.
_presence_lock = asyncio.Lock()


# ============================================================
# UTILITIES
# ============================================================


def _utc_now() -> str:
    return (
        datetime.now(
            timezone.utc
        ).isoformat()
    )


def _write_json_atomic(
    path: Path,
    data: dict,
) -> None:
    """
    Write JSON using a temporary file and rename.

    This reduces the chance of leaving a partially
    written JSON file if something goes wrong.
    """

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = Path(
        f"{path}.tmp"
    )

    temp_path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temp_path.replace(
        path
    )


def _reset_whiteboard_data_locked() -> None:
    """
    Reset all data for the current one-room prototype.

    IMPORTANT:
    Caller must already hold _presence_lock.
    """

    _write_json_atomic(
        STROKES_FILE,
        {
            "strokes": {}
        },
    )

    _write_json_atomic(
        EQUATIONS_FILE,
        {
            "equations": {}
        },
    )

    print(
        "[Room Presence] "
        "Room empty -> "
        "strokes.json and equations.json reset"
    )


def _remove_expired_sessions_locked() -> list[str]:
    """
    Remove sessions whose heartbeat has expired.

    IMPORTANT:
    Caller must already hold _presence_lock.
    """

    now = time.monotonic()

    expired_session_ids = [
        session_id
        for (
            session_id,
            session,
        ) in _active_sessions.items()
        if (
            now -
            float(
                session["last_seen"]
            )
        )
        > SESSION_TIMEOUT_SECONDS
    ]

    for session_id in expired_session_ids:

        session = (
            _active_sessions.pop(
                session_id,
                None,
            )
        )

        if session:
            print(
                "[Room Presence] "
                "Session expired:",
                session_id,
                "IP:",
                session.get(
                    "client_ip"
                ),
            )

    return expired_session_ids


# ============================================================
# JOIN
# ============================================================


async def join_session(
    session_id: str,
    client_ip: str | None = None,
) -> dict[str, Any]:
    """
    Register one browser/tab as active in the room.

    session_id should be a unique UUID generated
    by the frontend.

    IP is stored only as metadata. Presence counting
    is based on session_id, NOT IP.
    """

    if not session_id:
        raise ValueError(
            "session_id is required."
        )

    async with _presence_lock:

        now_monotonic = (
            time.monotonic()
        )

        now_iso = _utc_now()

        # Remove dead sessions first.
        expired = (
            _remove_expired_sessions_locked()
        )
        # Previous room users timed out before
        # this new user joined.
        #
        # Reset old whiteboard data before
        # starting the new room session.
        if (
            expired
            and not _active_sessions
        ):
            _reset_whiteboard_data_locked()

        existing = (
            _active_sessions.get(
                session_id
            )
        )

        if existing:

            existing[
                "last_seen"
            ] = now_monotonic

            existing[
                "last_seen_at"
            ] = now_iso

            if client_ip:
                existing[
                    "client_ip"
                ] = client_ip

        else:

            _active_sessions[
                session_id
            ] = {
                "session_id":
                    session_id,

                "client_ip":
                    client_ip,

                "joined_at":
                    now_iso,

                "last_seen":
                    now_monotonic,

                "last_seen_at":
                    now_iso,
            }

        active_count = len(
            _active_sessions
        )

        print(
            "[Room Presence] JOIN",
            session_id,
            "IP:",
            client_ip,
            "active:",
            active_count,
        )

        return {
            "status":
                "ok",

            "session_id":
                session_id,

            "client_ip":
                client_ip,

            "active_count":
                active_count,

            "expired_sessions":
                expired,
        }


# ============================================================
# HEARTBEAT
# ============================================================


async def heartbeat_session(
    session_id: str,
    client_ip: str | None = None,
) -> dict[str, Any]:
    """
    Update last_seen for an active browser session.

    If the session is missing, heartbeat will
    re-register it. This makes the system recover
    more gracefully after a backend restart.
    """

    if not session_id:
        raise ValueError(
            "session_id is required."
        )

    async with _presence_lock:

        expired = (
            _remove_expired_sessions_locked()
        )

        now_monotonic = (
            time.monotonic()
        )

        now_iso = _utc_now()

        session = (
            _active_sessions.get(
                session_id
            )
        )

        if session is None:

            session = {
                "session_id":
                    session_id,

                "client_ip":
                    client_ip,

                "joined_at":
                    now_iso,

                "last_seen":
                    now_monotonic,

                "last_seen_at":
                    now_iso,
            }

            _active_sessions[
                session_id
            ] = session

            print(
                "[Room Presence] "
                "Heartbeat restored session:",
                session_id,
            )

        else:

            session[
                "last_seen"
            ] = now_monotonic

            session[
                "last_seen_at"
            ] = now_iso

            if client_ip:
                session[
                    "client_ip"
                ] = client_ip

        return {
            "status":
                "ok",

            "session_id":
                session_id,

            "active_count":
                len(
                    _active_sessions
                ),

            "expired_sessions":
                expired,
        }


# ============================================================
# LEAVE
# ============================================================


async def leave_session(
    session_id: str,
) -> dict[str, Any]:
    """
    Explicitly remove a browser session.

    If this was the final active session,
    reset strokes.json and equations.json.
    """

    if not session_id:
        raise ValueError(
            "session_id is required."
        )

    async with _presence_lock:

        removed_session = (
            _active_sessions.pop(
                session_id,
                None,
            )
        )

        active_count = len(
            _active_sessions
        )

        print(
            "[Room Presence] LEAVE",
            session_id,
            "found:",
            removed_session is not None,
            "active:",
            active_count,
        )

        # Only reset when an actual active session
        # left and the room has become empty.
        if (
            removed_session is not None
            and active_count == 0
        ):
            _reset_whiteboard_data_locked()

        return {
            "status":
                "ok",

            "session_id":
                session_id,

            "removed":
                removed_session
                is not None,

            "active_count":
                active_count,

            "room_reset":
                (
                    removed_session
                    is not None
                    and active_count == 0
                ),
        }


# ============================================================
# REMOVE TIMED-OUT USERS
# ============================================================


async def cleanup_expired_sessions(
) -> dict[str, Any]:
    """
    Remove browser sessions that stopped sending
    heartbeat.

    If one or more sessions expire and this leaves
    the room empty, reset both JSON files.
    """

    async with _presence_lock:

        expired = (
            _remove_expired_sessions_locked()
        )

        active_count = len(
            _active_sessions
        )

        room_reset = False

        # Important:
        # Only reset because users actually expired.
        #
        # We do NOT reset simply because the dict was
        # already empty before this function ran.
        if (
            expired
            and active_count == 0
        ):
            _reset_whiteboard_data_locked()

            room_reset = True

        return {
            "expired_sessions":
                expired,

            "active_count":
                active_count,

            "room_reset":
                room_reset,
        }


# ============================================================
# BACKGROUND CLEANUP LOOP
# ============================================================


async def run_presence_cleanup_loop(
) -> None:
    """
    Background loop for detecting users who disappear
    without sending an explicit leave request.

    Examples:
    - browser crash
    - laptop sleeps
    - Wi-Fi disappears
    - tab/process is killed
    """

    print(
        "[Room Presence] "
        "Cleanup loop started"
    )

    try:

        while True:

            await asyncio.sleep(
                CLEANUP_INTERVAL_SECONDS
            )

            result = (
                await cleanup_expired_sessions()
            )

            if result[
                "expired_sessions"
            ]:
                print(
                    "[Room Presence] "
                    "Cleanup:",
                    result,
                )

    except asyncio.CancelledError:

        print(
            "[Room Presence] "
            "Cleanup loop stopped"
        )

        raise


# ============================================================
# DEBUG / STATUS
# ============================================================


async def get_presence_status(
) -> dict[str, Any]:
    """
    Return room presence information.

    Useful while developing/debugging.
    """

    async with _presence_lock:

        sessions = []

        for session in (
            _active_sessions.values()
        ):

            # Do not expose monotonic internals.
            sessions.append({
                "session_id":
                    session[
                        "session_id"
                    ],

                "client_ip":
                    session.get(
                        "client_ip"
                    ),

                "joined_at":
                    session.get(
                        "joined_at"
                    ),

                "last_seen_at":
                    session.get(
                        "last_seen_at"
                    ),
            })

        return {
            "active_count":
                len(
                    _active_sessions
                ),

            "sessions":
                sessions,

            "timeout_seconds":
                SESSION_TIMEOUT_SECONDS,
        }


# ============================================================
# MANUAL RESET
# ============================================================


async def force_reset_room(
) -> None:
    """
    Development/debug helper.

    Clears active sessions and both JSON files.
    """

    async with _presence_lock:

        _active_sessions.clear()

        _reset_whiteboard_data_locked()