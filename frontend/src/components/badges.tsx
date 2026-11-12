import {
  CircleCheck,
  CircleDashed,
  CircleDot,
  Droplets,
  FlaskConical,
  OctagonAlert,
  PencilLine,
  TriangleAlert,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { Chance, IdfDarCategory, PlanStatus, RiskWord } from '@/api/types'
import { useChanceText } from '@/lib/hooks'
import { cn } from '@/lib/utils'

// Every badge has an icon and a word as well as a colour, so that no badge relies on
// colour alone. A badge with a border is kept for states that need attention. Normal states,
// such as a plan that is not started, are plain text with an icon. Red is kept for alerts, so
// a high chance or a high IDF-DAR score is shown in amber with its own icon.

const BASE =
  'inline-flex w-fit shrink-0 items-center gap-1.5 rounded-full border px-3 py-0.5 text-base font-medium whitespace-nowrap [&>svg]:size-4 [&>svg]:shrink-0'

const LEVEL_STYLE: Record<'low' | 'moderate' | 'high', string> = {
  low: 'border-slate-300 bg-slate-50 text-slate-800',
  moderate: 'border-amber-400 bg-amber-50 text-amber-950',
  high: 'border-amber-600 bg-amber-100 text-amber-950',
}

const PLAIN = 'inline-flex w-fit items-center gap-1.5 text-base [&>svg]:size-4 [&>svg]:shrink-0'

function LevelIcon({ level }: { level: 'low' | 'moderate' | 'high' }) {
  if (level === 'high') return <OctagonAlert aria-hidden />
  if (level === 'moderate') return <TriangleAlert aria-hidden />
  return <CircleDot aria-hidden />
}

const LEVEL_OF_WORD: Record<RiskWord, 'low' | 'moderate' | 'high'> = {
  Low: 'low',
  Moderate: 'moderate',
  High: 'high',
}

export function ChanceBadge({ chance, className }: { chance: Chance; className?: string }) {
  const chanceText = useChanceText()
  const level = LEVEL_OF_WORD[chance.word]
  return (
    <span className={cn(BASE, LEVEL_STYLE[level], className)}>
      <LevelIcon level={level} />
      {chanceText(chance)}
    </span>
  )
}

/** A chance as bold text with an icon, for tables and panels that already have a colour. */
export function ChanceText({ chance }: { chance: Chance }) {
  const chanceText = useChanceText()
  return (
    <span className={cn(PLAIN, 'font-semibold tabular-nums')}>
      <LevelIcon level={LEVEL_OF_WORD[chance.word]} />
      {chanceText(chance)}
    </span>
  )
}

export function IdfDarBadge({
  category,
  total,
  named = true,
}: {
  category: IdfDarCategory
  total: number
  named?: boolean
}) {
  const { t } = useTranslation()
  // The IDF-DAR category is a standard score, not an alert, so the badge is neutral and the
  // icon and the words carry the level.
  return (
    <span className={cn(BASE, 'border-slate-300 bg-white text-slate-800')}>
      <LevelIcon level={category} />
      {t(named ? 'idfDar.categoryWithPoints' : 'idfDar.categoryPoints', {
        category: t(`idfDar.category.${category}`),
        count: total,
      })}
    </span>
  )
}

/** The IDF-DAR category as plain text with an icon, for the list of patients. */
export function IdfDarText({ category, total }: { category: IdfDarCategory; total: number }) {
  const { t } = useTranslation()
  return (
    <span className={PLAIN}>
      <LevelIcon level={category} />
      {t('idfDar.categoryPoints', { category: t(`idfDar.category.${category}`), count: total })}
    </span>
  )
}

export function PlanStatusBadge({ status }: { status: PlanStatus }) {
  const { t } = useTranslation()
  // Only an approved plan has a badge. A plan that is not started or a draft is plain text.
  const styles: Record<PlanStatus, string> = {
    not_started: cn(PLAIN, 'text-muted-foreground'),
    draft: cn(PLAIN, 'text-sky-900'),
    approved: cn(BASE, 'border-emerald-400 bg-emerald-50 text-emerald-900'),
  }
  const icons: Record<PlanStatus, ReactNode> = {
    not_started: <CircleDashed aria-hidden />,
    draft: <PencilLine aria-hidden />,
    approved: <CircleCheck aria-hidden />,
  }
  return (
    <span className={styles[status]}>
      {icons[status]}
      {t(`planStatus.${status}`)}
    </span>
  )
}

export function SyntheticBadge() {
  const { t } = useTranslation()
  return (
    <span className={cn(BASE, 'border-violet-300 bg-violet-50 text-violet-900')}>
      <FlaskConical aria-hidden />
      {t('notice.synthetic')}
    </span>
  )
}

export function DehydrationBadge() {
  const { t } = useTranslation()
  return (
    <span className={cn(BASE, 'border-amber-400 bg-amber-50 text-amber-950')}>
      <Droplets aria-hidden />
      {t('patients.dehydration')}
    </span>
  )
}
