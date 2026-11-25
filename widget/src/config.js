// Browser URLs use the Vite proxy. FastAPI itself stays at /api and /health.
export const API_BASE_URL = "/talk-sketch/chatbot-api";

export function apiUrl(path = "") {
  const endpoint = path.replace(/^\/+|\/+$/g, "");
  if (/^(?:api|chatbot-api|talk-sketch)(?:\/|$)/.test(endpoint) ||
      endpoint.includes("://")) {
    throw new Error("Pass an endpoint relative to the chatbot API, such as 'chat'.");
  }
  return endpoint ? `${API_BASE_URL}/${endpoint}` : API_BASE_URL;
}

export const API_CHAT_URL = apiUrl("chat");
export const API_HISTORY_URL = apiUrl("history");
