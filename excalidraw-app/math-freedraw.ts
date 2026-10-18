
type Point = [number, number];

type Glyph = Point[][];

const GLYPHS: Record<string, Glyph> = {
  "0": [
    [[0, 0], [8, 0], [10, 3], [10, 17], [8, 20], [0, 20], [-2, 17], [-2, 3], [0, 0]],
  ],
  "1": [
    [[3, 4], [6, 0], [6, 20]],
  ],
  "2": [
    [[0, 5], [1, 2], [3, 0], [7, 0], [10, 2], [11, 5], [10, 8], [7, 11], [4, 14], [1, 17], [0, 20], [11, 20]],
  ],
  "3": [
    [[0, 1], [4, 0], [8, 0], [11, 3], [10, 6], [7, 9], [4, 10]],
    [[4, 10], [8, 10], [11, 13], [11, 17], [8, 20], [4, 20], [0, 19]],
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
    [[10, 0], [3, 0], [0, 4], [0, 16], [3, 20], [8, 20], [10, 17], [11, 12], [8, 9], [0, 9]],
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
  "/": [
    [[0, 20], [10, 0]],
  ],
};

const GLYPH_WIDTH = 12;
const GLYPH_HEIGHT = 20;
const CHARACTER_GAP = 8;
const FRACTION_GAP = 8;
const FRACTION_PADDING = 5;

type MathLayout = {
  width: number;
  height: number;
  strokes: Point[][];
};

function moveStrokes(
  strokes: Point[][],
  dx: number,
  dy: number,
): Point[][] {
  return strokes.map((stroke) =>
    stroke.map(([x, y]): Point => [x + dx, y + dy]),
  );
}

function layoutText(expression: string): MathLayout {
  const strokes: Point[][] = [];
  let cursorX = 0;

  for (const char of expression) {
    if (char === " ") {
      cursorX += GLYPH_WIDTH;
      continue;
    }

    const glyph = GLYPHS[char];

    if (!glyph) {
      throw new Error(
        `Unsupported math character: "${char}"`,
      );
    }

    strokes.push(...moveStrokes(glyph, cursorX, 0));
    cursorX += GLYPH_WIDTH + CHARACTER_GAP;
  }

  return {
    width: Math.max(
      1,
      cursorX > 0 ? cursorX - CHARACTER_GAP : 1,
    ),
    height: GLYPH_HEIGHT,
    strokes,
  };
}

/**
 * Supports:
 *   x=3/2
 *   3/2
 *   x=12/5
 *
 * Fractions are laid out vertically.
 */
function layoutExpression(expression: string): MathLayout {
  const normalized = expression.replace(/\s+/g, "");

  // Match an optional equation prefix followed by
  // a numeric fraction.
  const match = normalized.match(
    /^(.*?)(-?\d+)\/(\d+)$/,
  );

  if (!match) {
    return layoutText(normalized);
  }

  const [, prefix, numerator, denominator] = match;

  const prefixLayout = layoutText(prefix);
  const numeratorLayout = layoutText(numerator);
  const denominatorLayout = layoutText(denominator);

  const fractionWidth =
    Math.max(
      numeratorLayout.width,
      denominatorLayout.width,
    ) +
    FRACTION_PADDING * 2;

  const fractionHeight =
    GLYPH_HEIGHT * 2 + FRACTION_GAP * 2;

  const prefixGap = prefix ? CHARACTER_GAP : 0;
  const fractionX = prefixLayout.width + prefixGap;

  const numeratorX =
    fractionX +
    (fractionWidth - numeratorLayout.width) / 2;

  const denominatorX =
    fractionX +
    (fractionWidth - denominatorLayout.width) / 2;

  const numeratorY = 0;
  const barY = GLYPH_HEIGHT + FRACTION_GAP / 2;
  const denominatorY = GLYPH_HEIGHT + FRACTION_GAP;

  const prefixY =
    (fractionHeight - prefixLayout.height) / 2;

  const strokes: Point[][] = [
    ...moveStrokes(prefixLayout.strokes, 0, prefixY),
    ...moveStrokes(
      numeratorLayout.strokes,
      numeratorX,
      numeratorY,
    ),
    [
      [fractionX, barY],
      [fractionX + fractionWidth, barY],
    ],
    ...moveStrokes(
      denominatorLayout.strokes,
      denominatorX,
      denominatorY,
    ),
  ];

  return {
    width: fractionX + fractionWidth,
    height: fractionHeight,
    strokes,
  };
}

function getStrokeBounds(stroke: Point[]) {
  const xs = stroke.map(([x]) => x);
  const ys = stroke.map(([, y]) => y);

  return {
    minX: Math.min(...xs),
    minY: Math.min(...ys),
    maxX: Math.max(...xs),
    maxY: Math.max(...ys),
  };
}

/**
 * Measure the exact layout used by the renderer.
 */
export function measureMathExpression(
  expression: string,
  options: { scale?: number } = {},
) {
  const scale = options.scale ?? 1.5;
  const layout = layoutExpression(expression);

  return {
    width: layout.width * scale,
    height: layout.height * scale,
  };
}

/**
 * Convert mathematical layout into native
 * Excalidraw freedraw elements.
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
  const scale = options.scale ?? 1.5;
  const layout = layoutExpression(expression);

  return layout.strokes.map((stroke) => {
    const transformed = stroke.map(
      ([x, y]): Point => [
        startX + x * scale,
        startY + y * scale,
      ],
    );

    const { minX, minY, maxX, maxY } =
      getStrokeBounds(transformed);

    const points = transformed.map(
      ([x, y]): Point => [
        x - minX,
        y - minY,
      ],
    );

    return {
      type: "freedraw" as const,
      groupIds: [],
      boundElements: null,
      frameId: null,

      x: minX,
      y: minY,
      width: Math.max(1, maxX - minX),
      height: Math.max(1, maxY - minY),

      points,
      pressures: points.map(() => 0.2),
      simulatePressure: false,

      strokeColor: "#1e1e1e",
      backgroundColor: "transparent",
      fillStyle: "solid" as const,
      strokeWidth: 1,
      strokeStyle: "solid" as const,
      roughness: 0,
      opacity: 100,
    };
  });
}
