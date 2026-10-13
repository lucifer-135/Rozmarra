import { Droplets } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { Comparison, Simulation } from '@/api/types'
import { type ChartEvent, GlucoseChart } from '@/charts/GlucoseChart'
import { COLOURS } from '@/charts/theme'
import { ChanceBadge } from '@/components/badges'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatNumber, formatTime, toDate } from '@/lib/format'
import { PLAN_COLOURS, type PlanKey } from './plan'


/** A short line in the plan colour, used beside the plan name as a key. */
export function PlanKeyLine({ plan }: { plan: PlanKey }) {
  return (
    <span
      aria-hidden
      className="inline-block h-1 w-6 shrink-0 rounded-full"
      style={{ backgroundColor: PLAN_COLOURS[plan] }}
    />
  )
}

/** The table that compares the two plans. It is also the text version of the two charts. */
export function ComparisonTable({ comparison }: { comparison: Comparison }) {
  const { t, i18n } = useTranslation()
  const language = i18n.language
  const plans: PlanKey[] = ['plan_a', 'plan_b']
  const lowest = (s: Simulation) =>
    s.summary.lowest_glucose_time
      ? t('results.lowestAt', {
          value: formatNumber(s.summary.lowest_glucose_mg_dl, language),
          time: formatTime(s.summary.lowest_glucose_time, language),
        })
      : `${formatNumber(s.summary.lowest_glucose_mg_dl, language)} mg/dL`
  const rows: [string, (s: Simulation) => ReactNode][] = [
    [t('results.chanceOfLow'), (s) => <ChanceBadge chance={s.summary.chance_of_low_during_fast} />],
    [t('results.lowest'), lowest],
    [
      t('results.minutesBelow70'),
      (s) => t('results.minutes', { count: s.summary.expected_minutes_below_70 }),
    ],
    [
      t('results.chanceOfHigh'),
      (s) =>
        s.summary.chance_of_high_after_fast ? (
          <ChanceBadge chance={s.summary.chance_of_high_after_fast} />
        ) : (
          t('results.noBreakingMeal')
        ),
    ],
  ]
  return (
    <Table className="text-base">
      <TableCaption className="text-left text-base">{t('results.tableCaption')}</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead className="text-base">
            <span className="sr-only">{t('results.measure')}</span>
          </TableHead>
          {plans.map((key) => (
            <TableHead key={key} className="text-base whitespace-normal">
              <span className="flex items-center gap-2">
                <PlanKeyLine plan={key} />
                {comparison[key].plan.plan_name}
              </span>
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map(([label, cell]) => (
          <TableRow key={label}>
            <TableHead scope="row" className="text-base font-normal whitespace-normal text-muted-foreground">
              {label}
            </TableHead>
            {plans.map((key) => (
              <TableCell key={key} className="whitespace-normal">
                {cell(comparison[key])}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}


export function DehydrationCaution({ comparison }: { comparison: Comparison }) {
  const { t } = useTranslation()
  const which = (['plan_a', 'plan_b'] as PlanKey[]).filter((k) => comparison[k].dehydration_caution)
  if (which.length === 0) return null
  const caution = comparison[which[0]].dehydration_caution!
  return (
    <Alert role="note" className="border-amber-400 bg-amber-50 text-amber-950">
      <Droplets aria-hidden />
      <AlertTitle className="text-base font-semibold">{t('results.cautionTitle')}</AlertTitle>
      <AlertDescription className="grid gap-1 text-base text-amber-950">
        <p>
          {which.length === 2
            ? t('results.cautionBoth')
            : t('results.cautionOne', { plan: comparison[which[0]].plan.plan_name })}
        </p>
        <p>{caution.message}</p>
        <ul className="list-disc pl-5">
          {caution.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  )
}

function chartEvents(simulation: Simulation, language: string, t: (k: string, o?: Record<string, unknown>) => string): ChartEvent[] {
  const m = simulation.markers
  const unit = (u: string) => t(`units.${u}`, { defaultValue: u })
  return [
    ...m.meals.map((meal) => {
      const label = language === 'hi' && meal.label_hi ? meal.label_hi : meal.label
      return {
        kind: 'meal' as const,
        start: meal.time,
        label: t('results.mealEvent', { label, carbs: formatNumber(meal.carbs_g, language) }),
        short: `${formatNumber(meal.carbs_g, language)} g`,
      }
    }),
    ...m.medicines.map((d) => {
      const name = language === 'hi' ? d.display_name_hi : d.display_name
      const dose = `${formatNumber(d.dose, language, 1)} ${unit(d.unit)}`
      return {
        kind: 'medicine' as const,
        start: d.time,
        label: d.changed ? t('results.medicineChanged', { name, dose }) : `${name} ${dose}`,
        short: `${name} ${dose}`,
      }
    }),
    ...m.activities.map((a) => ({
      kind: 'activity' as const,
      start: a.start,
      end: a.end,
      label: t('results.activityEvent', { label: a.label, mets: formatNumber(a.mets, language, 1) }),
    })),
  ]
}

/** The meals, medicines and activities of a plan as text, in time order, below its chart. */
function EventList({ events }: { events: ChartEvent[] }) {
  const { t, i18n } = useTranslation()
  const kinds = (['meal', 'medicine', 'activity'] as const).filter((k) =>
    events.some((e) => e.kind === k),
  )
  const sorted = [...events].sort((a, b) => toDate(a.start).getTime() - toDate(b.start).getTime())
  return (
    <dl className="grid gap-x-4 gap-y-1 text-base sm:grid-cols-[8rem_1fr]">
      {kinds.map((kind) => (
        <div key={kind} className="contents">
          <dt className="font-medium">{t(`chart.strip.${kind}`)}</dt>
          <dd>
            <ul className="grid gap-0.5">
              {sorted
                .filter((e) => e.kind === kind)
                .map((e, i) => (
                  <li key={i}>
                    <span className="tabular-nums text-muted-foreground">
                      {e.end
                        ? t('results.fromTo', {
                            from: formatTime(e.start, i18n.language),
                            to: formatTime(e.end, i18n.language),
                          })
                        : formatTime(e.start, i18n.language)}
                    </span>{' '}
                    {e.label}
                  </li>
                ))}
            </ul>
          </dd>
        </div>
      ))}
    </dl>
  )
}

/** The chart of one plan: the twin's curve with its band and the average-patient curve. */
export function PlanChart({
  planKey,
  simulation,
  yMax,
  start,
  end,
  action,
}: {
  planKey: PlanKey
  simulation: Simulation
  yMax: number
  start: string
  end: string
  action?: ReactNode
}) {
  const { t, i18n } = useTranslation()
  const language = i18n.language
  const curve = simulation.curve
  const s = simulation.summary
  const plan = simulation.plan
  const events = chartEvents(simulation, language, t)
  return (
    <section className="grid gap-2 rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-lg font-semibold">
          <PlanKeyLine plan={planKey} />
          {plan.plan_name}
        </h3>
        {action}
      </div>
      <GlucoseChart
        height={360}
        yMax={yMax}
        start={start}
        end={end}
        lines={[
          {
            id: `${planKey}-twin`,
            name: t('chart.twinCurve'),
            times: curve.times,
            values: curve.p50,
            colour: PLAN_COLOURS[planKey],
            style: 'solid',
            labelLowest: true,
            lowest: s.lowest_glucose_time
              ? { value: s.lowest_glucose_mg_dl, time: s.lowest_glucose_time }
              : undefined,
            band: { name: t('chart.band'), lower: curve.p10, upper: curve.p90 },
          },
          ...(curve.average_patient
            ? [
                {
                  id: `${planKey}-average`,
                  name: t('chart.averagePatient'),
                  times: curve.times,
                  values: curve.average_patient,
                  colour: COLOURS.average,
                  style: 'dotted' as const,
                },
              ]
            : []),
        ]}
        windows={[
          {
            start: simulation.markers.fast.start,
            end: simulation.markers.fast.end,
            label: simulation.markers.fast.water_allowed
              ? t('chart.fastWithWater')
              : t('chart.fastWithoutWater'),
          },
        ]}
        events={events}
        summary={t('results.chartSummary', {
          plan: plan.plan_name,
          value: formatNumber(s.lowest_glucose_mg_dl, language),
          time: s.lowest_glucose_time ? formatTime(s.lowest_glucose_time, language) : '-',
          percent: s.chance_of_low_during_fast.percent,
        })}
      />
      <EventList events={events} />
    </section>
  )
}

