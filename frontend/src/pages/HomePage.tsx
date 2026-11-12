import { useQuery } from '@tanstack/react-query'
import { FileText, FlaskConical, HandHeart, Pill } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { fetchPatients } from '@/api/client'
import { COLOURS } from '@/charts/theme'
import { buttonVariants } from '@/components/ui/button'
import { formatAxisTime } from '@/lib/format'
import { usePatientName, useTemplates } from '@/lib/hooks'
import { cn } from '@/lib/utils'

// The home page introduces Rozmarra to a doctor or a judge who opens the dashboard for the
// first time. Its picture is one fasting day with the fasting window in the same indigo as the
// charts and the printed plan, so that the colour of the fast is learnt here first.

// The illustration covers 5:00 am to 11:00 pm and 40 to 250 mg/dL. Its values are invented
// for the picture and do not come from any patient.
const FIRST_HOUR = 5
const HOURS = 18
const GLUCOSE_MIN = 40
const GLUCOSE_MAX = 250
const FAST_START = 6.25
const FAST_END = 20.25
const NOW = 15
const MEASURED: [number, number][] = [
  [5, 140], [6, 152], [7, 168], [8, 151], [9, 129], [10, 118], [11, 111],
  [12, 104], [13, 97], [14, 90], [15, 82],
]
const FORECAST: [number, number][] = [[15, 82], [15.5, 76], [16, 71], [16.5, 67], [17, 66]]

const x = (hour: number) => ((hour - FIRST_HOUR) / HOURS) * 100
const y = (glucose: number) => ((GLUCOSE_MAX - glucose) / (GLUCOSE_MAX - GLUCOSE_MIN)) * 100
const path = (points: [number, number][]) =>
  points.map(([h, g], i) => `${i ? 'L' : 'M'}${x(h) * 10},${y(g) * 10}`).join(' ')

/** The hour as an axis label in the language of the dashboard, for example "6 am". */
function hourLabel(hour: number, language: string) {
  return formatAxisTime(new Date(2026, 9, 28, hour).getTime(), language)
}

/**
 * One fasting day drawn with HTML and a stretched SVG path, so that every label stays at the
 * 16-pixel minimum text size on a phone as well as on a large screen.
 */
