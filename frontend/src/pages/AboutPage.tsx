import { useQuery } from '@tanstack/react-query'
import { ShieldAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { fetchModelCard } from '@/api/client'
import type { Metric, ModelCard } from '@/api/types'
import { ComparisonChart, type ComparisonRow } from '@/charts/ComparisonChart'
import { QueryState } from '@/components/QueryState'
import { Section } from '@/components/Section'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatFixed, formatNumber } from '@/lib/format'

function Card({ card }: { card: ModelCard }) {
  const { t, i18n } = useTranslation()
  const language = i18n.language
  const n = (v: number | undefined, digits = 3) =>
    v == null ? '-' : formatFixed(v, language, digits)
  const synthetic = card.metrics.synthetic
  const real = card.metrics.real.e1
  const realMeals = card.metrics.real.e2

  const methodName = (name: string) => t(`about.methods.${name}`, { defaultValue: name })
  const methodInSentence = (name: string) =>
    t(`about.methodsInSentence.${name}`, { defaultValue: name })
  // The methods that scored a higher AUPRC than the full model, named in a sentence.
  const beatenBy = (full: Metric, baselines: Record<string, Metric>) => {
    const names = Object.entries(baselines)
      .filter(([, m]) => (m.auprc ?? 0) > (full.auprc ?? 0))
      .map(([name]) => methodInSentence(name))
    return names.length
      ? new Intl.ListFormat(language === 'hi' ? 'hi-IN' : 'en-IN', { type: 'conjunction' }).format(
          names,
        )
      : null
  }
  // A random guess reaches an AUPRC equal to the share of moments before low blood sugar.
  const randomGuess = (full: Metric) =>
    full.time_points && full.positive_time_points != null
      ? full.positive_time_points / full.time_points
      : null
  const comparison = (full: Metric, baselines: Record<string, Metric>): ComparisonRow[] => [
    { label: t('about.methods.full model'), value: full.auprc ?? 0, highlight: true },
    ...Object.entries(baselines)
      .filter(([, m]) => m.auprc != null)
      .map(([name, m]) => ({ label: methodName(name), value: m.auprc ?? 0 }))
      .sort((a, b) => b.value - a.value),
  ]
  const syntheticRows = comparison(synthetic.e1, synthetic.e1.baselines)
  const realRows = comparison(real.all, real.baselines)
  const comparisonSummary = (rows: ComparisonRow[], guess: number | null) =>
    [
      rows.map((r) => `${r.label}: ${n(r.value)}.`).join(' '),
      guess == null ? '' : t('about.compare.randomSummary', { value: n(guess) }),
    ]
      .filter(Boolean)
      .join(' ')
  const panels = [
    {
      key: 'synthetic',
      rows: syntheticRows,
      guess: randomGuess(synthetic.e1),
      beaten: beatenBy(synthetic.e1, synthetic.e1.baselines),
    },
    {
      key: 'real',
      rows: realRows,
      guess: randomGuess(real.all),
      beaten: beatenBy(real.all, real.baselines),
    },
  ] as const

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

      <Section title={t('about.compare.title')} description={t('about.compare.description')}>
        <div className="grid gap-6 lg:grid-cols-2">
          {panels.map((panel) => (
            <div key={panel.key} className="grid content-start gap-2">
              <h3 className="text-lg font-semibold">{t(`about.compare.${panel.key}`)}</h3>
              <ComparisonChart
                rows={panel.rows}
                baseline={
                  panel.guess == null
                    ? undefined
                    : {
                        value: panel.guess,
                        label: t('about.compare.randomGuess', { value: n(panel.guess) }),
                      }
                }
                summary={comparisonSummary(panel.rows, panel.guess)}
              />
              {panel.beaten && (
                <p className="text-base">
                  {t(`about.compare.${panel.key}Note`, { methods: panel.beaten })}
                </p>
              )}
            </div>
          ))}
        </div>
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
        <h1 className="text-[1.75rem] leading-tight font-semibold">{t('screens.about')}</h1>
        <p className="max-w-4xl text-base text-muted-foreground">{t('about.intro')}</p>
      </div>
      <QueryState query={card}>{(data) => <Card card={data} />}</QueryState>
    </div>
  )
}
