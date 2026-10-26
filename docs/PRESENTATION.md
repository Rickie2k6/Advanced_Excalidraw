My project connects a chatbot agent to Excalidraw. The goal is for the agent to understand whiteboard content and respond directly on the canvas.

## 1. Give hints directly on the sketch

**Show the input.** Open a clean board and handwrite this unfinished calculation, leaving space to its right:

```text
3x + 4 = 19
3x = ____
```

Say: “Here is a math problem where I have started the work but left the next step incomplete.”

**Submit the request.** Type: “Look at my work and give me a hint without revealing the answer.”

**Show the agent’s action.** Pause so the audience can see the feedback beside the unfinished line. An acceptable hint is: “What operation would undo the +4? Apply it to both sides.” The hint must avoid giving the missing value or the final solution.

**Explain what it demonstrates.** Say: “The system processes the whiteboard content and places feedback near the work it refers to.” Use this wording after an autonomous run has been verified. If you must copy the hint from chat onto the canvas, demonstrate that step openly and say instead: “The chatbot generates a hint. Placing that feedback beside the relevant work automatically is a feature under development.”

**Tools used.** PaddleOCR-VL recognizes the handwritten math, and the Claude Messages API (`generate_reply`) generates the chat response from the question and whiteboard context. A separate `GET /api/whiteboard/hints` endpoint uses the equation relationship graph, frontier detection, and SymPy-based next-step reasoning to produce tutoring instructions with the relevant equation’s bounding box. That endpoint is not called by the current chat flow. The widget still needs a canvas text-annotation action to place the hint beside the sketch automatically.

Presenter wording: “PaddleOCR reads the handwritten math, and Claude generates the chat feedback. We also have a separate SymPy-based hint pipeline that identifies the next algebra step. Connecting that hint to automatic canvas placement is under development.”

## 2. Circle the appropriate emotion in an image

**Show the input.** On a fresh board, insert one image with several clearly labeled facial expressions, such as Happiness, Sadness, Anger, and Surprise. Keep all faces visible and large enough to distinguish. Confirm that each label matches its expression before presenting.

Say: “This image contains several facial expressions. I will ask the agent to select one.”

**Submit the request.** Type: “Circle the face that represents happiness.”

**Show the agent’s action.** Pause to show the agent drawing a circle around the happy face. Check that the circle encloses the face rather than only its label or a neighboring expression.

**Explain what it demonstrates.** Say: “This demonstrates visual understanding and an action on the whiteboard.” If you must identify the face or draw or reposition the circle yourself, say: “Automatic identification and accurate circle placement are features under development,” and identify the step you performed manually.

**Tools used.** The Claude Messages API analyzes the inserted image (`analyze_inserted_image`), interprets the requested target (`extract_visual_target`), and selects among detected candidates (`select_visual_candidate`). Grounding DINO (`IDEA-Research/grounding-dino-tiny`), loaded through Hugging Face Transformers and PyTorch, proposes bounding boxes for the target. The geometry helper `image_bbox_to_excalidraw` converts the selected image coordinates into canvas coordinates. The backend returns a `circle` action, and the widget calls the Excalidraw bridge’s `addEllipse` method to draw it.

Presenter wording: “Claude interprets the image and request, Grounding DINO locates candidate faces, and Claude selects the matching candidate. The Excalidraw bridge draws the circle at the selected location.”

## 3. Let the chatbot agent solve a basic math equation

**Show the input.** On a fresh board, handwrite `2x + 3 = 7`. Leave ample blank space below it and remove other equations so the intended problem is unambiguous.

Say: “For the final demonstration, I will ask the agent to solve the equation and show its working.”

**Submit the request.** Type: “Solve this equation yourself and write each step below it.”

**Show the agent’s action.** Pause while the solution appears below the problem:

```text
2x + 3 = 7
2x = 4
x = 2
```

**Explain what it demonstrates.** Say: “The agent reads the problem, determines the solution steps, and writes them directly on the canvas.” If you must retype the equation in chat or move the generated steps below the input, say: “Reading the handwritten equation and placing its solution directly below it are features under development,” specifying which step needed assistance.

**Tools used.** PaddleOCR-VL recognizes the handwritten equation, which is stored in `data/equations.json`. For a request without an explicit equation, `extract_whiteboard_solve_action` selects the source only when exactly one recognized equation is stored. The local `solve_linear_steps` function uses SymPy to solve the equation and verify the generated steps, then returns a `write_math_steps` action. The widget calls the Excalidraw bridge’s `writeMath` method for each step. Claude generates the accompanying chat response; the local SymPy solver determines these solution steps. This solver currently supports one-variable linear equations with integer coefficients and an integer solution. Placement below the original handwriting still needs live verification.

Presenter wording: “PaddleOCR reads the equation, SymPy solves it and checks the steps, and the Excalidraw bridge writes each step on the canvas.”

## Rehearsal and backup checklist

1. Follow the backend setup in [README.md](../README.md#run-the-backend), then start it from the project root with `cd backend` followed by `python run.py`. Check `/health` on the configured backend host and port.
2. Open the Excalidraw host with the widget connected. Verify that requests through the widget’s `/chatbot-api/chat` URL reach the backend’s `/api/chat` endpoint. A backend health response alone does not verify the browser connection.
3. Save separate starting boards for the three inputs. Rehearse them in presentation order using the exact requests above, with the backend running. Reset to each starting board before retrying.
4. For each run, verify the canvas action: a hint beside the incomplete work without revealing the answer; a circle around the happy face; and correct solution steps below the equation. Record any manual intervention.
5. Capture a screenshot of each successful result with the canvas and submitted request visible, or make a short recording showing input → request → canvas action. Suggested filenames: `01-hint-success.png`, `02-happiness-success.png`, and `03-equation-success.png`. Keep the backups locally accessible and check that they open before presenting.
6. If a live request fails, show its successful rehearsal screenshot or recording and explicitly identify it as a recorded run. If no successful run exists, present that scenario as a feature under development. A manually prepared canvas is a mockup, not evidence of an autonomous run.

## Preparation status

These are preparation notes, not spoken claims of completed functionality.

| Scenario | Repository inspection / local check | Live rehearsal |
| --- | --- | --- |
| Hint beside sketch | No hint-text canvas action was found in the current chat action dispatcher. Automatic placement is under development. | Pending |
| Circle happiness | Chat and widget contain a circle action path; image interpretation and placement still require browser verification. | Pending |
| Solve equation | The local solver returns `2x+3=7`, `2x=4`, `x=2`. Selecting the handwritten source and placing steps below it still require browser verification. | Pending |

The backend startup attempt in this workspace failed with `ModuleNotFoundError: No module named 'uvicorn'`. The active Python environment also lacks FastAPI and Paddle. No connected Excalidraw browser was available for a canvas rehearsal. No successful-run screenshots or recordings have been captured; all three live rehearsals and their backups remain pending.
