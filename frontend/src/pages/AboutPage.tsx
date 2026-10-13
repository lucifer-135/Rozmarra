import { useQuery } from '@tanstack/react-query'
import { CircleCheck, CircleDashed, CircleMinus, CircleX, ShieldAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchModelCard } from '@/api/client'
import type { Metric, ModelCard } from '@/api/types'
import { ComparisonChart, type ComparisonRow } from '@/charts/ComparisonChart'
import { QueryState } from '@/components/QueryState'
import { Section } from '@/components/Section'
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatFixed, formatNumber } from '@/lib/format'
import { cn } from '@/lib/utils'

type Status = 'met' | 'notMet' | 'notTested' | 'noTarget'

function StatusWord({ status }: { status: Status }) {
  const { t } = useTranslation()
  const icon: Record<Status, ReactNode> = {
    met: <CircleCheck aria-hidden className="size-4 text-emerald-700" />,
    notMet: <CircleX aria-hidden className="size-4 text-red-700" />,
    notTested: <CircleDashed aria-hidden className="size-4 text-slate-600" />,
    noTarget: <CircleMinus aria-hidden className="size-4 text-slate-600" />,
  }
  return (
    <span className="inline-flex items-center gap-1.5 font-medium whitespace-nowrap">
      {icon[status]}
      {t(`about.status.${status}`)}
    </span>
  )
}

