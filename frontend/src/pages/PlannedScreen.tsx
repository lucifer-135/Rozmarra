import { CalendarClock } from 'lucide-react'
import { useTranslation } from 'react-i18next'

/** A screen that the team will add on 18 October 2026. */
export function PlannedScreen({ screen }: { screen: 'monitor' | 'plan' | 'about' }) {
  const { t } = useTranslation()
  return (
    <div className="grid max-w-3xl gap-3 rounded-xl border bg-card p-6">
      <h2 className="flex items-center gap-2 text-xl font-semibold">
        <CalendarClock aria-hidden className="size-5 text-primary" />
        {t(`screens.${screen}`)}
      </h2>
      <p className="text-base">{t('planned.body')}</p>
      <p className="text-base text-muted-foreground">{t(`planned.${screen}`)}</p>
    </div>
  )
}
