import {
  groupEquationStrokes,
} from "../utils/equation-groups.js";


function getBridge() {
  const bridge =
    window.__excalidrawChatbotBridge;

  if (!bridge) {
    throw new Error(
      "Excalidraw chatbot bridge is not available.",
    );
  }

  return bridge;
}


export function getExcalidrawScene() {
  return getBridge().getScene();
}


export async function getEquationContext() {
  const bridge = getBridge();

  const scene = bridge.getScene();

  const groups = groupEquationStrokes(
    scene.elements,
  );

  console.log(
    `[Chatbot] detected ${groups.length} equation groups`,
  );

  const boxes = [];

  for (const group of groups) {
    console.log(
      `[Chatbot] Box ${group.id}`,
      group.bbox,
      group.elementIds,
    );

    const image =
      await bridge.exportElementsToPng(
        group.elementIds,
      );

    boxes.push({
      id: group.id,
      bbox: group.bbox,
      elementIds: group.elementIds,
      image,
    });
  }

  return {
    groups: boxes,
  };
}