import { useState } from "react";

import "../../../Chatbot/prompt_box/prompt.css";

type PromptPageProps = {
  onSubmit: (prompt: string) => void;
};

const PromptPage = ({ onSubmit }: PromptPageProps) => {
  const [prompt, setPrompt] = useState("");

  const handleSubmit = (
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();

    const trimmedPrompt = prompt.trim();

    if (!trimmedPrompt) {
      return;
    }

    console.log(
      "[Prompt Page] Initial prompt:",
      trimmedPrompt,
    );

    sessionStorage.setItem(
      "initialWhiteboardPrompt",
      trimmedPrompt,
    );

    onSubmit(trimmedPrompt);
  };

  return (
    <div className="prompt-landing-page">
      

      <main className="prompt-page">
        <section className="prompt-container">
          <div className="title-line" />

          <h1>ENTER PROMPT</h1>

          <div className="title-line" />

          <form
            className="prompt-box"
            onSubmit={handleSubmit}
          >
            <textarea
              id="promptInput"
              value={prompt}
              onChange={(event) =>
                setPrompt(event.target.value)
              }
              placeholder="Describe what you want to create..."
              rows={1}
              required
              autoFocus
            />

            <button
              className="submit-button"
              type="submit"
              aria-label="Submit prompt"
            >
              ➤
            </button>
          </form>
        </section>
      </main>
    </div>
  );
};

export default PromptPage;
