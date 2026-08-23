# Excalidraw Chatbot

This project provides an AI chatbot for an Excalidraw whiteboard. The chatbot can inspect the current board, recognize mathematical equations with PaddleOCR, and use the recognized whiteboard context to answer questions through an OpenAI model.

## Project components

- `widget/` contains the browser-based chat widget and its Excalidraw integration.
- `backend/` contains the FastAPI application, OCR services, chatbot service, and whiteboard reasoning pipeline.
- `data/strokes.json` stores the current whiteboard stroke snapshot.
- `data/equations.json` stores grouped and recognized equations.

## Chatbot workflow

```mermaid
flowchart TD
    A[User draws on the Excalidraw whiteboard] --> B[Whiteboard strokes and equation groups]
    B --> C[PaddleOCR recognizes equations]
    C --> D[Recognized equations are stored in data/equations.json]
    E[User enters a question in the chat widget] --> F[Widget exports the current whiteboard as a PNG]
    F --> G[POST /api/chat with the question and optional whiteboard image]
    D --> H[Backend builds the recognized-equation context]
    G --> I[Backend optionally analyzes the full whiteboard image]
    H --> J[Combine the question and whiteboard context]
    I --> J
    J --> K[OpenAI generates a response]
    K --> L[Widget sanitizes and displays the Markdown response]
```

The main chat flow works as follows:

1. The widget initializes inside the host page and connects to the Excalidraw bridge.
2. The user types a question and submits it by pressing Enter or clicking the send button.
3. The widget asks the bridge to export the current whiteboard as a PNG.
4. The widget sends the question and, when available, the PNG to `POST /api/chat` as form data.
5. The backend analyzes the supplied whiteboard image with PaddleOCR.
6. The backend also loads previously recognized equations from `data/equations.json`, ordered by their position on the board.
7. The full-board analysis and recognized equations are combined into the chatbot context.
8. The question and context are sent to the configured OpenAI model.
9. The API returns the answer to the widget, which sanitizes and renders it as Markdown.

### Equation-processing workflow

The backend also exposes a more focused equation pipeline:

1. `POST /api/strokes/sync` replaces the stored stroke snapshot with the current whiteboard state and removes equations whose strokes no longer exist.
2. `POST /api/equations/group` groups nearby freehand strokes into candidate equation regions.
3. `POST /api/equations/{equation_id}/ocr` recognizes an individual equation image with PaddleOCR and saves the result.
4. `POST /api/equations/sync` can save recognized equation groups in a batch.
5. `GET /api/whiteboard/hints` reads the recognized equations, identifies relationships and equation frontiers, and returns suggested next-step tutoring hints.

These endpoints are available for the surrounding Excalidraw integration; the chat widget shown in this repository directly calls `POST /api/chat`.

## Run the backend

### Install the required packages

From the project root, create and activate a Python virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows, activate the environment with:

```powershell
.venv\Scripts\activate
```

Install all backend packages from `requirement.doc`:

```bash
python -m pip install -r requirement.doc
```

Although the dependency file uses the requested `.doc` extension, it is a plain-text, pip-compatible requirements file.

### Configure and start the server

The backend reads its settings from `backend/.env`. Make sure the environment contains the required configuration, including a valid `OPENAI_API_KEY`.

From the project root, enter the backend directory and start the FastAPI server:

```bash
cd backend
python run.py
```

The server uses `BACKEND_HOST` and `BACKEND_PORT` from `backend/.env`. Once it is running, the root endpoint returns a confirmation message, and the interactive FastAPI documentation is available at `/docs`.

## Main API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/` | Check that the backend is running |
| `GET` | `/health` | Check application health |
| `POST` | `/api/chat` | Ask a question using the current whiteboard context |
| `POST` | `/api/analyze` | Analyze a complete whiteboard image |
| `POST` | `/api/analyze-equations` | Recognize multiple cropped equation images |
| `POST` | `/api/strokes/sync` | Store the current whiteboard stroke snapshot |
| `POST` | `/api/equations/group` | Group strokes into candidate equations |
| `POST` | `/api/equations/{equation_id}/ocr` | Recognize and store one equation |
| `GET` | `/api/whiteboard/hints` | Generate next-step tutoring hints |
