import { CaptureUpdateAction } from "@excalidraw/excalidraw";
import {
  newElement,
  newFreeDrawElement,
  syncInvalidIndices,
} from "@excalidraw/element";
import { pointFrom } from "@excalidraw/math";

import type { ExcalidrawElement } from "@excalidraw/element/types";
import type { ExcalidrawImperativeAPI } from "@excalidraw/excalidraw/types";

import { expressionToFreedraw, measureMathExpression } from "./math-freedraw";
import { findAvailablePosition } from "./math-placement";

/** Default render scale of math-freedraw glyphs. */
export const BASE_MATH_SCALE = 1.5;
/** Vertical gap between a step and the anchor above it, at scale 1. */
export const STEP_GAP = 35;

export type WriteMathOptions = {
  expression: string;
  /** Start of the free-space search (or exact x when `exact`). */
  x?: number;
  y?: number;
  /**
   * Exact top-left corner chosen by the backend (e.g. an empty spot inside a
   * worksheet question). No collision search is done: the backend already
   * avoided existing content, and a search would treat the worksheet image as
   * an obstacle and push the solution off the page.
   */
  position?: { x: number; y: number };
  /** Place at x / directly below the anchors without a collision search. */
  exact?: boolean;
  /** Relative size: 1 = default, 0.8 = 80%. */
  scale?: number;
  anchorElementIds?: string[];
  solutionGroupId?: string;
  actionId?: string;
};

export function createCanvasActions(api: ExcalidrawImperativeAPI) {
  const commit = (elements: ExcalidrawElement[]) => {
    if (!elements.length) {
      throw new Error("No canvas elements were generated.");
    }
    // Read the current scene at commit time so concurrent edits are retained.
    api.updateScene({
      // Constructors leave indices null. Sync the complete scene so appended
      // elements follow existing content, including deleted elements.
      elements: syncInvalidIndices([
        ...api.getSceneElementsIncludingDeleted(),
        ...elements,
      ]),
      captureUpdate: CaptureUpdateAction.IMMEDIATELY,
    });
    const ids = elements.map((element) => element.id);
    const current = new Set(
      api.getSceneElements().map((element) => element.id),
    );
    if (!ids.every((id) => current.has(id))) {
      throw new Error("Canvas did not retain the new elements.");
    }
    return { success: true, element_ids: ids };
  };
  return {
    async addEllipse({
      x,
      y,
      width,
      height,
    }: {
      x: number;
      y: number;
      width: number;
      height: number;
    }) {
      if (
        ![x, y, width, height].every(Number.isFinite) ||
        width <= 0 ||
        height <= 0
      ) {
        throw new Error("Invalid ellipse coordinates.");
      }
      return commit([
        newElement({
          type: "ellipse",
          x,
          y,
          width,
          height,
          strokeColor: "#e03131",
          backgroundColor: "transparent",
          strokeWidth: 2,
        }),
      ]);
    },
    async writeMath({
      expression,
      x,
      y,
      position,
      exact = false,
      scale = 1,
      anchorElementIds = [],
      solutionGroupId,
      actionId,
    }: WriteMathOptions) {
      if (typeof expression !== "string" || !expression.trim()) {
        throw new Error("A mathematical expression is required.");
      }
      if (!Number.isFinite(scale) || scale <= 0 || scale > 3) {
        throw new Error("Invalid math scale.");
      }
      if (
        position != null &&
        !(Number.isFinite(position.x) && Number.isFinite(position.y))
      ) {
        throw new Error("Invalid math position.");
      }
      const scene = api.getSceneElements();
      // Idempotence applies to a specific solution step, not repeated user commands.
      const existing = actionId
        ? scene.filter(
            (element) => element.customData?.chatbotActionId === actionId,
          )
        : [];
      if (existing.length) {
        return {
          success: true,
          element_ids: existing.map((element) => element.id),
        };
      }
      const renderScale = BASE_MATH_SCALE * scale;
      const size = measureMathExpression(expression, { scale: renderScale });
      const anchors = scene.filter((element) =>
        anchorElementIds.includes(element.id),
      );
      if (anchorElementIds.length && !anchors.length) {
        throw new Error(
          "The source equation was removed. Please retry solving.",
        );
      }
      const startX =
        x ??
        (anchors.length
          ? Math.min(...anchors.map((element) => element.x))
          : 100);
      const startY =
        y ??
        (anchors.length
          ? Math.max(...anchors.map((element) => element.y + element.height)) +
            STEP_GAP * scale
          : 100);
      const placed = position
        ? position
        : exact
        ? { x: startX, y: startY }
        : findAvailablePosition(scene, size.width, size.height, {
            startX,
            startY,
            maxX: Math.max(1200, startX + size.width),
          });
      const elements = expressionToFreedraw(expression, placed.x, placed.y, {
        scale: renderScale,
      }).map((element) =>
        newFreeDrawElement({
          ...element,
          points: element.points.map(([px, py]) => pointFrom(px, py)),
          groupIds: solutionGroupId ? [solutionGroupId] : [],
          customData: {
            chatbotGenerated: true,
            chatbotActionId: actionId ?? null,
          },
        }),
      );
      return commit(elements);
    },
  };
}