import { requestChat } from "../../network/chat.js";
import { executeVisualAction } from "../../integrations/visual-actions.js";

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

export async function sendMessage(messages, text) {
  const question = text.trim();
  if (!question || isSending) return false;
  isSending = true;
  messages.querySelector("#aicc-chat-placeholder")?.remove();
  addMessage(messages, question, true);
  try {
    const bridge = window.__excalidrawChatbotBridge;
    if (!bridge || typeof bridge.getScene !== "function") {
      throw new Error("Excalidraw bridge is not ready. Reload the canvas.");
    }
    const scene = await bridge.getScene();
    let whiteboard = null;
    // Screenshot context is optional; an export failure must not block writes.
    try {
      whiteboard = await bridge.exportWhiteboardToPng?.();
    } catch (error) {
      console.warn("[Chatbot] Whiteboard export failed:", error);
    }
    const data = await requestChat(question, scene, whiteboard);
    let result;
    try {
      if (data.visual_action != null) {
        result = await executeVisualAction(bridge, data.visual_action);
      }
    } catch (error) {
      // Avoid displaying a model's success claim when the canvas action failed.
      throw new Error(`Canvas action failed: ${error.message}`);
    }
    addMessage(messages, data.answer.trim() || result.message, false, { renderMarkdown: true });
    return true;
  } catch (error) {
    console.error("[Chatbot]", error);
    addMessage(messages, error.message || "The chatbot request could not be completed.", false);
    return false;
  } finally {
    isSending = false;
  }
}
