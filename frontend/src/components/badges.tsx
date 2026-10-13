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
import { cn } from '@/lib/utils'

// Every badge has an icon and a word as well as a colour, so that no badge relies on
// colour alone.

const BASE =
  'inline-flex w-fit shrink-0 items-center gap-1.5 rounded-full border px-3 py-0.5 text-base font-medium whitespace-nowrap [&>svg]:size-4 [&>svg]:shrink-0'

const LEVEL_STYLE: Record<'low' | 'moderate' | 'high', string> = {
  low: 'border-slate-300 bg-slate-50 text-slate-800',
  moderate: 'border-amber-400 bg-amber-50 text-amber-950',
  high: 'border-red-300 bg-red-50 text-red-800',
}

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
  const { t } = useTranslation()
  const level = LEVEL_OF_WORD[chance.word]
  return (
    <span className={cn(BASE, LEVEL_STYLE[level], className)}>
      <LevelIcon level={level} />
      {t('risk.chance', { percent: chance.percent, word: t(`risk.${level}`) })}
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
  return (
    <span className={cn(BASE, LEVEL_STYLE[category])}>
      <LevelIcon level={category} />
      {t(named ? 'idfDar.categoryWithPoints' : 'idfDar.categoryPoints', {
        category: t(`idfDar.category.${category}`),
        count: total,
      })}
    </span>
  )
}

export function PlanStatusBadge({ status }: { status: PlanStatus }) {
  const { t } = useTranslation()
  const styles: Record<PlanStatus, string> = {
    not_started: 'border-dashed border-slate-400 bg-white text-slate-800',
    draft: 'border-sky-300 bg-sky-50 text-sky-900',
    approved: 'border-emerald-400 bg-emerald-50 text-emerald-900',
  }
  const icons: Record<PlanStatus, ReactNode> = {
    not_started: <CircleDashed aria-hidden />,
    draft: <PencilLine aria-hidden />,
    approved: <CircleCheck aria-hidden />,
  }
  return (
    <span className={cn(BASE, styles[status])}>
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
