
/**
 * Animate native Excalidraw freedraw strokes on an SVG overlay.
 * The caller commits the actual Excalidraw elements in onComplete.
 */

type Point = readonly [number, number];

export type HandwritingStroke = {
  x: number;
  y: number;
  points: readonly Point[];
  strokeColor: string;
  strokeWidth: number;
};

type Viewport = {
  scrollX: number;
  scrollY: number;
  zoom: number;
  offsetLeft: number;
  offsetTop: number;
};

type AnimationOptions = {
  strokes: readonly HandwritingStroke[];
  container: HTMLElement;
  getViewport: () => Viewport;
  durationPerStroke?: number;
  signal?: AbortSignal;
  onComplete?: () => void | Promise<void>;
};

export async function animateMathHandwriting({
  strokes,
  container,
  getViewport,
  durationPerStroke = 180,
  signal,
  onComplete,
}: AnimationOptions): Promise<void> {
  const namespace = "http://www.w3.org/2000/svg";

  const svg = document.createElementNS(namespace, "svg");

  Object.assign(svg.style, {
    position: "absolute",
    inset: "0",
    width: "100%",
    height: "100%",
    pointerEvents: "none",
    zIndex: "15",
    overflow: "hidden",
  });

  container.appendChild(svg);

  const paths = strokes.map((stroke) => {
    const path = document.createElementNS(namespace, "path");

    path.setAttribute("fill", "none");
    path.setAttribute("stroke", stroke.strokeColor);
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");

    svg.appendChild(path);

    return path;
  });

  const draw = (strokeIndex: number, progress: number) => {
    const viewport = getViewport();
    const rect = container.getBoundingClientRect();
    const zoom = viewport.zoom;

    const stroke = strokes[strokeIndex];
    const points = stroke.points;

    if (!points.length) {
      return;
    }

    const toScreen = ([px, py]: Point): Point => [
      (stroke.x + px + viewport.scrollX) * zoom +
        viewport.offsetLeft - rect.left,
      (stroke.y + py + viewport.scrollY) * zoom +
        viewport.offsetTop - rect.top,
    ];

    const path = paths[strokeIndex];

    path.setAttribute(
      "stroke-width",
      String(stroke.strokeWidth * zoom),
    );

    // Handle a stroke containing only one point.
    if (points.length === 1) {
      const [x, y] = toScreen(points[0]);

      path.setAttribute(
        "d",
        `M ${x} ${y} L ${x + 0.01} ${y}`,
      );

      return;
    }

    const segmentCount = points.length - 1;

    const position =
      Math.max(0, Math.min(1, progress)) * segmentCount;

    const completed = Math.floor(position);
    const fraction = position - completed;

    const visible = points
      .slice(0, completed + 1)
      .map(toScreen);

    if (completed < segmentCount) {
      const start = points[completed];
      const end = points[completed + 1];

      visible.push(
        toScreen([
          start[0] + (end[0] - start[0]) * fraction,
          start[1] + (end[1] - start[1]) * fraction,
        ]),
      );
    }

    const d = visible
      .map(
        ([x, y], index) =>
          `${index === 0 ? "M" : "L"} ${x} ${y}`,
      )
      .join(" ");

    path.setAttribute("d", d);
  };

  try {
    for (let i = 0; i < strokes.length; i++) {
      if (signal?.aborted) {
        throw new Error(
          "Handwriting animation cancelled.",
        );
      }

      await new Promise<void>((resolve, reject) => {
        let start: number | undefined;

        const frame = (now: number) => {
          if (signal?.aborted) {
            reject(
              new Error("Handwriting animation cancelled."),
            );
            return;
          }

          start ??= now;

          const progress = Math.min(
            1,
            (now - start) / Math.max(1, durationPerStroke),
          );

          draw(i, progress);

          if (progress < 1) {
            requestAnimationFrame(frame);
          } else {
            resolve();
          }
        };

        requestAnimationFrame(frame);
      });
    }

    if (signal?.aborted) {
      throw new Error(
        "Handwriting animation cancelled.",
      );
    }

    // Commit native Excalidraw elements after animation.
    await onComplete?.();

    // // Give Excalidraw time to paint before removing SVG.
    // await new Promise<void>((resolve) =>
    //   requestAnimationFrame(() => resolve()),
    // );
  } finally {
    svg.remove();
  }
}
