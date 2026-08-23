import React from "react";

type HintBBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type WhiteboardHint = {
  anchor_equation_id: string;
  equation: string;
  bbox: HintBBox;
  instruction: string;
};

type Props = {
  hints: WhiteboardHint[];
  appState: any;
};

export const WhiteboardHintsOverlay = ({
  hints,
  appState,
}: Props) => {
  if (!appState) {
    return null;
  }

  const zoom =
    typeof appState.zoom === "number"
      ? appState.zoom
      : appState.zoom?.value ?? 1;

  const scrollX = appState.scrollX ?? 0;
  const scrollY = appState.scrollY ?? 0;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        overflow: "hidden",
        zIndex: 20,
      }}
    >
      {hints.map((hint) => {
        if (!hint.bbox) {
          return null;
        }

        const x =
          (hint.bbox.x + scrollX) * zoom;

        const y =
          (hint.bbox.y + scrollY) * zoom;

        const width =
          hint.bbox.width * zoom;

        return (
          <div
            key={hint.anchor_equation_id}
            style={{
              position: "absolute",

              // place bubble above equation
              left: x + width / 2,
              top: y - 12,

              transform:
                "translate(-50%, -100%)",

              maxWidth: 260,
              padding: "8px 12px",

              borderRadius: 8,
              border: "1px solid rgba(0,0,0,0.15)",

              background: "white",

              boxShadow:
                "0 3px 12px rgba(0,0,0,0.15)",

              fontSize: 13,
              lineHeight: 1.4,

              pointerEvents: "none",
            }}
          >
            💡 {hint.instruction}
          </div>
        );
      })}
    </div>
  );
};