const form =
  document.getElementById("promptForm");

const input =
  document.getElementById("promptInput");

const goBack =
  document.getElementById("goBack");

form.addEventListener(
  "submit",
  (event) => {
    event.preventDefault();

    const prompt =
      input.value.trim();

    if (!prompt) {
      return;
    }

    console.log(
      "[Prompt Page] Initial prompt:",
      prompt,
    );

    // Save it so the Excalidraw/chatbot page
    // can retrieve it.
    sessionStorage.setItem(
      "initialWhiteboardPrompt",
      prompt,
    );

    /*
     * NEXT STEP:
     * Redirect to your Excalidraw UI here.
     *
     * Example:
     *
     * window.location.href =
     *   "YOUR_EXCALIDRAW_URL";
     */
  },
);

goBack.addEventListener(
  "click",
  () => {
    window.history.back();
  },
);