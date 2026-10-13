export const Y_MIN = 40
export const Y_STEP = 30

/** The top of the glucose axis: at least 250 mg/dL, on the 30 mg/dL grid that starts at 40. */
export function glucoseAxisTop(highest: number): number {
  const top = Math.max(250, highest + 10)
  return Y_MIN + Math.ceil((top - Y_MIN) / Y_STEP) * Y_STEP
}
