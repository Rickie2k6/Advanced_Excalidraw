
import { marked } from "marked";
import DOMPurify from "dompurify";
import katex from "katex";
import "katex/dist/katex.min.css";

export function createMessagesArea() {
  const messages =
    document.createElement("div");

  messages.id =
    "aicc-chat-messages";

  messages.className =
    "aicc-chat-messages";


  const placeholder =
    document.createElement("div");

  placeholder.id =
    "aicc-chat-placeholder";

  placeholder.className =
    "aicc-chat-placeholder";


  placeholder.innerHTML = `
    <div class="aicc-chat-placeholder-title">
      Aloha 👋
    </div>

    <div class="aicc-chat-placeholder-subtitle">
      How can I have you?
    </div>
  `;


  messages.appendChild(
    placeholder,
  );


  return {
    messages,
    placeholder,
  };
}
function renderMathMarkdown(text) {
  const mathExpressions = [];

  const protectedText = String(text ?? "").replace(
    /\\\[([\s\S]*?)\\\]|\\\(([\s\S]*?)\\\)|\$\$([\s\S]*?)\$\$/g,
    (match, displayMath, inlineMath, dollarMath) => {
      const expression =
        displayMath ?? inlineMath ?? dollarMath;

      const displayMode =
        displayMath !== undefined ||
        dollarMath !== undefined;

      const index = mathExpressions.length;

      mathExpressions.push({
        expression,
        displayMode,
      });

      return `MATHPLACEHOLDER${index}END`;
    },
  );

  let html = marked.parse(protectedText);

  html = html.replace(
    /MATHPLACEHOLDER(\d+)END/g,
    (match, index) => {
      const math = mathExpressions[Number(index)];

      if (!math) {
        return match;
      }

      return katex.renderToString(math.expression, {
        displayMode: math.displayMode,
        throwOnError: false,
        output: "html",
        trust: false,
      });
    },
  );

  return DOMPurify.sanitize(html);
}

export function addMessage(
  container,
  text,
  isUser,
  {
    renderMarkdown = false,
  } = {},
) {
  const wrapper =
    document.createElement("div");

  wrapper.className =
    "aicc-chat-message-wrapper";


  wrapper.classList.add(
    isUser
      ? "aicc-chat-message-wrapper-user"
      : "aicc-chat-message-wrapper-bot",
  );


  const message =
    document.createElement("div");

  message.className =
    "aicc-chat-message";


  message.classList.add(
    isUser
      ? "aicc-chat-message-user"
      : "aicc-chat-message-bot",
  );


  if (
    renderMarkdown &&
    !isUser
  ) {
    message.innerHTML = renderMathMarkdown(text);
  } else {
    message.textContent =
      text ?? "";
  }


  wrapper.appendChild(
    message,
  );

  container.appendChild(
    wrapper,
  );


  container.scrollTop =
    container.scrollHeight;


  return message;
}


let isSending = false;


