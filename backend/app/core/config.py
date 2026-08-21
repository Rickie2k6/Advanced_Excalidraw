import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BACKEND_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    backend_host: str = os.getenv(
        "BACKEND_HOST",
        "10.255.0.11",
    )

    backend_port: int = int(
        os.getenv(
            "BACKEND_PORT",
            "65532",
        )
    )

    paddle_pipeline_version: str = os.getenv(
        "PADDLE_PIPELINE_VERSION",
        "v1.6",
    )

    paddle_engine: str = os.getenv(
        "PADDLE_ENGINE",
        "transformers",
    )

    paddle_device: str = os.getenv(
        "PADDLE_DEVICE",
        "gpu:0",
    )

    paddle_layout_threshold: float = float(
        os.getenv(
            "PADDLE_LAYOUT_THRESHOLD",
            "0.5",
        )
    )

    history_limit: int = int(
        os.getenv(
            "HISTORY_LIMIT",
            "50",
        )
    )


settings = Settings()