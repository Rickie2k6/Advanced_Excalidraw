import { validateFractionalIndices } from "@excalidraw/element";
import { Excalidraw } from "@excalidraw/excalidraw";

import { pointFrom } from "@excalidraw/math";
import { act } from "@testing-library/react";

import type { ExcalidrawImperativeAPI } from "@excalidraw/excalidraw/types";

import { API } from "../../packages/excalidraw/tests/helpers/api";
import {
  render,
  unmountComponent,
} from "../../packages/excalidraw/tests/test-utils";
import { createCanvasActions } from "../chatbot-bridge";
import { chatbotApiUrl } from "../chatbot-backend-url";
import { expressionToFreedraw, measureMathExpression } from "../math-freedraw";

unmountComponent();

describe("chatbot browser API URLs", () => {
  it.each([
    ["", "/talk-sketch/api/chat"],
    ["/talk-sketch", "/talk-sketch/api/chat"],
    ["/talk-sketch/api/", "/talk-sketch/api/chat"],
    ["/talk-sketch/chatbot-api", "/talk-sketch/chatbot-api/chat"],
    ["http://127.0.0.1:65532/", "http://127.0.0.1:65532/api/chat"],
  ])("uses base %s without doubling prefixes", (base, expected) => {
    expect(chatbotApiUrl("chat", base)).toBe(expected);
    expect(chatbotApiUrl("/api/chat", base)).toBe(expected);
  });
});

