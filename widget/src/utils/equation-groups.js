function median(values) {
  if (!values.length) {
    return 20;
  }

  const sorted =
    [...values].sort((a, b) => a - b);

  const middle =
    Math.floor(sorted.length / 2);

  if (sorted.length % 2 === 0) {
    return (
      sorted[middle - 1] +
      sorted[middle]
    ) / 2;
  }

  return sorted[middle];
}


function getStrokeBox(element) {
  return {
    id: element.id,

    x1: element.x,
    y1: element.y,

    x2:
      element.x +
      element.width,

    y2:
      element.y +
      element.height,

    centerY:
      element.y +
      element.height / 2,

    element,
  };
}

/**
 * EN:
 * Calculate the vertical gap between two bounding boxes.
 * Returns 0 when the boxes overlap vertically.
 *
 * VI:
 * Tính khoảng cách theo chiều dọc giữa hai bounding box.
 * Trả về 0 nếu hai box có vùng chiều dọc chồng lên nhau.
 */
function getVerticalGap(boxA, boxB) {
  if (boxA.maxY < boxB.minY) {
    return boxB.minY - boxA.maxY;
  }

  if (boxB.maxY < boxA.minY) {
    return boxA.minY - boxB.maxY;
  }

  return 0;
}


/**
 * EN:
 * Calculate the horizontal gap between two bounding boxes.
 * Returns 0 when the boxes overlap horizontally.
 *
 * VI:
 * Tính khoảng cách theo chiều ngang giữa hai bounding box.
 * Trả về 0 nếu hai box có vùng chiều ngang chồng lên nhau.
 */
function getHorizontalGap(boxA, boxB) {
  if (boxA.maxX < boxB.minX) {
    return boxB.minX - boxA.maxX;
  }

  if (boxB.maxX < boxA.minX) {
    return boxA.minX - boxB.maxX;
  }

  return 0;
}


/**
 * EN:
 * Create a bounding box that covers all strokes in a row.
 *
 * VI:
 * Tạo bounding box bao phủ toàn bộ các stroke trong một row.
 */
function getRowBounds(row) {
  return {
    minX: Math.min(
      ...row.strokes.map(
        (stroke) => stroke.x1,
      ),
    ),

    minY: Math.min(
      ...row.strokes.map(
        (stroke) => stroke.y1,
      ),
    ),

    maxX: Math.max(
      ...row.strokes.map(
        (stroke) => stroke.x2,
      ),
    ),

    maxY: Math.max(
      ...row.strokes.map(
        (stroke) => stroke.y2,
      ),
    ),
  };
}


/**
 * EN:
 * Merge small isolated stroke groups into a nearby equation row.
 *
 * Small symbols such as a superscript, minus sign, dot, or part of
 * a handwritten character may appear vertically separated from the
 * main equation. This step prevents them from becoming a separate
 * equation box.
 *
 * VI:
 * Gộp các nhóm stroke nhỏ bị tách riêng vào equation row gần nhất.
 *
 * Các ký hiệu nhỏ như số mũ, dấu trừ, dấu chấm hoặc một phần của
 * chữ viết tay có thể nằm lệch theo chiều dọc so với phương trình
 * chính. Bước này ngăn chúng bị nhận nhầm thành một equation box riêng.
 */
