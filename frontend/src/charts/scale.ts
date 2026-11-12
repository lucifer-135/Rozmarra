export const Y_MIN = 40
export const Y_STEP = 30

/** The top of the glucose axis: at least 250 mg/dL, on the 30 mg/dL grid that starts at 40. */
export function glucoseAxisTop(highest: number): number {
  const top = Math.max(250, highest + 10)
  return Y_MIN + Math.ceil((top - Y_MIN) / Y_STEP) * Y_STEP
}

/**
 * The labels of the glucose axis. The axis labels the limits that doctors read on an ambulatory
 * glucose profile (54, 70, 180 and 250 mg/dL) instead of a regular grid, and the top of the axis
 * when the top lies above 250 mg/dL.
 */
export function glucoseTicks(top: number): number[] {
  return [54, 70, 180, 250, ...(top > 250 ? [top] : [])].filter((value) => value <= top)
}
