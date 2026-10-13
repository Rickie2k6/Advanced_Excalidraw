
type Point = [number, number];

const GLYPHS: Record<string, Point[][]> = {
  "0": [
    [[0, 0], [8, 0], [10, 3], [10, 17], [8, 20], [0, 20], [-2, 17], [-2, 3], [0, 0]],
  ],

  "1": [
    [[3, 4], [6, 0], [6, 20]],
  ],

  "2": [
    [[0, 4], [2, 0], [8, 0], [10, 3], [10, 7], [0, 20], [10, 20]],
  ],

  "3": [
    [[0, 0], [8, 0], [10, 3], [8, 9], [10, 12], [10, 17], [8, 20], [0, 20]],
  ],

  "4": [
    [[8, 20], [8, 0]],
    [[0, 12], [10, 12]],
    [[0, 12], [7, 0]],
  ],

  "5": [
    [[10, 0], [0, 0], [0, 9], [7, 9], [10, 12], [10, 17], [7, 20], [0, 20]],
  ],

  "6": [
    [[10, 0], [3, 0], [0, 4], [0, 16], [3, 20], [8, 20], [10, 17], [10, 12], [8, 9], [0, 9]],
  ],

  "7": [
    [[0, 0], [10, 0], [3, 20]],
  ],

  "8": [
    [[3, 0], [8, 0], [10, 3], [10, 7], [8, 10], [3, 10], [0, 7], [0, 3], [3, 0]],
    [[3, 10], [8, 10], [10, 13], [10, 17], [8, 20], [3, 20], [0, 17], [0, 13], [3, 10]],
  ],

  "9": [
    [[10, 11], [2, 11], [0, 8], [0, 3], [2, 0], [7, 0], [10, 4], [10, 20]],
  ],

  "x": [
    [[0, 2], [10, 18]],
    [[10, 2], [0, 18]],
  ],

  "X": [
    [[0, 2], [10, 18]],
    [[10, 2], [0, 18]],
  ],

  "+": [
    [[5, 2], [5, 18]],
    [[0, 10], [10, 10]],
  ],

  "-": [
    [[0, 10], [10, 10]],
  ],

  "=": [
    [[0, 7], [10, 7]],
    [[0, 13], [10, 13]],
  ],
};

/**
 * Transform glyph points into Excalidraw scene coordinates.
 */
function transformStroke(
  stroke: Point[],
  offsetX: number,
  offsetY: number,
  scale: number,
): Point[] {
  return stroke.map(
    ([x, y]): Point => [
      offsetX + x * scale,
      offsetY + y * scale,
    ],
  );
}

/**
 * Convert a mathematical expression into Excalidraw
 * freedraw elements.
 *
 * Each glyph can contain multiple independent strokes.
 * Each stroke becomes one freedraw element.
 */
export function expressionToFreedraw(
  expression: string,
  startX: number,
  startY: number,
  options: {
    scale?: number;
    spacing?: number;
  } = {},
) {
  const {
    scale = 1.5,
    spacing = 8,
  } = options;

  const elements: any[] = [];

  let cursorX = startX;

  for (const char of expression) {
    if (char === " ") {
      cursorX += 8 * scale;
      continue;
    }

    const glyph = GLYPHS[char];

    if (!glyph) {
      cursorX += 12 * scale;
      continue;
    }

    for (const stroke of glyph) {
      const transformed = transformStroke(
        stroke,
        cursorX,
        startY,
        scale,
      );

      const minX = Math.min(
        ...transformed.map(([x]) => x),
      );

      const minY = Math.min(
        ...transformed.map(([, y]) => y),
      );

      const maxX = Math.max(
        ...transformed.map(([x]) => x),
      );

      const maxY = Math.max(
        ...transformed.map(([, y]) => y),
      );

      // Excalidraw freedraw points must be relative
      // to the element's own x/y position.
      const relativePoints: Point[] = transformed.map(
        ([x, y]): Point => [
          x - minX,
          y - minY,
        ],
      );

      // Use a consistent pressure value for every point.
      // These strokes are generated programmatically,
      // rather than recorded from pen input.
      const pressures = relativePoints.map(
        () => 0.5,
      );

      elements.push({
        type: "freedraw",

        groupIds: [],
        boundElements: null,
        frameId: null,


        x: minX,
        y: minY,

        width: Math.max(
          1,
          maxX - minX,
        ),

        height: Math.max(
          1,
          maxY - minY,
        ),

        points: relativePoints,

        pressures,

        simulatePressure: false,

        strokeColor: "#1e1e1e",

        backgroundColor: "transparent",

        fillStyle: "solid",

        strokeWidth: 1,

        strokeStyle: "solid",

        roughness: 0,

        opacity: 100,
      });
    }

    cursorX += 12 * scale + spacing;
  }

  return elements;
}