function mergeSmallOrphanRows(
  rows,
  baseHeight,
) {
  if (rows.length <= 1) {
    return rows;
  }

  const result = [...rows];

  const maxVerticalGap = Math.max(
    25,
    baseHeight * 1.2,
  );

  const maxHorizontalGap = Math.max(
    180,
    baseHeight * 6,
  );

  for (let i = 0; i < result.length; i++) {
    const row = result[i];

    // Only treat very small groups as possible orphan fragments.
    if (row.strokes.length > 2) {
      continue;
    }

    const rowBox =
      getRowBounds(row);

    let bestIndex = -1;
    let bestDistance =
      Infinity;

    for (
      let j = 0;
      j < result.length;
      j++
    ) {
      if (i === j) {
        continue;
      }

      const candidate =
        result[j];

      const candidateBox =
        getRowBounds(candidate);

      const verticalGap =
        getVerticalGap(
          rowBox,
          candidateBox,
        );

      const horizontalGap =
        getHorizontalGap(
          rowBox,
          candidateBox,
        );

      if (
        verticalGap <=
          maxVerticalGap &&
        horizontalGap <=
          maxHorizontalGap
      ) {
        const distance =
          verticalGap +
          horizontalGap * 0.1;

        if (
          distance <
          bestDistance
        ) {
          bestDistance =
            distance;

          bestIndex = j;
        }
      }
    }

    if (bestIndex !== -1) {
      result[
        bestIndex
      ].strokes.push(
        ...row.strokes,
      );

      result[
        bestIndex
      ].centerY =
        result[
          bestIndex
        ].strokes.reduce(
          (sum, stroke) =>
            sum +
            stroke.centerY,
          0,
        ) /
        result[
          bestIndex
        ].strokes.length;

      result.splice(i, 1);

      i--;
    }
  }

  return result;
}

export function groupEquationStrokes(
  elements,
) {
  const strokes = elements
    .filter(
      (element) =>
        element.type === "freedraw",
    )
    .map(getStrokeBox);

  if (!strokes.length) {
    return [];
  }

  /*
   * Very thin strokes such as "-" and "=" should not
   * control our handwriting-height estimate.
   */
  const usefulHeights = strokes
    .map(
      (stroke) =>
        Math.abs(
          stroke.y2 - stroke.y1,
        ),
    )
    .filter(
      (height) => height >= 5,
    );

  const baseHeight =
    median(usefulHeights);

  /*
   * Allows superscripts/subscripts to stay in
   * the same equation while separating equations
   * written on different rows.
   */
  const rowTolerance =
    Math.max(
      25,
      baseHeight * 1.2,
    );

  const sorted = [...strokes].sort(
    (a, b) => {
      if (
        Math.abs(
          a.centerY - b.centerY,
        ) > rowTolerance
      ) {
        return a.centerY - b.centerY;
      }

      return a.x1 - b.x1;
    },
  );

  const rows = [];

  for (const stroke of sorted) {
    let bestRow = null;
    let bestDistance = Infinity;

    for (const row of rows) {
      const distance =
        Math.abs(
          stroke.centerY -
          row.centerY,
        );

      if (
        distance <= rowTolerance &&
        distance < bestDistance
      ) {
        bestDistance = distance;
        bestRow = row;
      }
    }

    if (!bestRow) {
      rows.push({
        strokes: [stroke],
        centerY: stroke.centerY,
      });

      continue;
    }

    bestRow.strokes.push(stroke);

    bestRow.centerY =
      bestRow.strokes.reduce(
        (sum, item) =>
          sum + item.centerY,
        0,
      ) /
      bestRow.strokes.length;
  }


    const mergedRows =
        mergeSmallOrphanRows(
            rows,
            baseHeight,
        );

    mergedRows.sort(
        (a, b) =>
            a.centerY - b.centerY,
    );
  /*
   * Sort equations top -> bottom.
   */
  mergedRows.sort(
    (a, b) =>
      a.centerY - b.centerY,
  );

  return mergedRows.map(
    (row, index) => {
      const minX =
        Math.min(
          ...row.strokes.map(
            (stroke) =>
              stroke.x1,
          ),
        );

      const minY =
        Math.min(
          ...row.strokes.map(
            (stroke) =>
              stroke.y1,
          ),
        );

      const maxX =
        Math.max(
          ...row.strokes.map(
            (stroke) =>
              stroke.x2,
          ),
        );

      const maxY =
        Math.max(
          ...row.strokes.map(
            (stroke) =>
              stroke.y2,
          ),
        );

      const padding =
        Math.max(
          10,
          baseHeight * 0.2,
        );

      return {
        id: index + 1,

        bbox: [
          minX - padding,
          minY - padding,
          maxX + padding,
          maxY + padding,
        ],

        elementIds:
          row.strokes.map(
            (stroke) =>
              stroke.id,
          ),
      };
    },
  );
}