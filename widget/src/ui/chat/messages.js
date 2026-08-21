import { marked } from "marked";
import DOMPurify from "dompurify";

export function createMessagesArea() {
  const messages = document.createElement("div");
  messages.id = "aicc-chat-messages";
  messages.className = "aicc-chat-messages";

  const placeholder = document.createElement("div");
  placeholder.id = "aicc-chat-placeholder";
  placeholder.className = "aicc-chat-placeholder";
  placeholder.innerHTML = `
    <div class="aicc-chat-placeholder-title">
      Xin chào 👋
    </div>

    <div class="aicc-chat-placeholder-subtitle">
      Tôi có thể giúp gì cho bạn?
    </div>
  `;

  messages.appendChild(placeholder);

  return {
    messages,
    placeholder,
  };
}

export function addMessage(
  container,
  text,
  isUser,
  { renderMarkdown = false } = {},
) {
  const wrapper = document.createElement("div");
  wrapper.className = "aicc-chat-message-wrapper";
  wrapper.classList.add(
    isUser
      ? "aicc-chat-message-wrapper-user"
      : "aicc-chat-message-wrapper-bot",
  );

  const message = document.createElement("div");
  message.className = "aicc-chat-message";
  message.classList.add(
    isUser
      ? "aicc-chat-message-user"
      : "aicc-chat-message-bot",
  );

  if (renderMarkdown && !isUser) {
    const html = marked.parse(text);
    message.innerHTML = DOMPurify.sanitize(html);
  } else {
    message.textContent = text;
  }

  wrapper.appendChild(message);
  container.appendChild(wrapper);

  container.scrollTop = container.scrollHeight;

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

  const trimmedText = text.trim();

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

  const placeholder = messages.querySelector(
    "#aicc-chat-placeholder",
  );

  if (placeholder) {
    placeholder.remove();
  }

  // Hiện message của user
  addMessage(
    messages,
    trimmedText,
    true,
  );

  try {
    const bridge =
      window.__excalidrawChatbotBridge;

    if (!bridge) {
      throw new Error(
        "Excalidraw chatbot bridge is not available.",
      );
    }

    const whiteboardBlob =
      await bridge.exportWhiteboardToPng();

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
      whiteboardBlob?.constructor?.name,
    );

    const formData = new FormData();

    formData.append(
      "question",
      trimmedText,
    );

    // Chỉ append nếu thực sự là Blob
    if (whiteboardBlob instanceof Blob) {
      formData.append(
        "whiteboard",
        whiteboardBlob,
        "whiteboard.png",
      );
    }

    const response = await fetch(
      "/api/chat",
      {
        method: "POST",
        body: formData,
      },
    );

    if (!response.ok) {
      throw new Error(
        `Backend error: ${response.status}`,
      );
    }

    const data =
      await response.json();

    addMessage(
      messages,
      data.answer,
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