describe("chatbot native canvas actions", () => {
  let api: ExcalidrawImperativeAPI;
  beforeEach(async () => {
    await render(
      <Excalidraw
        onExcalidrawAPI={(value) => {
          if (value) {
            api = value;
          }
        }}
      />,
    );
    API.setElements([]);
    const updateScene = api.updateScene;
    vi.spyOn(api, "updateScene").mockImplementation((sceneData) => {
      // Validate before Scene can repair indices: the bridge must submit a
      // valid scene rather than rely on automatic recovery after a warning.
      if (sceneData.elements) {
        validateFractionalIndices(sceneData.elements, {
          shouldThrow: true,
          includeBoundTextValidation: false,
          ignoreLogs: true,
        });
      }
      return updateScene(sceneData);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("commits x^2 + 2x + 1 as valid native freedraw strokes", async () => {
    let result;
    await act(async () => {
      result = await createCanvasActions(api).writeMath({
        expression: "x^2 + 2x + 1",
      });
    });
    expect(result).toMatchObject({ success: true });
    const elements = api.getSceneElements();
    expect(elements.length).toBeGreaterThan(0);
    for (const element of elements) {
      expect(element.type).toBe("freedraw");
      expect(element.version).toBeGreaterThan(0);
      expect(Number.isFinite(element.seed)).toBe(true);
      expect(element.customData?.chatbotGenerated).toBe(true);
    }
    expect(measureMathExpression("x^2").height).toBeGreaterThan(
      measureMathExpression("x").height,
    );
    expect(expressionToFreedraw("x^{2}", 0, 0)).toEqual(
      expressionToFreedraw("x^2", 0, 0),
    );
  });

  it("commits a visible ellipse using the returned canvas coordinates", async () => {
    await act(async () => {
      await createCanvasActions(api).addEllipse({
        x: 20,
        y: 30,
        width: 100,
        height: 50,
      });
    });
    expect(api.getSceneElements()).toEqual([
      expect.objectContaining({
        type: "ellipse",
        x: 20,
        y: 30,
        width: 100,
        height: 50,
      }),
    ]);
  });

  it("places grouped steps beneath source strokes and retains previous content", async () => {
    const source = API.createElement({
      type: "freedraw",
      x: 200,
      y: 200,
      width: 100,
      height: 40,
      points: [pointFrom(0, 0), pointFrom(100, 40)],
    });
    API.setElements([source]);
    const actions = createCanvasActions(api);
    let first!: Awaited<ReturnType<typeof actions.writeMath>>;
    await act(async () => {
      first = await actions.writeMath({
        expression: "2x=4",
        anchorElementIds: [source.id],
        solutionGroupId: "solution1",
        actionId: "step1",
      });
    });
    const firstElements = api
      .getSceneElements()
      .filter((element) => first.element_ids.includes(element.id));
    expect(
      firstElements.every((element) => element.y > source.y + source.height),
    ).toBe(true);
    await act(async () => {
      await actions.writeMath({
        expression: "x=2",
        anchorElementIds: first.element_ids,
        solutionGroupId: "solution1",
        actionId: "step2",
      });
    });
    const generated = api
      .getSceneElements()
      .filter((element) => element.id !== source.id);
    expect(
      generated.every((element) => element.groupIds.includes("solution1")),
    ).toBe(true);
    expect(
      api.getSceneElements().find((element) => element.id === source.id),
    ).toBeDefined();
    const count = generated.length;
    await act(async () => {
      await actions.writeMath({
        expression: "2x=4",
        solutionGroupId: "solution1",
        actionId: "step1",
      });
    });
    expect(api.getSceneElements().length).toBe(count + 1);
  });

  it("preserves existing indices and deleted elements across successive commits", async () => {
    const source = API.createElement({ type: "rectangle" });
    const deleted = API.createElement({ type: "ellipse", isDeleted: true });
    API.setElements([source, deleted]);
    const originals = api.getSceneElementsIncludingDeleted().map((element) => ({
      id: element.id,
      index: element.index,
      version: element.version,
      isDeleted: element.isDeleted,
    }));
    const actions = createCanvasActions(api);
    await act(async () => {
      await actions.writeMath({ expression: "x=2" });
      await actions.addEllipse({ x: 20, y: 30, width: 100, height: 50 });
      await actions.writeMath({ expression: "2+2=4" });
    });
    const elements = api.getSceneElementsIncludingDeleted();
    expect(elements.slice(0, originals.length)).toMatchObject(originals);
    expect(elements.length).toBeGreaterThan(originals.length + 1);
    validateFractionalIndices(elements, {
      shouldThrow: true,
      includeBoundTextValidation: false,
      ignoreLogs: true,
    });
  });

  it("keeps fraction rendering and refuses unsupported math or missing anchors", async () => {
    const actions = createCanvasActions(api);
    await act(async () => {
      await actions.writeMath({ expression: "x=3/2" });
    });
    const count = api.getSceneElements().length;
    await expect(actions.writeMath({ expression: "sin(x)" })).rejects.toThrow(
      "Unsupported math character",
    );
    await expect(
      actions.writeMath({ expression: "x=2", anchorElementIds: ["deleted"] }),
    ).rejects.toThrow("source equation was removed");
    expect(api.getSceneElements().length).toBe(count);
  });

  // ---------- "solve question N": exact placement inside a worksheet ----------

  const bounds = (ids: readonly string[]) => {
    const elements = api
      .getSceneElements()
      .filter((element) => ids.includes(element.id));
    return {
      minX: Math.min(...elements.map((e) => e.x)),
      minY: Math.min(...elements.map((e) => e.y)),
      maxX: Math.max(...elements.map((e) => e.x + e.width)),
      maxY: Math.max(...elements.map((e) => e.y + e.height)),
    };
  };

  it("writes at an exact position on top of a worksheet instead of moving away", async () => {
    // A large element standing in for the worksheet image: the collision
    // search would push the solution outside it.
    const worksheet = API.createElement({
      type: "rectangle",
      x: 0,
      y: 0,
      width: 1300,
      height: 800,
    });
    API.setElements([worksheet]);
    let result!: { element_ids: string[] };
    await act(async () => {
      result = await createCanvasActions(api).writeMath({
        expression: "7x-2(1)=5",
        position: { x: 860, y: 385 },
      });
    });
    const box = bounds(result.element_ids);
    expect(box.minX).toBeCloseTo(860);
    expect(box.minY).toBeCloseTo(385);
    expect(box.maxX).toBeLessThan(1300);
    expect(box.maxY).toBeLessThan(800);
  });

  it("stacks exact steps directly below the previous step in the same column", async () => {
    const worksheet = API.createElement({
      type: "rectangle",
      x: 0,
      y: 0,
      width: 1300,
      height: 800,
    });
    API.setElements([worksheet]);
    const actions = createCanvasActions(api);
    let first!: { element_ids: string[] };
    let second!: { element_ids: string[] };
    await act(async () => {
      first = await actions.writeMath({
        expression: "7x-2y=5",
        position: { x: 860, y: 385 },
        actionId: "q2-step-1",
      });
      second = await actions.writeMath({
        expression: "7x-3y=4",
        anchorElementIds: first.element_ids,
        x: 860,
        exact: true,
        actionId: "q2-step-2",
      });
    });
    const a = bounds(first.element_ids);
    const b = bounds(second.element_ids);
    expect(b.minX).toBeCloseTo(860);
    expect(b.minY).toBeGreaterThan(a.maxY);
    expect(b.minY - a.maxY).toBeLessThan(60);
    expect(b.maxY).toBeLessThan(800);
  });

  it("scales the handwriting down when asked", async () => {
    const actions = createCanvasActions(api);
    let full!: { element_ids: string[] };
    let small!: { element_ids: string[] };
    await act(async () => {
      full = await actions.writeMath({
        expression: "x+y=5",
        position: { x: 0, y: 0 },
      });
      small = await actions.writeMath({
        expression: "x+y=5",
        position: { x: 0, y: 200 },
        scale: 0.5,
      });
    });
    const f = bounds(full.element_ids);
    const s = bounds(small.element_ids);
    expect(s.maxX - s.minX).toBeCloseTo((f.maxX - f.minX) / 2, 0);
    await expect(
      actions.writeMath({ expression: "x=1", scale: 0 }),
    ).rejects.toThrow("Invalid math scale");
    await expect(
      actions.writeMath({ expression: "x=1", position: { x: NaN, y: 0 } }),
    ).rejects.toThrow("Invalid math position");
  });

  it.each([
    "7x-2y=5",
    "x+y+z=6",
    "(x-2)(x-3)=0",
    "x≈3.303",
    "Δ=13",
    "(3,2)",
    "x^4-5x^2+4=0",
  ])("draws %s", (expression) => {
    expect(expressionToFreedraw(expression, 0, 0).length).toBeGreaterThan(0);
  });
});
