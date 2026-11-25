import { beforeEach, afterEach, describe, it, expect, vi } from "vitest";
import { apiUrl, API_CHAT_URL } from "../src/config.js";
import { requestChat } from "../src/network/chat.js";
import { executeVisualAction } from "../src/integrations/visual-actions.js";
import { writeMath } from "../src/integrations/excalidraw.js";
import { sendMessage, createMessagesArea } from "../src/ui/chat/messages.js";
import { bindChatSubmission } from "../src/ui/chat/submission.js";

const success = id => ({ success: true, element_ids: [id] });
const response = data => ({ ok: true, json: async () => data });
beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); delete window.__excalidrawChatbotBridge; });

describe("API URLs and multipart contract", () => {
  it("builds browser URLs without duplicate prefixes", () => {
    expect(API_CHAT_URL).toBe("/talk-sketch/chatbot-api/chat");
    expect(apiUrl("/client-ip/confirm/")).toBe("/talk-sketch/chatbot-api/client-ip/confirm");
    expect(apiUrl("health")).toBe("/talk-sketch/chatbot-api/health");
    for (const path of ["api/chat", "chatbot-api/chat", "talk-sketch/api/chat"]) expect(() => apiUrl(path)).toThrow();
  });
  it("preserves scene images and all multipart fields without Content-Type", async () => {
    fetch.mockResolvedValue(response({ answer: "ok", visual_action: null }));
    const scene = { elements: [{ id: "image" }], files: { f: { dataURL: "data:image/png;base64,AA==" } } };
    await requestChat("circle this", scene, new Blob(["image"]));
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe(API_CHAT_URL);
    expect(options.headers).toBeUndefined();
    expect(options.body.get("question")).toBe("circle this");
    expect(JSON.parse(options.body.get("scene_json"))).toEqual(scene);
    expect(options.body.get("whiteboard").name).toBe("whiteboard.png");
  });
  it.each([null, {}, { answer: 7 }, { answer: "" }, { answer: "ok", visual_action: [] }])("rejects malformed or empty responses: %j", async data => {
    fetch.mockResolvedValue(response(data));
    await expect(requestChat("hi", null, null)).rejects.toThrow();
  });
  it("reports HTTP failures and non-JSON proxy responses", async () => {
    fetch.mockResolvedValue({ ok: false, status: 502, text: async () => "upstream unavailable" });
    await expect(requestChat("hi")).rejects.toThrow("HTTP 502");
    fetch.mockResolvedValue({ ok: true, json: async () => { throw new Error(); } });
    await expect(requestChat("hi")).rejects.toThrow("invalid JSON");
  });
});

