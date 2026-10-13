type Rectangle = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export function rectanglesOverlap(
  a: Rectangle,
  b: Rectangle,
  padding = 20,
) {
  return !(
    a.x + a.width + padding < b.x ||
    a.x > b.x + b.width + padding ||
    a.y + a.height + padding < b.y ||
    a.y > b.y + b.height + padding
  );
}


export function estimateMathSize(
  expression: string,
) {
  const characterWidth = 20;

  return {
    width: Math.max(
      80,
      expression.length *
        characterWidth,
    ),

    height: 40,
  };
}


export function findAvailablePosition(
  elements: readonly any[],
  width: number,
  height: number,
  options: {
    startX?: number;
    startY?: number;
    stepX?: number;
    stepY?: number;
    maxX?: number;
    padding?: number;
  } = {},
) {
  const {
    startX = 100,
    startY = 100,

    stepX = 50,
    stepY = 50,

    maxX = 1200,

    padding = 20,
  } = options;

  let x = startX;
  let y = startY;

  const activeElements =
    elements.filter(
      (element) =>
        !element.isDeleted,
    );

  while (true) {
    const candidate = {
      x,
      y,
      width,
      height,
    };

    const collision =
      activeElements.some(
        (element) =>
          rectanglesOverlap(
            candidate,
            {
              x: element.x,
              y: element.y,
              width: element.width,
              height: element.height,
            },
            padding,
          ),
      );

    if (!collision) {
      return {
        x,
        y,
      };
    }

    x += stepX;

    if (x > maxX) {
      x = startX;
      y += stepY;
    }
  }
}