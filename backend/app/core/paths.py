from pathlib import Path


CHATBOT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

DATA_DIR = (
    CHATBOT_ROOT /
    "data"
)


# ============================================================
# WHITEBOARD IMAGES
# ============================================================

WHITEBOARD_IMAGES_DIR = (
    DATA_DIR /
    "whiteboard_images"
)


# ============================================================
# WHITEBOARD IMAGE ANALYSIS
# ============================================================

WHITEBOARD_IMAGE_ANALYSIS_DIR = (
    DATA_DIR /
    "whiteboard_image_analysis"
)


# ============================================================
# WHITEBOARD CURRENT STATE
# ============================================================

WHITEBOARD_STATE_DIR = (
    DATA_DIR /
    "whiteboard_state"
)

WHITEBOARD_ELEMENTS_FILE = (
    WHITEBOARD_STATE_DIR /
    "elements.json"
)

WHITEBOARD_APP_STATE_FILE = (
    WHITEBOARD_STATE_DIR /
    "app_state.json"
)


# ============================================================
# CREATE DIRECTORIES
# ============================================================

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

WHITEBOARD_IMAGES_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

WHITEBOARD_IMAGE_ANALYSIS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

WHITEBOARD_STATE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)