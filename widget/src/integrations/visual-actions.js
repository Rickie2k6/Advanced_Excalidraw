function requireMethod(bridge, name) {
  if (typeof bridge?.[name] !== "function") {
    throw new Error(`Excalidraw ${name} is not available. Reload the canvas.`);
  }
}

function checkResult(result, operation) {
  if (result?.success !== true || !Array.isArray(result.element_ids) ||
      result.element_ids.length === 0) {
    throw new Error(result?.error || `${operation} did not create any canvas elements.`);
  }
  return result;
}

function validateSolution(solution) {
  if (!solution || !Array.isArray(solution.steps) || !solution.steps.length ||
      solution.steps.some(step => typeof step !== "string" || !step.trim())) {
    throw new Error("Invalid solution: expected non-empty mathematical steps.");
  }
  if (solution.source_stroke_ids != null &&
      (!Array.isArray(solution.source_stroke_ids) ||
       solution.source_stroke_ids.some(id => typeof id !== "string" || !id))) {
    throw new Error("Invalid solution stroke anchors.");
  }
}

// "Solve question N": the backend chose an empty spot for the solution and
// may split the steps into columns. Each column starts at its own position.
function validateColumns(action) {
  if (action.columns == null) return;
  if (!Array.isArray(action.columns) || !action.columns.length ||
      action.columns.some(c => !Number.isFinite(c?.x) || !Number.isFinite(c?.y) ||
                               !Array.isArray(c.steps) || !c.steps.length)) {
    throw new Error("Invalid solution placement in backend response.");
  }
  const placed = action.columns.flatMap(c => c.steps);
  if (placed.length !== action.steps.length || placed.some((s, i) => s !== action.steps[i])) {
    throw new Error("Solution placement does not match the solution steps.");
  }
}

async function writeColumns(bridge, action) {
  const solutionGroupId = `solution-${action.source_equation_id ?? "question"}-${globalThis.crypto.randomUUID()}`;
  const scale = Number.isFinite(action.scale) ? action.scale : 1;
  const results = [];
  let stepNumber = 0;
  for (const column of action.columns) {
    let anchorElementIds = [];
    for (const [index, expression] of column.steps.entries()) {
      stepNumber += 1;
      const result = checkResult(await bridge.writeMath({
        expression,
        anchorElementIds,
        solutionGroupId,
        actionId: `${solutionGroupId}-step-${stepNumber}`,
        // The first line of a column goes exactly where the backend found empty
        // space; the next lines go directly below the previous one, in the same
        // column. `exact` skips the canvas collision search, which would treat the
        // worksheet image as an obstacle and push the solution off the page.
        ...(index === 0
          ? { position: { x: column.x, y: column.y } }
          : { x: column.x, exact: true }),
        scale,
      }), `Solution step ${stepNumber}`);
      anchorElementIds = result.element_ids;
      results.push(result);
    }
  }
  // When the equations were read with the LLM's help, say what was read so the
  // student can spot a misreading.
  const readAs = Array.isArray(action.read_as) && action.read_as.length
    ? ` (read as ${action.read_as.join(", ")})`
    : "";
  const answer = action.question_number != null && action.answer
    ? `Solved question ${action.question_number}${readAs}: ${action.answer}.`
    : "Wrote the solution steps on the canvas.";
  const location = { beside: "beside the worksheet", below: "below the worksheet" }[action.placement];
  const message = location ? `${answer} I wrote the steps ${location}.` : answer;
  return { message, results };
}

export async function executeVisualAction(bridge, action) {
  if (!action || typeof action !== "object") {
    throw new Error("Invalid visual_action in backend response.");
  }
  if (action.action === "circle") {
    requireMethod(bridge, "addEllipse");
    const { x, y, width, height } = action;
    if (![x, y, width, height].every(Number.isFinite) || width <= 0 || height <= 0) {
      throw new Error("Invalid circle coordinates in backend response.");
    }
    const result = checkResult(await bridge.addEllipse({ x, y, width, height }), "Circle");
    return { message: "Circled the target on the canvas.", results: [result] };
  }
  requireMethod(bridge, "writeMath");
  if (action.action === "write_math") {
    if (typeof action.expression !== "string" || !action.expression.trim()) {
      throw new Error("Missing mathematical expression in backend response.");
    }
    const result = checkResult(await bridge.writeMath({ expression: action.expression }), "Write math");
    return { message: "Wrote the expression on the canvas.", results: [result] };
  }
  if (action.action === "write_math_steps" && action.columns != null) {
    validateSolution(action);
    validateColumns(action);
    return writeColumns(bridge, action);
  }
  let solutions;
  if (action.action === "write_math_steps") {
    solutions = [action];
  } else if (action.action === "write_multiple_math_steps" &&
             Array.isArray(action.solutions) && action.solutions.length) {
    solutions = action.solutions;
  } else {
    throw new Error(`Unsupported visual action: ${action.action ?? "missing action"}.`);
  }
  // Validate all solutions before making any changes to the canvas.
  solutions.forEach(validateSolution);
  const results = [];
  for (const [index, solution] of solutions.entries()) {
    let anchorElementIds = [...(solution.source_stroke_ids ?? [])];
    const solutionGroupId = `solution-${solution.source_equation_id ?? index}-${globalThis.crypto.randomUUID()}`;
    // Every solver response includes the original equation as its first step.
    const steps = anchorElementIds.length ? solution.steps.slice(1) : solution.steps;
    for (const [stepIndex, expression] of steps.entries()) {
      const result = checkResult(await bridge.writeMath({
        expression, anchorElementIds, solutionGroupId,
        actionId: `${solutionGroupId}-step-${stepIndex + 1}`,
      }), `Solution step ${stepIndex + 1}`);
      anchorElementIds = result.element_ids;
      results.push(result);
    }
  }
  return {
    message: results.length ? "Wrote the solution steps on the canvas." : "The anchored equation is already solved; no extra steps were needed.",
    results,
  };
}