function FastingDayFigure() {
  const { t, i18n } = useTranslation()
  const language = i18n.language
  const nowGlucose = MEASURED[MEASURED.length - 1][1]
  return (
    <figure className="m-0 grid gap-3">
      <div aria-hidden="true" className="rounded-xl border bg-card p-4 pb-3 shadow-xs">
        <div className="relative h-8 text-base font-medium text-fast">
          <span className="absolute bottom-1 whitespace-nowrap" style={{ left: `${x(FAST_START)}%` }}>
            {t('home.figure.start')}
          </span>
          <span
            className="absolute bottom-1 whitespace-nowrap"
            style={{ right: `${100 - x(FAST_END)}%` }}
          >
            {t('home.figure.end')}
          </span>
        </div>
        <div className="flex gap-2">
          <div className="relative w-8 shrink-0 text-right text-base text-muted-foreground">
            {[180, 70].map((value) => (
              <span key={value} className="absolute right-0 -translate-y-1/2" style={{ top: `${y(value)}%` }}>
                {value}
              </span>
            ))}
          </div>
          <div className="relative h-56 flex-1 border-b border-l sm:h-64">
            <div
              className="absolute inset-x-0"
              style={{
                top: `${y(180)}%`,
                height: `${y(70) - y(180)}%`,
                backgroundColor: COLOURS.targetRange,
              }}
            />
            <div
              className="absolute inset-y-0 border-x border-fast/40 bg-fast/10"
              style={{ left: `${x(FAST_START)}%`, width: `${x(FAST_END) - x(FAST_START)}%` }}
            />
            <div
              className="absolute inset-x-0 border-t-2 border-dashed"
              style={{ top: `${y(70)}%`, borderColor: COLOURS.low }}
            />
            <svg
              viewBox="0 0 1000 1000"
              preserveAspectRatio="none"
              className="motion-reveal absolute inset-0 size-full overflow-visible"
            >
              <path
                d={path(MEASURED)}
                fill="none"
                stroke={COLOURS.measured}
                strokeWidth={2.5}
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
              />
              <path
                d={path(FORECAST)}
                fill="none"
                stroke={COLOURS.measured}
                strokeWidth={2.5}
                strokeDasharray="6 5"
                vectorEffect="non-scaling-stroke"
              />
            </svg>
            <span
              className="motion-fade-in-late absolute size-0 -translate-x-1/2 -translate-y-full border-x-[9px] border-b-[14px] border-x-transparent"
              style={{
                left: `${x(NOW)}%`,
                top: `calc(${y(nowGlucose)}% - 6px)`,
                borderBottomColor: COLOURS.alert,
              }}
            />
            {/* The label sits above the triangle, where the falling line never passes. */}
            <span
              className="motion-fade-in-late absolute -translate-x-1/2 -translate-y-full text-base font-medium whitespace-nowrap"
              style={{ left: `${x(NOW)}%`, top: `calc(${y(nowGlucose)}% - 22px)`, color: COLOURS.alert }}
            >
              {t('home.figure.alert')}
            </span>
            <span
              className="motion-fade-in-late absolute pt-2 text-base whitespace-nowrap text-muted-foreground"
              style={{ left: `${x(16)}%`, top: `${y(66)}%` }}
            >
              {t('home.figure.forecast')}
            </span>
          </div>
        </div>
        <div className="relative ml-10 h-7 text-base text-muted-foreground">
          {[6, 12, 18].map((hour) => (
            <span
              key={hour}
              className="absolute top-1 -translate-x-1/2 whitespace-nowrap"
              style={{ left: `${x(hour)}%` }}
            >
              {hourLabel(hour, language)}
            </span>
          ))}
        </div>
      </div>
      <figcaption className="text-base text-muted-foreground">{t('home.figure.caption')}</figcaption>
    </figure>
  )
}

const STEPS = [
  { key: 'patients', path: null },
  { key: 'virtual', path: '' },
  { key: 'simulator', path: 'simulator' },
  { key: 'monitor', path: 'monitor' },
  { key: 'plan', path: 'plan' },
] as const

/** The five screens in the order of the doctor's work. The order matters, so it is numbered. */
function Steps() {
  const { t } = useTranslation()
  const patientName = usePatientName()
  const patients = useQuery({ queryKey: ['patients'], queryFn: fetchPatients })
  // The first patient in the list needs attention first, so the links open that patient. The
  // printed plan needs an approved plan, so its link prefers a patient whose plan is approved.
  const first = patients.data?.[0]
  const withPlan = patients.data?.find((row) => row.plan_status === 'approved') ?? first
  const linkClass = 'w-fit font-medium text-primary underline-offset-4 hover:underline'
  return (
    <ol role="list" className="grid gap-8 xl:grid-cols-5 xl:gap-6">
      {STEPS.map((step, index) => {
        // The first step needs no link of its own: the main button above opens the list.
        let link: ReactNode = null
        const patient = step.key === 'plan' ? withPlan : first
        if (step.path !== null && patient) {
          const to = step.path
            ? `/patients/${patient.patient_id}/${step.path}`
            : `/patients/${patient.patient_id}`
          link = (
            <Link to={to} className={linkClass}>
              {t('home.steps.open', { name: patientName(patient) })}
            </Link>
          )
        }
        return (
          <li key={step.key} className="relative grid content-start gap-2 pl-14 xl:pt-14 xl:pl-0">
            <span
              aria-hidden
              className="absolute top-0 left-0 z-10 flex size-10 items-center justify-center rounded-full border-2 border-primary bg-background text-lg font-semibold text-primary"
            >
              {index + 1}
            </span>
            {index < STEPS.length - 1 && (
              <span
                aria-hidden
                className="absolute top-10 -bottom-8 left-5 w-0.5 bg-border xl:top-5 xl:right-[-1.5rem] xl:bottom-auto xl:left-10 xl:h-0.5 xl:w-auto"
              />
            )}
            <h3 className="text-lg font-semibold">{t(`home.steps.items.${step.key}.title`)}</h3>
            <p className="text-base">{t(`home.steps.items.${step.key}.body`)}</p>
            {link}
          </li>
        )
      })}
    </ol>
  )
}

