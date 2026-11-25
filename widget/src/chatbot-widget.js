import { bindChatSubmission } from "./ui/chat/submission.js";
import {
  loadWidgetCSS,
  onDOMReady,
} from "./bootstrap.js";
import { createChatWidget } from "./ui/widget.js";
import { createToggleButton } from "./ui/toggle-button.js";
import {
  addMessage,
  sendMessage,
} from "./ui/chat/messages.js";

(function () {
  if (window.__aiccChatbotInitialized) {
    console.log("[Chatbot] already initialized, skipping.");
    return;
  }

  window.__aiccChatbotInitialized = true;
  window.__aiccActiveAgent = null;

  loadWidgetCSS();

  let messagesContainer = null;

  function showAgentGreeting(agent) {
    if (!messagesContainer) {
      return;
    }

    messagesContainer
      .querySelector("#aicc-chat-placeholder")
      ?.remove();

    const bubble = addMessage(
      messagesContainer,
      agent.message ||
        `Hi, I am ${agent.name}. I’m ready to help.`,
      false,
    );

    const row = bubble.parentElement;

    if (!row) {
      return;
    }

    row.classList.add("aicc-agent-greeting");

    const avatarId = /^human-(0[1-9]|1[0-2])$/.test(
      agent.avatar_id ?? "",
    )
      ? agent.avatar_id
      : "human-01";

    const avatar = document.createElement("img");
    avatar.className = "aicc-agent-message-avatar";
    avatar.alt = `${agent.name}'s avatar`;
    avatar.width = 36;
    avatar.height = 36;
    avatar.src = `/talk-sketch/avatars/${avatarId}.png`;

    // Show initials if the portrait asset cannot load.
    avatar.addEventListener(
      "error",
      () => {
        const fallback = document.createElement("span");
        fallback.className = "aicc-agent-message-avatar";
        fallback.textContent =
          Array.from(agent.name.trim())[0]?.toUpperCase() || "?";
        fallback.setAttribute("role", "img");
        fallback.setAttribute(
          "aria-label",
          `${agent.name}'s avatar`,
        );

        avatar.replaceWith(fallback);
      },
      { once: true },
    );

    avatar.addEventListener(
      "load",
      () => {
        messagesContainer.scrollTop =
          messagesContainer.scrollHeight;
      },
      { once: true },
    );

    row.prepend(avatar);

    messagesContainer.scrollTop =
      messagesContainer.scrollHeight;
  }

  window.addEventListener("chatbot:agent-created", (event) => {
    const agent = event.detail;

    if (
      !agent ||
      typeof agent.agent_id !== "string" ||
      typeof agent.name !== "string" ||
      agent.status !== "ready"
    ) {
      console.error("[Chatbot] Invalid agent creation response.");
      return;
    }

    if (window.__aiccActiveAgent?.agent_id === agent.agent_id) {
      return;
    }

    window.__aiccActiveAgent = {
      agent_id: agent.agent_id,
      name: agent.name,
      avatar_id: agent.avatar_id,
      message: agent.message,
    };

    showAgentGreeting(window.__aiccActiveAgent);
  });

  function initialize() {
    const {
      messages,
      input,
      button,
      container,
    } = createChatWidget();

    messagesContainer = messages;

    createToggleButton(container);

    bindChatSubmission(
      { messages, input, button },
      sendMessage,
    );

    if (window.__aiccActiveAgent) {
      showAgentGreeting(window.__aiccActiveAgent);
    }
  }

  onDOMReady(initialize);
})();