function Card({ card }: { card: ModelCard }) {
  const { t, i18n } = useTranslation()
  const language = i18n.language
  const n = (v: number | undefined, digits = 3) =>
    v == null ? '-' : formatFixed(v, language, digits)
  const withInterval = (m: Metric, key: 'auroc' | 'auprc') => {
    const interval = m.confidence_intervals_95?.[key]
    return interval
      ? t('about.valueWithInterval', {
          value: n(m[key]),
          low: n(interval[0]),
          high: n(interval[1]),
        })
      : n(m[key])
  }
  const percent = (v: number, digits = 2) => `${formatFixed(v * 100, language, digits)}%`
  const synthetic = card.metrics.synthetic
  const real = card.metrics.real.e1
  const realMeals = card.metrics.real.e2
  const mealGlucose = realMeals?.baselines['glucose 2 hours before the meal']?.auroc
  const alerts = synthetic.e1.thresholds.sensitivity_80
  const parkes = card.twin_fit?.parkes
  const parkes30 = parkes?.all['30_min']
  const parkes120 = parkes?.all['120_min']
  const forecast = card.twin_fit?.median_forecast_rmse_mg_dl
  const horizons = ['30', '60', '120'].filter((h) => forecast?.[h])
  const twinBeatsLastValue = horizons.every((h) => forecast![h].twin < forecast![h].last_value)
  const singleStreams = (ablation: Record<string, Metric>) =>
    Math.max(
      ...['health record alone', 'wearables alone', 'CGM alone'].map((k) => ablation[k]?.auprc ?? 0),
    )
  const fusionSynthetic = (synthetic.e1.auprc ?? 0) > singleStreams(synthetic.e1.ablation)
  const fusionReal = (real.all.auprc ?? 0) > singleStreams(real.ablation)

  const rows: { measure: string; result: string; target: string; status: Status }[] = [
    {
      measure: t('about.results.e1Real'),
      result: withInterval(real.all, 'auroc'),
      target: t('about.targets.auroc80'),
      status: (real.all.auroc ?? 0) >= 0.8 ? 'met' : 'notMet',
    },
    {
      measure: t('about.results.e1Synthetic'),
      result: withInterval(synthetic.e1, 'auroc'),
      target: t('about.targets.auroc85'),
      status: (synthetic.e1.auroc ?? 0) >= 0.85 ? 'met' : 'notMet',
    },
    {
      measure: t('about.results.detected'),
      result: `${n(alerts.event_sensitivity * 100, 0)}%`,
      target: t('about.targets.detected'),
      status: alerts.event_sensitivity >= 0.8 ? 'met' : 'notMet',
    },
    {
      measure: t('about.results.falseAlerts'),
      result: n(alerts.false_alerts_per_patient_day, 1),
      target: t('about.targets.falseAlerts'),
      status: alerts.false_alerts_per_patient_day <= 2 ? 'met' : 'notMet',
    },
    {
      measure: t('about.results.warning'),
      result: t('about.minutes', { count: alerts.median_warning_minutes }),
      target: t('about.targets.warning'),
      status: alerts.median_warning_minutes >= 30 ? 'met' : 'notMet',
    },
    {
      measure: t('about.results.e2'),
      result: withInterval(synthetic.e2, 'auroc'),
      target: t('about.targets.auroc80'),
      status: (synthetic.e2.auroc ?? 0) >= 0.8 ? 'met' : 'notMet',
    },
    ...(realMeals
      ? [
          {
            measure: t('about.results.e2Real'),
            result: t('about.e2RealValue', {
              value: withInterval(realMeals, 'auroc'),
              glucose: n(mealGlucose),
            }),
            target: t('about.targets.none'),
            status: 'noTarget' as Status,
          },
        ]
      : []),
    {
      measure: t('about.results.forecast'),
      result: horizons
        .map((h) =>
          t('about.forecastValue', {
            minutes: h,
            twin: n(forecast![h].twin, 1),
            last: n(forecast![h].last_value, 1),
          }),
        )
        .join('; '),
      target: t('about.targets.forecast'),
      status: horizons.length && twinBeatsLastValue ? 'met' : 'notMet',
    },
    {
      measure: t('about.results.fusionSynthetic'),
      result: t('about.fusionValue', {
        full: n(synthetic.e1.auprc),
        single: n(singleStreams(synthetic.e1.ablation)),
      }),
      target: t('about.targets.fusion'),
      status: fusionSynthetic ? 'met' : 'notMet',
    },
    {
      measure: t('about.results.fusionReal'),
      result: t('about.fusionValue', {
        full: n(real.all.auprc),
        single: n(singleStreams(real.ablation)),
      }),
      target: t('about.targets.fusion'),
      status: fusionReal ? 'met' : 'notMet',
    },
    {
      measure: t('about.results.parkes'),
      result: parkes30
        ? t('about.parkesValue', {
            twin: percent(parkes30.twin.share_a_and_b),
            pairs: formatNumber(parkes30.twin.pairs, language),
            last: percent(parkes30.last_value.share_a_and_b),
          })
        : t('about.notTestedYet'),
      target: t('about.targets.parkes'),
      status: !parkes30
        ? 'notTested'
        : parkes30.twin.share_a_and_b >= parkes!.target_share_a_and_b_30_min
          ? 'met'
          : 'notMet',
    },
    {
      measure: t('about.results.f1'),
      result: t('about.f1Value', {
        value: withInterval(synthetic.f1.f1_low, 'auroc'),
        twin: n(synthetic.f1.f1_low.twin_alone.auroc),
        score: n(synthetic.f1.f1_low.idf_dar_alone.auroc),
      }),
      target: t('about.targets.none'),
      status: 'noTarget',
    },
  ]

  const methodName = (name: string) => t(`about.methods.${name}`, { defaultValue: name })
  const comparison = (full: Metric, baselines: Record<string, Metric>): ComparisonRow[] => [
    { label: t('about.methods.full model'), value: full.auprc ?? 0, highlight: true },
    ...Object.entries(baselines)
      .filter(([, m]) => m.auprc != null)
      .map(([name, m]) => ({ label: methodName(name), value: m.auprc ?? 0 }))
      .sort((a, b) => b.value - a.value),
  ]
  const syntheticRows = comparison(synthetic.e1, synthetic.e1.baselines)
  const realRows = comparison(real.all, real.baselines)
  const comparisonSummary = (rows: ComparisonRow[]) =>
    rows.map((r) => `${r.label}: ${n(r.value)}`).join('. ')

  return (
    <div className="grid gap-6">
      <Section title={t('about.layers.title')}>
        <ol className="grid list-decimal gap-2 pl-6">
          <li>{t('about.layers.score')}</li>
          <li>{t('about.layers.twin')}</li>
          <li>{t('about.layers.model')}</li>
        </ol>
        <p>{t('about.layers.doctor')}</p>
      </Section>

      <Section title={t('about.data.title')} description={t('about.data.description')}>
        <Table className="text-base">
          <TableHeader>
            <TableRow>
              <TableHead className="text-base">{t('about.data.name')}</TableHead>
              <TableHead className="text-base">{t('about.data.type')}</TableHead>
              <TableHead className="text-base">{t('about.data.licence')}</TableHead>
              <TableHead className="text-base">{t('about.data.use')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {card.data_sources.map((source) => (
              <TableRow key={source.name}>
                <TableCell className="font-medium whitespace-normal">{source.name}</TableCell>
                <TableCell className="whitespace-normal">
                  {t(`about.data.types.${source.type}`, { defaultValue: source.type })}
                </TableCell>
                <TableCell className="whitespace-normal">{source.licence}</TableCell>
                <TableCell className="whitespace-normal">
                  {t(`about.data.uses.${source.id}`, { defaultValue: source.use })}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Section>

      <Section title={t('about.testing.title')}>
        <ul className="grid list-disc gap-2 pl-6">
          <li>
            {t('about.testing.real', {
              patients: real.all.patients,
            })}
          </li>
          {realMeals && (
            <li>
              {t('about.testing.realMeals', {
                meals: realMeals.meals,
                patients: realMeals.patients,
              })}
            </li>
          )}
          <li>
            {t('about.testing.synthetic', {
              patients: card.synthetic_cohort?.virtual_patients ?? 0,
              episodes: formatNumber(card.synthetic_cohort?.fasting_episodes ?? 0, language),
              test: synthetic.e1.patients,
            })}
          </li>
          <li>{t('about.testing.baselines')}</li>
          <li>{t('about.testing.intervals')}</li>
        </ul>
      </Section>

      <Section title={t('about.results.title')} description={t('about.results.description')}>
        <Table className="text-base">
          <TableCaption className="text-left text-base">{t('about.results.caption')}</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead className="text-base">{t('about.results.measure')}</TableHead>
              <TableHead className="text-base">{t('about.results.result')}</TableHead>
              <TableHead className="text-base">{t('about.results.target')}</TableHead>
              <TableHead className="text-base">{t('about.results.status')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.measure} className={cn(row.status === 'notMet' && 'bg-red-50/50')}>
                <TableCell className="whitespace-normal">{row.measure}</TableCell>
                <TableCell className="whitespace-normal tabular-nums">{row.result}</TableCell>
                <TableCell className="whitespace-normal">{row.target}</TableCell>
                <TableCell>
                  <StatusWord status={row.status} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Section>

      <Section title={t('about.compare.title')} description={t('about.compare.description')}>
        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <h3 className="mb-2 text-lg font-semibold">{t('about.compare.synthetic')}</h3>
            <ComparisonChart
              rows={syntheticRows}
              summary={comparisonSummary(syntheticRows)}
            />
          </div>
          <div>
            <h3 className="mb-2 text-lg font-semibold">{t('about.compare.real')}</h3>
            <ComparisonChart rows={realRows} summary={comparisonSummary(realRows)} />
          </div>
        </div>
      </Section>

      <Section title={t('about.meaning.title')}>
        <ul className="grid list-disc gap-2 pl-6">
          <li>
            {t('about.meaning.twinAlone', {
              twin: n(synthetic.e1.baselines['twin alone']?.auprc),
              full: n(synthetic.e1.auprc),
            })}
          </li>
          <li>
            {t('about.meaning.cgmOnly', {
              cgm: n(real.baselines['model with CGM data only']?.auprc),
              full: n(real.all.auprc),
            })}
          </li>
          <li>
            {t(
              alerts.false_alerts_per_patient_day <= 2
                ? 'about.meaning.falseAlertsWithin'
                : 'about.meaning.falseAlerts',
              { value: n(alerts.false_alerts_per_patient_day, 1) },
            )}
          </li>
          {alerts.median_warning_minutes < 30 && (
            <li>
              {t('about.meaning.warning', {
                minutes: formatFixed(alerts.median_warning_minutes, language, 0),
              })}
            </li>
          )}
          {parkes120 && (
            <li>
              {t('about.meaning.parkes', {
                twin: percent(parkes120.twin.shares.A, 1),
                last: percent(parkes120.last_value.shares.A, 1),
              })}
            </li>
          )}
          {realMeals && (
            <li>
              {t('about.meaning.realMeals', {
                model: n(realMeals.auroc),
                glucose: n(mealGlucose),
              })}
            </li>
          )}
          <li>{t('about.meaning.synthetic')}</li>
        </ul>
      </Section>

      <Section title={t('about.limits.title')}>
        <ul className="grid list-disc gap-2 pl-6">
          {card.limitations.map((limit) => (
            <li key={limit.id}>{t(`about.limits.items.${limit.id}`, { defaultValue: limit.text })}</li>
          ))}
        </ul>
        <p className="flex items-start gap-2 font-medium">
          <ShieldAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-primary" />
          {t('notice.clinical')}
        </p>
      </Section>
    </div>
  )
}

/** Screen 6: how Rozmarra makes predictions, which is the model card in plain language. */
export function AboutPage() {
  const { t } = useTranslation()
  const card = useQuery({ queryKey: ['model-card'], queryFn: fetchModelCard, staleTime: Infinity })
  return (
    <div className="grid gap-5">
      <div className="grid gap-2">
        <h1 className="text-2xl font-semibold">{t('screens.about')}</h1>
        <p className="max-w-4xl text-base text-muted-foreground">{t('about.intro')}</p>
      </div>
      <QueryState query={card}>{(data) => <Card card={data} />}</QueryState>
    </div>
  )
}
