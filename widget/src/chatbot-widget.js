import {
  loadWidgetCSS,
  onDOMReady,
} from "./bootstrap.js";

import {
  createChatWidget,
} from "./ui/widget.js";

import {
  createToggleButton,
} from "./ui/toggle-button.js";

import {
  sendMessage,
} from "./ui/chat/messages.js";

(function () {
  // Prevent chatbot from being initialized twice
  if (window.__aiccChatbotInitialized) {
    console.log(
      "[Chatbot] already initialized, skipping.",
    );

    return;
  }

  window.__aiccChatbotInitialized = true;

  loadWidgetCSS();

  function initialize() {
    const {
      messages,
      input,
      button,
      container,
    } = createChatWidget();

    createToggleButton(container);

    button.addEventListener(
      "click",
      () => {
        sendMessage(
          messages,
          input.value,
        );

        input.value = "";
      },
    );

    input.addEventListener(
      "keydown",
      (event) => {
        if (event.key === "Enter") {
          event.preventDefault();

          sendMessage(
            messages,
            input.value,
          );

          input.value = "";
        }
      },
    );
  }

  onDOMReady(initialize);
})();