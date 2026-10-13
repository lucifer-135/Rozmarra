import type { Comparison, FastingPlan, PlanOptions, Simulation } from '@/api/types'
import { glucoseAxisTop } from '@/charts/scale'
import { COLOURS } from '@/charts/theme'
import { formatNumber, formatTime, toDate } from '@/lib/format'

// Helpers for the fasting plan simulator that are not components.

export type PlanKey = 'plan_a' | 'plan_b'
export const PLAN_COLOURS: Record<PlanKey, string> = {
  plan_a: COLOURS.planA,
  plan_b: COLOURS.planB,
}

/** Problems in a plan that the doctor must fix before Rozmarra can simulate it. */
export function planProblems(plan: FastingPlan, options: PlanOptions | undefined): string[] {
  const problems: string[] = []
  if (plan.fast_end <= plan.fast_start) problems.push('fastEnd')
  plan.medicines.forEach((m, i) => {
    const medicine = options?.medicines.find((o) => o.name === m.name)
    if (!Number.isFinite(m.dose) || (medicine && m.dose > medicine.max_single_dose)) {
      problems.push(`dose:${i}`)
    }
  })
  for (const meal of plan.meals) if (!Number.isFinite(meal.carbs_g)) problems.push('carbs')
  for (const a of plan.activities) if (a.end <= a.start) problems.push('activityEnd')
  return problems
}

/** The sentence that compares the lowest predicted glucose of the two plans. */
export function comparisonSentence(
  comparison: Comparison,
  t: (key: string, options?: Record<string, unknown>) => string,
  language: string,
): string {
  const one = (s: Simulation, key: string) =>
    s.summary.lowest_glucose_time
      ? t(key, {
          value: formatNumber(s.summary.lowest_glucose_mg_dl, language),
          time: formatTime(s.summary.lowest_glucose_time, language),
        })
      : ''
  return [
    one(comparison.plan_a, 'results.sentenceA'),
    one(comparison.plan_b, 'results.sentenceB'),
  ]
    .filter(Boolean)
    .join(' ')
}

/** The common time range and glucose range of the two charts, so that they compare fairly. */
export function sharedScale(comparison: Comparison) {
  const sims = [comparison.plan_a, comparison.plan_b]
  const times = sims.flatMap((s) => [s.curve.times[0], s.curve.times[s.curve.times.length - 1]])
  const sorted = [...times].sort((a, b) => toDate(a).getTime() - toDate(b).getTime())
  const highest = Math.max(
    ...sims.flatMap((s) => [...s.curve.p90, ...(s.curve.average_patient ?? [])].map((v) => v ?? 0)),
  )
  return {
    start: sorted[0],
    end: sorted[sorted.length - 1],
    yMax: glucoseAxisTop(highest),
  }
}
