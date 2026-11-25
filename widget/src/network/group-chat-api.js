// Requests for the group chat endpoints in backend/app/api/routes/group_chat.py.
// apiUrl("group-chats") -> /talk-sketch/chatbot-api/group-chats (Vite proxy)
//                       -> FastAPI /api/group-chats
import { apiUrl } from "../config.js";

export function createGroupChatClient() {
  const root = apiUrl("group-chats");

  async function request(path, body) {
    const res = await fetch(`${root}${path}`, {
      method: body ? "POST" : "GET",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : "";
      throw new Error(detail || `Request failed with status ${res.status}.`);
    }
    return data;
  }

  return {
    listAgents: () => request("/agents"),
    create: (agentIds, topic = "") => request("", { agent_ids: agentIds, topic }),
    send: (roomId, text, replies = 0) => request(`/${roomId}/messages`, { text, replies }),
    runTurns: (roomId, count = 1) => request(`/${roomId}/turns`, { count }),
  };
}