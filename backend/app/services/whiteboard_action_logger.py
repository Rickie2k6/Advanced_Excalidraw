import json
from datetime import datetime, timezone
from pathlib import Path


ACTION_LOG_PATH = Path(
    "/home/student/chuynh/Chatbot/data/"
    "whiteboard_actions.jsonl"
)


def log_whiteboard_action(
    action: str,
    element_id: str | None = None,
    element_type: str | None = None,
    user_ip: str | None = None,
    data: dict | None = None,
):
    ACTION_LOG_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    entry = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "action": action,
        "element_id": element_id,
        "element_type": element_type,
        "user_ip": user_ip,
        "data": data or {},
    }

    with ACTION_LOG_PATH.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            json.dumps(
                entry,
                ensure_ascii=False,
            )
            + "\n"
        )