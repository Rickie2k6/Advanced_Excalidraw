# URL and canvas-action repair

Browser requests use `/talk-sketch`; FastAPI routes do not. The existing Vite
proxies and Socket.IO proxy were retained:

| Browser request | FastAPI request |
| --- | --- |
| `/talk-sketch/chatbot-api/chat` | `/api/chat` |
| `/talk-sketch/api/equations/group` | `/api/equations/group` |
| `/talk-sketch/chatbot-api/health` | `/health` |

## Causes and fixes

- The widget bypassed its URL configuration, and Excalidraw's empty backend base
  produced unproxied `/api/...` requests. Widget callers now share `config.js`;
  Excalidraw uses its own base-aware `chatbot-backend-url.ts` helper.
- The Excalidraw bridge exposed scene/export methods but lacked `writeMath` and
  `addEllipse`. `chatbot-bridge.ts` now creates complete native elements, commits
  undoable scene updates, and returns verified element IDs. It retains deleted
  elements in the scene snapshot for collaboration.
- The existing handwritten glyph renderer did not support `^`. It now lays out
  integer superscripts, including `x^2` and `x^{2}`, while retaining fractions.
- Local `backend/.env` set `PADDLE_ENGINE=transformers1`; this was corrected
  to `transformers`, the [documented engine name](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/PaddleOCR-VL.html).
  No credential values changed.
- Both the bridge scene snapshot and widget multipart payload omitted image
  files. Both now include them. Backend image lookup uses the same canonical
  directory as image uploads, independent of the server's working directory.
- Explicit drawing commands waited for unrelated OCR and LLM calls. The backend
  now returns deterministic write/solve actions directly; detector/Paddle imports
  are deferred until needed. Full-board OCR failures do not block image targeting.
  Explicit solve parsing validates the entire expression instead of accepting a
  supported-looking prefix of an unsupported equation.
- Circle was not awaited; missing methods and unknown actions could be silently
  logged, followed by an empty bubble or a false success claim. Shared action
  execution now validates responses, awaits canvas commits, and reports actual
  failures. Successful actions with an empty answer get a concrete confirmation.
- One click/Enter handling path sends every command through the backend. Repeated
  event registration is ignored, while the in-flight guard remains. The integration
  wrapper forwards anchors and grouping options without dropping them.
- Solve actions retain source-stroke anchors, solution groups, sequential placement,
  and the rule that an anchored original equation is not redrawn. Generated math
  strokes are excluded from the handwritten-equation OCR input to avoid feedback.

## Files changed

Chatbot:

- `backend/app/api/routes/chat.py`
- `backend/app/services/paddle/model.py`
- Local `backend/.env`: only the noncredential `PADDLE_ENGINE` value
- `backend/tests/test_chat_contract.py`
- `widget/src/config.js`, `widget/src/chatbot-widget.js`
- `widget/src/network/chat.js`, `widget/src/network/public-ip.js`
- `widget/src/integrations/excalidraw.js`, `widget/src/integrations/visual-actions.js`
- `widget/src/ui/chat/messages.js`, `widget/src/ui/chat/submission.js`
- `widget/tests/chat.test.js`, `widget/vitest.config.mjs`
- `widget/package.json`, `widget/package-lock.json`

Excalidraw, under `excalidraw-app/`:

- `App.tsx`, `chatbot-backend-url.ts`, `chatbot-bridge.ts`, `math-freedraw.ts`
- `tests/chatbot.test.tsx`, `tests/collab.test.tsx`

Existing unrelated edits to logs, the agent panel, styles, and Vite configuration
were retained. Credentials, Nginx, FastAPI prefixes, and the Socket.IO proxy were
not changed.

## Verification

- Backend: 42 tests pass, including HTTP requests with mocked OCR, LLM, and detector
  outputs, response contracts, canonical image lookup, and `/api/chat`/`/health`.
- Widget: 20 tests pass for URLs, multipart fields, malformed/HTTP responses,
  action results, grouping/anchors, and duplicate submissions.
- Native canvas: 9 Excalidraw tests pass for URL bases, real scene commits,
  superscripts, fractions, grouping, placement, and unsupported input.
- Existing collaboration tests: 2 pass after updating their backend/crypto mocks.
- Excalidraw TypeScript passes; lint passes for the new source/test files.
- A clean Chromium session against the running local Vite server made exactly
  three POST requests to `/talk-sketch/chatbot-api/chat`, forwarded to `/api/chat`.
  It visibly drew the polynomial (11 strokes), anchored solution steps (13 strokes),
  and an ellipse at x=676, y=238, width=248, height=124 around the test image target.
  OCR and detection were mocked in an isolated temporary backend; live model calls
  were not tested. The temporary backend was stopped after verification.
- The public HTTPS frontend timed out from this environment. Public deployment
  verification remains outstanding.

## Start/reload

Use the normal backend Python environment with `backend/requirements.txt` installed:

```bash
cd /tank/homes/student/chuynh/Chatbot/backend
BACKEND_HOST=127.0.0.1 BACKEND_PORT=65532 python run.py
```

The existing Vite server picks up the source changes. Fully reload the browser so
its one-time widget initialization runs again. No production rebuild is required
for this Vite development setup. If the Vite process needs restarting, stop the
existing process first, then run:

```bash
cd /tank/homes/student/chuynh/Excalidraw/excalidraw/excalidraw-app
../node_modules/.bin/vite --host 0.0.0.0 --port 8099
```

Reproduce the automated checks:

```bash
cd /tank/homes/student/chuynh/Chatbot
npm test --prefix widget
cd backend
python -m unittest discover -s tests -v
```

```bash
cd /tank/homes/student/chuynh/Excalidraw/excalidraw
./node_modules/.bin/tsc --noEmit --incremental false
./node_modules/.bin/vitest run excalidraw-app/tests/chatbot.test.tsx excalidraw-app/tests/collab.test.tsx --maxWorkers=1 --minWorkers=1
```
