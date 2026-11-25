import { API_CHAT_URL } from "../config.js";

export async function requestChat(question, scene, whiteboard) {
  const body = new FormData();
  body.append("question", question);
  body.append("scene_json", JSON.stringify({
    elements: scene?.elements ?? [],
    files: scene?.files ?? {},
  }));
  if (whiteboard instanceof Blob) {
    body.append("whiteboard", whiteboard, "whiteboard.png");
  }
  const response = await fetch(API_CHAT_URL, { method: "POST", body });
  if (!response.ok) {
    const detail = (await response.text()).slice(0, 500);
    throw new Error(`Chat request failed (HTTP ${response.status}): ${detail || response.statusText}`);
  }
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("The chatbot returned invalid JSON. Check the API proxy and backend logs.");
  }
  if (!data || typeof data !== "object" || Array.isArray(data) ||
      typeof data.answer !== "string" ||
      !(data.visual_action == null || (typeof data.visual_action === "object" && !Array.isArray(data.visual_action)))) {
    throw new Error("Malformed chatbot response: expected answer and optional visual_action.");
  }
  if (!data.answer.trim() && !data.visual_action) {
    throw new Error("The chatbot returned an empty answer without a canvas action.");
  }
  return data;
}
