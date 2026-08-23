from app.api.whiteboard import router as whiteboard_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from contextlib import (
    asynccontextmanager,
    suppress,
)

from app.services.room_presence import (
    run_presence_cleanup_loop,
)
from app.api.routes import (
    analyze,
    chat,
    health,
    history,
    state,
    client,
    excalidraw_store,
    equations,
    strokes,
    presence,
)

@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    """
    Start the room-presence cleanup task
    when FastAPI starts.

    Stop it cleanly when FastAPI shuts down.
    """

    cleanup_task = asyncio.create_task(
        run_presence_cleanup_loop()
    )

    print(
        "[FastAPI] "
        "Room presence cleanup started"
    )

    try:
        yield

    finally:
        cleanup_task.cancel()

        with suppress(
            asyncio.CancelledError
        ):
            await cleanup_task

        print(
            "[FastAPI] "
            "Room presence cleanup stopped"
        )
app = FastAPI(
    title="Excalidraw PaddleOCR Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(whiteboard_router)

app.include_router(
    health.router,
)

app.include_router(
    presence.router,
    prefix="/api",
)

app.include_router(
    strokes.router,
    prefix="/api",
)

app.include_router(
    equations.router,
    prefix="/api",
)

app.include_router(
    analyze.router,
    prefix="/api",
)

app.include_router(
    chat.router,
    prefix="/api",
)

app.include_router(
    state.router,
    prefix="/api",
)

app.include_router(
    history.router,
    prefix="/api",
)

app.include_router(
    client.router,
    prefix="/api",
)

app.include_router(
    excalidraw_store.router,
    prefix="/api",
)


@app.get("/")
def root():
    return {
        "message":
            "Excalidraw PaddleOCR "
            "backend is running."
    }