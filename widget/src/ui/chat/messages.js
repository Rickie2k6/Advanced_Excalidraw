import { marked } from "marked";
import DOMPurify from "dompurify";


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
    const html =
      marked.parse(
        text ?? "",
      );

    message.innerHTML =
      DOMPurify.sanitize(
        html,
      );
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
        "/api/chat",
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

          bridge.writeMath({
            expression,
          });
        } else {
          console.error(
            "[Chatbot] writeMath is not available.",
          );
        }
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
      "Không thể kết nối tới chatbot backend.",
      false,
    );


  } finally {
    isSending = false;
  }
}