function Fasts() {
  const { t, i18n } = useTranslation()
  const templates = useTemplates()
  const names = [
    ...new Set(
      (templates.data ?? []).map((template) =>
        i18n.language === 'hi' ? template.name_hi.split(':')[0] : template.short_name,
      ),
    ),
  ]
  return (
    <section aria-labelledby="home-fasts" className="grid content-start gap-3">
      <h2 id="home-fasts" className="text-lg font-semibold">
        {t('home.fasts.title')}
      </h2>
      <p className="text-base text-muted-foreground">{t('home.fasts.description')}</p>
      <ul role="list" className="flex flex-wrap gap-2">
        {names.map((name) => (
          <li key={name} className="rounded-full bg-fast-soft px-3 py-1 text-base font-medium text-fast">
            {name}
          </li>
        ))}
      </ul>
    </section>
  )
}

function Safety() {
  const { t } = useTranslation()
  const items = [
    { key: 'medicines', icon: Pill },
    { key: 'judge', icon: HandHeart },
    { key: 'ai', icon: FileText },
    { key: 'prototype', icon: FlaskConical },
  ] as const
  return (
    <section aria-labelledby="home-safety" className="grid content-start gap-3">
      <h2 id="home-safety" className="text-lg font-semibold">
        {t('home.safety.title')}
      </h2>
      <ul role="list" className="grid gap-3">
        {items.map(({ key, icon: Icon }) => (
          <li key={key} className="flex items-start gap-3 text-base">
            <Icon aria-hidden className="mt-0.5 size-5 shrink-0 text-primary" />
            {t(`home.safety.${key}`)}
          </li>
        ))}
      </ul>
    </section>
  )
}

/** The home page of the dashboard. */
export function HomePage() {
  const { t } = useTranslation()
  return (
    <div className="grid gap-14 py-4">
      <section className="grid items-center gap-10 lg:grid-cols-[minmax(0,7fr)_minmax(0,6fr)]">
        <div className="grid content-start gap-5">
          <h1 className="max-w-[22ch] text-4xl leading-[1.15] font-semibold tracking-tight md:text-[2.75rem]">
            {t('home.title')}
          </h1>
          <p className="max-w-[60ch] text-lg text-muted-foreground">{t('home.lead')}</p>
          <div className="flex flex-wrap gap-3">
            <Link to="/patients" className={cn(buttonVariants(), 'h-11 px-5 text-base')}>
              {t('home.openPatients')}
            </Link>
            <Link
              to="/about"
              className={cn(buttonVariants({ variant: 'outline' }), 'h-11 px-5 text-base')}
            >
              {t('home.readAbout')}
            </Link>
          </div>
        </div>
        <FastingDayFigure />
      </section>

      <section aria-labelledby="home-steps" className="grid gap-6">
        <div className="grid gap-1">
          <h2 id="home-steps" className="text-2xl font-semibold">
            {t('home.steps.title')}
          </h2>
          <p className="max-w-[70ch] text-base text-muted-foreground">
            {t('home.steps.description')}
          </p>
        </div>
        <Steps />
      </section>

      <div className="grid gap-10 border-t pt-10 lg:grid-cols-2">
        <Fasts />
        <Safety />
      </div>
    </div>
  )
}
