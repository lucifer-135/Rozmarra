// Formats for text that people read (docs/prd.md, Section 17.4): full dates such as
// "28 October 2026", the 12-hour clock such as "4:40 pm", and a unit with every number.
//
// The API sends local times without a time zone, for example "2026-10-28T19:31". The
// browser reads such a string as a local time, so the times stay as the API sent them.

import type { Language } from '@/i18n'

const LOCALES: Record<Language, string> = { en: 'en-IN', hi: 'hi-IN' }

export function locale(language: string): string {
  return LOCALES[language as Language] ?? LOCALES.en
}

/** Reads "2026-10-28" or "2026-10-28T19:31" as a local date and time. */
export function toDate(value: string | number | Date): Date {
  if (value instanceof Date) return value
  if (typeof value === 'number') return new Date(value)
  const [day, time = '00:00'] = value.split('T')
  const [y, m, d] = day.split('-').map(Number)
  const [hh, mm, ss = '0'] = time.split(':')
  return new Date(y, m - 1, d, Number(hh), Number(mm), Number(ss))
}

export function formatDate(value: string | number | Date, language: string): string {
  return new Intl.DateTimeFormat(locale(language), {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(toDate(value))
}

export function formatShortDate(value: string | number | Date, language: string): string {
  return new Intl.DateTimeFormat(locale(language), { day: 'numeric', month: 'short' }).format(
    toDate(value),
  )
}

export function formatTime(value: string | number | Date, language: string): string {
  return new Intl.DateTimeFormat(locale(language), {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
    .format(toDate(value))
    .replace('AM', 'am')
    .replace('PM', 'pm')
}

/** A short time for chart axes, for example "4 pm", or "4:30 pm" when the minutes matter. */
export function formatAxisTime(value: number, language: string): string {
  const date = toDate(value)
  if (date.getMinutes() !== 0) return formatTime(date, language)
  return new Intl.DateTimeFormat(locale(language), { hour: 'numeric', hour12: true })
    .format(date)
    .replace('AM', 'am')
    .replace('PM', 'pm')
}

/** A number with a fixed count of decimal places, for example "0.990" for a result. */
export function formatFixed(value: number, language: string, digits: number): string {
  return new Intl.NumberFormat(locale(language), {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value)
}

export function formatNumber(value: number, language: string, digits = 0): string {
  return new Intl.NumberFormat(locale(language), {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  }).format(value)
}

// --- Dates and times inside a plan ---------------------------------------------------------

/** Splits "2026-10-28T08:00:00" into the date and the time of day. */
export function splitDateTime(value: string): { date: string; time: string } {
  const [date, time = '00:00'] = value.split('T')
  return { date, time: time.slice(0, 5) }
}

export function joinDateTime(date: string, time: string): string {
  return `${date}T${time.slice(0, 5)}:00`
}

const pad = (n: number) => String(n).padStart(2, '0')
const dateText = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

export function addDays(date: string, days: number): string {
  const d = toDate(date)
  d.setDate(d.getDate() + days)
  return dateText(d)
}

/** Adds minutes to a date and time such as "2026-10-28T20:14:00". */
export function addMinutes(dateTime: string, minutes: number): string {
  const d = new Date(toDate(dateTime).getTime() + minutes * 60_000)
  return `${dateText(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}:00`
}

/** The number of whole days from one date to another. */
export function daysBetween(from: string, to: string): number {
  return Math.round((toDate(to).getTime() - toDate(from).getTime()) / 86_400_000)
}
