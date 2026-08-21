from collections import deque
from copy import deepcopy
from threading import Lock

from app.core.config import settings


_lock = Lock()

_current_scene = None
_current_analysis = None

_history = deque(
    maxlen=settings.history_limit
)


def update_scene(scene):
    global _current_scene

    with _lock:
        _current_scene = deepcopy(scene)


def update_analysis(analysis):
    global _current_analysis

    with _lock:
        _current_analysis = deepcopy(analysis)

        _history.append(
            deepcopy(analysis)
        )


def get_current_state():
    with _lock:
        return {
            "scene": deepcopy(
                _current_scene
            ),
            "analysis": deepcopy(
                _current_analysis
            ),
        }


def get_history():
    with _lock:
        return list(
            deepcopy(_history)
        )