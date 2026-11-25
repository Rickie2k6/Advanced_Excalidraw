// This is a browser-facing origin/base, never a FastAPI router prefix.
export function chatbotApiUrl(path: string, configuredBase = "") {
  const base = configuredBase.replace(/\/+$/, "");
  const endpoint = path.replace(/^\/+/, "").replace(/^api\//, "");
  if (!base) {
    return `/talk-sketch/api/${endpoint}`;
  }
  if (/(?:\/api|\/chatbot-api)$/.test(base)) {
    return `${base}/${endpoint}`;
  }
  return `${base}/api/${endpoint}`;
}
