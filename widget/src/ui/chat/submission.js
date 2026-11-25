// One command path for clicks and Enter; sendMessage owns the in-flight guard.
export function bindChatSubmission({ messages, input, button }, sendMessage) {
  if (input.dataset.chatSubmissionBound) return;
  input.dataset.chatSubmissionBound = "true";
  const submit = () => {
    const text = input.value;
    if (!text.trim()) return;
    input.value = "";
    void sendMessage(messages, text);
  };
  button.addEventListener("click", event => {
    event.preventDefault();
    submit();
  });
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.isComposing && !event.repeat) {
      event.preventDefault();
      submit();
    }
  });
}