export async function sendMessage(
  messages,
  text,
) {
  console.log(
    "[Chatbot] sendMessage called:",
    text,
  );


  console.trace(
    "[Chatbot] sendMessage trace",
  );


  const trimmedText =
    text.trim();


  if (!trimmedText) {
    return;
  }


  if (isSending) {
    console.log(
      "[Chatbot] duplicate send ignored.",
    );

    return;
  }


  isSending = true;


  const placeholder =
    messages.querySelector(
      "#aicc-chat-placeholder",
    );


  if (placeholder) {
    placeholder.remove();
  }


  // ============================================================
  // SHOW USER MESSAGE
  // ============================================================

  addMessage(
    messages,
    trimmedText,
    true,
  );

  let backendResponded = false;

  try {
    // ============================================================
    // GET EXCALIDRAW BRIDGE
    // ============================================================

    const bridge =
      window.__excalidrawChatbotBridge;


    if (!bridge) {
      throw new Error(
        "Excalidraw chatbot bridge is not available.",
      );
    }


    // ============================================================
    // EXPORT WHITEBOARD
    // ============================================================

    const whiteboardBlob =
      await bridge.exportWhiteboardToPng();


    // ============================================================
    // GET EXCALIDRAW SCENE
    // ============================================================

    const scene =
      await bridge.getScene();


    // ============================================================
    // DEBUG: CURRENT TEXT ELEMENTS
    // ============================================================

    console.log(
      "[Chatbot] TEXT ELEMENTS:",
      scene?.elements
        ?.filter(
          (element) =>
            element.type === "text" &&
            !element.isDeleted,
        )
        .map(
          (element) => ({
            id: element.id,
            text: element.text,
            x: element.x,
            y: element.y,
            width: element.width,
            height: element.height,
          }),
        ),
    );


    console.log(
      "========== EXCALIDRAW SCENE ==========",
    );


    console.log(
      "FULL SCENE:",
      scene,
    );


    console.log(
      "ELEMENTS:",
      scene?.elements,
    );


    console.log(
      "FILES:",
      scene?.files,
    );


    console.log(
      "IMAGE ELEMENTS:",
      scene?.elements?.filter(
        (element) =>
          element.type === "image",
      ),
    );


    console.log(
      "[Chatbot] whiteboard export:",
      whiteboardBlob,
    );


    console.log(
      "[Chatbot] is Blob:",
      whiteboardBlob instanceof Blob,
    );


    console.log(
      "[Chatbot] type:",
      typeof whiteboardBlob,
    );


    console.log(
      "[Chatbot] constructor:",
      whiteboardBlob
        ?.constructor
        ?.name,
    );


    // ============================================================
    // BUILD FORM DATA
    // ============================================================

    const formData =
      new FormData();


    formData.append(
      "question",
      trimmedText,
    );


    // ============================================================
    // SEND EXCALIDRAW SCENE
    // ============================================================

    if (scene) {
      const safeScene = {
        elements:
          scene?.elements ?? [],
      };

      const sceneJson =
        JSON.stringify(
          safeScene,
        );

      console.log(
        "[Chatbot] safe scene JSON:",
        sceneJson,
      );

      formData.append(
        "scene_json",
        sceneJson,
      );
    }


    // ============================================================
    // SEND WHITEBOARD IMAGE
    // ============================================================

    if (
      whiteboardBlob instanceof Blob
    ) {
      formData.append(
        "whiteboard",
        whiteboardBlob,
        "whiteboard.png",
      );
    }


    // ============================================================
    // SEND REQUEST TO BACKEND
    // ============================================================

    console.log(
      "[Chatbot] sending POST /api/chat",
    );


    const response =
      await fetch(
        "/talk-sketch/api/chat",
        {
          method: "POST",
          body: formData,
        },
      );


    // ============================================================
    // HANDLE BACKEND ERROR
    // ============================================================

    if (!response.ok) {
      const errorText =
        await response.text();


      console.error(
        "[Chatbot] Backend error response:",
        errorText,
      );


      throw new Error(
        `Backend error: ${response.status} ${errorText}`,
      );
    }


    // ============================================================
    // PARSE BACKEND RESPONSE
    // ============================================================

    const data =
      await response.json();

    backendResponded = true;


    console.log(
      "[Chatbot] backend response:",
      data,
    );


    // ============================================================
    // EXECUTE VISUAL ACTION ON EXCALIDRAW
    // ============================================================

    if (data.visual_action) {
      const action =
        data.visual_action.action;


      // ------------------------------------------------------------
      // CIRCLE
      // ------------------------------------------------------------

      if (
        action === "circle"
      ) {
        const {
          x,
          y,
          width,
          height,
        } = data.visual_action;


        console.log(
          "[Chatbot] executing circle:",
          data.visual_action,
        );


        if (
          typeof bridge.addEllipse ===
          "function"
        ) {
          bridge.addEllipse({
            x,
            y,
            width,
            height,
          });
        } else {
          console.error(
            "[Chatbot] addEllipse is not available.",
          );
        }
      }


      // ------------------------------------------------------------
      // WRITE MATH
      // ------------------------------------------------------------

      else if (
        action === "write_math"
      ) {
        const {
          expression,
        } = data.visual_action;


        console.log(
          "[Chatbot] executing write_math:",
          data.visual_action,
        );


        if (!expression) {
          console.error(
            "[Chatbot] Missing expression for write_math.",
          );
        } else if (
          typeof bridge.writeMath ===
          "function"
        ) {
          // ========================================================
          // IMPORTANT
          //
          // Không truyền x/y.
          //
          // App.tsx sẽ gọi:
          // getSceneElements()
          // -> estimateMathSize()
          // -> findAvailablePosition()
          //
          // math-placement.ts sẽ tự quyết định
          // vị trí trên whiteboard.
          // ========================================================

          try {
            const result = await bridge.writeMath({ expression });
            if (!result?.success) {
              throw new Error(result?.error ?? "Failed to write math.");
            }
          } catch (error) {
            console.error("[Chatbot] Math rendering failed:", error);
            const renderError = new Error("Math rendering failed.");
            renderError.userMessage =
              "Mình chưa đọc được công thức này, bạn thử viết lại nhé.";
            throw renderError;
          }
        } else {
          console.error(
            "[Chatbot] writeMath is not available.",
          );
        }
      }


          // ------------------------------------------------------------
          // WRITE MATH STEPS
          // ------------------------------------------------------------

          else if (
            action === "write_math_steps"
          ) {
            const {
              steps,
              source_stroke_ids: sourceStrokeIds,
            } = data.visual_action;

            console.log(
              "[Chatbot] executing write_math_steps:",
              steps,
            );

            if (
              !Array.isArray(steps) ||
              steps.length === 0
            ) {
              throw new Error(
                "Invalid write_math_steps: steps must be a non-empty array.",
              );
            }

            if (
              typeof bridge.writeMath !== "function"
            ) {
              throw new Error(
                "Excalidraw writeMath is not available.",
              );
            }

            const solutionGroupId =
              `solution-${Date.now()}`;

            const hasSourceStrokes =
              Array.isArray(sourceStrokeIds) &&
              sourceStrokeIds.length > 0;

            let anchorElementIds = hasSourceStrokes
              ? [...sourceStrokeIds]
              : [];

            const stepsToDraw = hasSourceStrokes
              ? steps.slice(1)
              : steps;  

            for (let i = 0; i < stepsToDraw.length; i++) {
              const expression = stepsToDraw[i];

              if (
                typeof expression !== "string" ||
                !expression.trim()
              ) {
                throw new Error(
                  `Invalid expression at step ${i + 1}`,
                );
              }

              const result = await bridge.writeMath({
                expression,
                anchorElementIds,
                solutionGroupId,
                actionId: `step-${i + 1}`,
              });

              if (
                !result?.success ||
                !Array.isArray(result.element_ids) ||
                result.element_ids.length === 0
              ) {
                throw new Error(
                  `Failed to write step ${i + 1}`,
                );
              }

              anchorElementIds = result.element_ids;

              console.log(
                `[Chatbot] Step ${i + 1} written:`,
                expression,
              );
            }

            console.log(
              "[Chatbot] All math steps written successfully.",
            );
          }


      // ------------------------------------------------------------
      // WRITE MULTIPLE MATH STEPS
      // Solve all recognized equations on the whiteboard
      // ------------------------------------------------------------

      else if (action === "write_multiple_math_steps") {
        const { solutions } = data.visual_action;

        if (!Array.isArray(solutions) || solutions.length === 0) {
          throw new Error(
            "Invalid write_multiple_math_steps: no solutions provided.",
          );
        }

        if (typeof bridge.writeMath !== "function") {
          throw new Error(
            "Excalidraw writeMath is not available.",
          );
        }

        console.log(
          "[Chatbot] Solving multiple equations:",
          solutions,
        );

        for (let groupIndex = 0; groupIndex < solutions.length; groupIndex++) {
          const solution = solutions[groupIndex];

          const {
            steps,
            source_equation_id: sourceEquationId,
            source_stroke_ids: sourceStrokeIds,
          } = solution;

          if (!Array.isArray(steps) || steps.length === 0) {
            console.warn(
              "[Chatbot] Skipping invalid solution:",
              solution,
            );
            continue;
          }

          const hasSourceStrokes =
            Array.isArray(sourceStrokeIds) &&
            sourceStrokeIds.length > 0;

          const solutionGroupId =
            `solution-${sourceEquationId ?? groupIndex}-${Date.now()}`;

          // Start below the original handwritten equation.
          let anchorElementIds = hasSourceStrokes
            ? [...sourceStrokeIds]
            : [];

          // Don't redraw the original equation if it's already
          // handwritten on the whiteboard.
          const stepsToDraw = hasSourceStrokes
            ? steps.slice(1)
            : steps;

          for (let stepIndex = 0; stepIndex < stepsToDraw.length; stepIndex++) {
            const expression = stepsToDraw[stepIndex];

            if (
              typeof expression !== "string" ||
              !expression.trim()
            ) {
              throw new Error(
                `Invalid math step at index ${stepIndex}`,
              );
            }

            const result = await bridge.writeMath({
              expression,
              anchorElementIds,
              solutionGroupId,
              actionId: `step-${stepIndex + 1}`,
            });

            if (
              !result?.success ||
              !Array.isArray(result.element_ids) ||
              result.element_ids.length === 0
            ) {
              throw new Error(
                `Failed to draw math step: ${expression}`,
              );
            }

            // Position the next step relative to the previous step.
            anchorElementIds = result.element_ids;

            console.log(
              `[Chatbot] Equation ${groupIndex + 1}, step ${stepIndex + 1}:`,
              expression,
            );
          }
        }

        console.log(
          "[Chatbot] Finished drawing multiple equation solutions.",
        );
      }


      // ------------------------------------------------------------
      // UNKNOWN ACTION
      // ------------------------------------------------------------

      else {
        console.warn(
          "[Chatbot] Unknown visual action:",
          data.visual_action,
        );
      }
    }


    // ============================================================
    // SHOW CHATBOT RESPONSE
    // ============================================================

    addMessage(
      messages,
      data.answer ?? "",
      false,
      {
        renderMarkdown: true,
      },
    );


  } catch (error) {
    console.error(
      "[Chatbot] sendMessage error:",
      error,
    );


    addMessage(
      messages,
      error.userMessage ?? (backendResponded
        ? `Đã nhận phản hồi từ backend nhưng xảy ra lỗi xử lý: ${error.message}`
        : `Không thể hoàn tất yêu cầu tới chatbot backend: ${error.message}`),
      false,
    );


  } finally {
    isSending = false;
  }
}
