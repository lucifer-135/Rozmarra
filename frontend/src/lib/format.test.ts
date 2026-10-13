import type { FastingPlan, PlanOptions } from '@/api/types'
import { planProblems } from '@/components/simulator/plan'
import fixtures from '@/test/fixtures.json'
import {
  addDays,
  addMinutes,
  daysBetween,
  formatDate,
  formatTime,
  joinDateTime,
  splitDateTime,
} from './format'

test('dates are written in full and times use the 12-hour clock', () => {
  expect(formatDate('2026-10-28', 'en')).toBe('28 October 2026')
  expect(formatDate('2026-10-28', 'hi')).toBe('28 अक्टूबर 2026')
  expect(formatTime('2026-10-28T19:31', 'en')).toBe('7:31 pm')
  expect(formatTime('2026-10-28T04:30:00', 'en')).toBe('4:30 am')
})

test('plan times keep their local date and time', () => {
  expect(splitDateTime('2026-10-28T08:00:00')).toEqual({ date: '2026-10-28', time: '08:00' })
  expect(joinDateTime('2026-10-28', '20:30')).toBe('2026-10-28T20:30:00')
  expect(addDays('2026-10-31', 1)).toBe('2026-11-01')
  expect(addMinutes('2026-10-28T23:30:00', 90)).toBe('2026-10-29T01:00:00')
  expect(daysBetween('2026-10-28', '2026-10-27')).toBe(-1)
})

test('the plan form finds the problems that stop a simulation', () => {
  const plan = fixtures.plan as FastingPlan
  const options = fixtures.options as PlanOptions
  expect(planProblems(plan, options)).toEqual([])
  const backwards = { ...plan, fast_end: plan.fast_start }
  expect(planProblems(backwards, options)).toContain('fastEnd')
  const tooHigh = {
    ...plan,
    medicines: plan.medicines.map((m, i) => (i === 0 ? { ...m, dose: 40 } : m)),
  }
  expect(planProblems(tooHigh, options)).toEqual(['dose:0'])
})