describe("canvas action contracts", () => {
  it("awaits circle completion and reports actual failures", async () => {
    let finish;
    const bridge = { addEllipse: vi.fn(() => new Promise(resolve => { finish = resolve; })) };
    let done = false;
    const pending = executeVisualAction(bridge, { action: "circle", x: 1, y: 2, width: 3, height: 4 }).then(() => { done = true; });
    await Promise.resolve(); expect(done).toBe(false);
    finish(success("circle")); await pending; expect(done).toBe(true);
    bridge.addEllipse.mockResolvedValue({ success: false, error: "canvas unavailable" });
    await expect(executeVisualAction(bridge, { action: "circle", x: 1, y: 2, width: 3, height: 4 })).rejects.toThrow("canvas unavailable");
  });
  it("passes write expressions and all integration options unchanged", async () => {
    const bridge = { writeMath: vi.fn().mockResolvedValue(success("math")) };
    window.__excalidrawChatbotBridge = bridge;
    await executeVisualAction(bridge, { action: "write_math", expression: "x^2 + 2x + 1" });
    expect(bridge.writeMath).toHaveBeenCalledWith({ expression: "x^2 + 2x + 1" });
    const options = { expression: "x=2", anchorElementIds: ["source"], solutionGroupId: "g", actionId: "a" };
    await writeMath(options); expect(bridge.writeMath).toHaveBeenLastCalledWith(options);
  });
  it.each(["write_math_steps", "write_multiple_math_steps"])("keeps anchors and groups and skips original for %s", async action => {
    const bridge = { writeMath: vi.fn().mockResolvedValueOnce(success("step1")).mockResolvedValueOnce(success("step2")) };
    const solution = { steps: ["2x+1=5", "2x=4", "x=2"], source_stroke_ids: ["original"], source_equation_id: "eq1" };
    await executeVisualAction(bridge, action === "write_math_steps" ? { action, ...solution } : { action, solutions: [solution] });
    expect(bridge.writeMath).toHaveBeenCalledTimes(2);
    expect(bridge.writeMath.mock.calls[0][0]).toMatchObject({ expression: "2x=4", anchorElementIds: ["original"] });
    expect(bridge.writeMath.mock.calls[1][0]).toMatchObject({ expression: "x=2", anchorElementIds: ["step1"], solutionGroupId: bridge.writeMath.mock.calls[0][0].solutionGroupId });
  });
  it("draws the original for explicit solves without anchors", async () => {
    const bridge = { writeMath: vi.fn().mockResolvedValue(success("s")) };
    await executeVisualAction(bridge, { action: "write_math_steps", steps: ["2x=4", "x=2"] });
    expect(bridge.writeMath.mock.calls[0][0].expression).toBe("2x=4");
  });
  it("writes a worksheet overflow solution at the supplied position and reports where it went", async () => {
    const bridge = { writeMath: vi.fn().mockResolvedValueOnce(success("first")).mockResolvedValueOnce(success("last")) };
    const steps = ["2x=4", "x=2"];
    const result = await executeVisualAction(bridge, {
      action: "write_math_steps", question_number: 2, answer: "x = 2", steps,
      columns: [{ x: 1400, y: 400, steps }], scale: 1, placement: "beside",
    });
    expect(bridge.writeMath.mock.calls[0][0]).toMatchObject({ expression: "2x=4", position: { x: 1400, y: 400 } });
    expect(bridge.writeMath.mock.calls[1][0]).toMatchObject({ expression: "x=2", x: 1400, exact: true, anchorElementIds: ["first"] });
    expect(result.message).toBe("Solved question 2: x = 2. I wrote the steps beside the worksheet.");
  });
  it.each([{ action: "unknown" }, { action: "circle", x: 0, y: 0, width: -1, height: 3 }, { action: "write_math" }, { action: "write_multiple_math_steps", solutions: [{}] }])("rejects invalid actions %j", async action => {
    await expect(executeVisualAction({ writeMath: vi.fn(), addEllipse: vi.fn() }, action)).rejects.toThrow();
  });
});

describe("submission and user feedback", () => {
  function setup() {
    const { messages } = createMessagesArea();
    const input = document.createElement("input"), button = document.createElement("button");
    const bridge = { getScene: () => ({ elements: [], files: {} }), exportWhiteboardToPng: async () => null, writeMath: vi.fn().mockResolvedValue(success("m")) };
    window.__excalidrawChatbotBridge = bridge;
    return { messages, input, button, bridge };
  }
  it.each(["click", "Enter"])("sends one request for %s even if registration is repeated", async event => {
    const ui = setup(); fetch.mockResolvedValue(response({ answer: "", visual_action: { action: "write_math", expression: "x=2" } }));
    bindChatSubmission(ui, sendMessage); bindChatSubmission(ui, sendMessage);
    ui.input.value = "Write x=2";
    if (event === "click") ui.button.click();
    else ui.input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(ui.messages.textContent).toContain("Wrote the expression"));
    expect(fetch).toHaveBeenCalledTimes(1); expect(ui.bridge.writeMath).toHaveBeenCalledTimes(1);
  });
  it("retains the in-flight guard and releases it after failure", async () => {
    const ui = setup(); let release;
    fetch.mockImplementationOnce(() => new Promise(resolve => { release = resolve; }));
    const pending = sendMessage(ui.messages, "Write x=2");
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    expect(await sendMessage(ui.messages, "Write x=3")).toBe(false);
    release(response({ answer: "", visual_action: { action: "write_math", expression: "x=2" } }));
    await pending;
    ui.bridge.writeMath.mockResolvedValue({ success: false, error: "unsupported math" });
    fetch.mockResolvedValue(response({ answer: "Done", visual_action: { action: "write_math", expression: "bad" } }));
    await sendMessage(ui.messages, "Write bad");
    expect(ui.messages.textContent).toContain("Canvas action failed: unsupported math");
    expect(ui.messages.textContent).not.toContain("Done");
  });
});
