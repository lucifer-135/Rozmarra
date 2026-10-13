import { useQuery } from '@tanstack/react-query'
import { Activity, CircleAlert, CircleCheck, LoaderCircle, ShieldAlert } from 'lucide-react'
import { NavLink, Outlet } from 'react-router'
import { useTranslation } from 'react-i18next'
import { fetchHealth } from '@/api/client'
import { SyntheticBadge } from '@/components/badges'
import { Button } from '@/components/ui/button'
import { LANGUAGES, type Language } from '@/i18n'
import { cn } from '@/lib/utils'

function LanguageSwitch() {
  const { t, i18n } = useTranslation()
  const labels: Record<Language, string> = {
    en: t('app.languageEnglish'),
    hi: t('app.languageHindi'),
  }
  return (
    <div role="group" aria-label={t('app.language')} className="flex gap-2">
      {LANGUAGES.map((language) => (
        <Button
          key={language}
          variant={i18n.language === language ? 'default' : 'outline'}
          aria-pressed={i18n.language === language}
          lang={language}
          className="text-base"
          onClick={() => void i18n.changeLanguage(language)}
        >
          {labels[language]}
        </Button>
      ))}
    </div>
  )
}

/** A one-line status of the connection to the Rozmarra service, with an icon and words. */
function ServiceStatus() {
  const { t } = useTranslation()
  const health = useQuery({ queryKey: ['health'], queryFn: fetchHealth, retry: false })
  let icon = <LoaderCircle aria-hidden className="size-4 animate-spin" />
  let message = t('service.checking')
  if (health.isSuccess) {
    icon = <CircleCheck aria-hidden className="size-4 text-emerald-700" />
    message = t('service.online', { version: health.data.version })
  } else if (health.isError) {
    icon = <CircleAlert aria-hidden className="size-4 text-destructive" />
    message = t('service.offline')
  }
  return (
    <p role="status" className="flex items-center gap-2 text-base text-muted-foreground">
      {icon}
      {message}
    </p>
  )
}

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'rounded-md px-3 py-2 text-base font-medium outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50',
    isActive ? 'bg-muted text-foreground' : 'text-muted-foreground',
  )

export function Layout() {
  const { t } = useTranslation()
  return (
    <div className="flex min-h-screen flex-col bg-muted/40">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:ring-3 focus:ring-ring/50"
      >
        {t('app.skipToContent')}
      </a>
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4">
          <div className="flex items-start gap-3">
            <Activity aria-hidden className="mt-1 size-8 text-primary" />
            <div>
              <p className="text-2xl font-semibold">{t('app.name')}</p>
              <p className="text-base text-muted-foreground">{t('app.subtitle')}</p>
            </div>
          </div>
          <LanguageSwitch />
        </div>
        <nav aria-label={t('nav.main')} className="mx-auto flex max-w-7xl gap-2 px-4 pb-3">
          <NavLink to="/patients" className={navLinkClass}>
            {t('nav.patients')}
          </NavLink>
          <NavLink to="/about" className={navLinkClass}>
            {t('nav.about')}
          </NavLink>
        </nav>
      </header>

      <div className="border-b bg-violet-50/60">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-2">
          <SyntheticBadge />
          <p className="text-base text-violet-950">{t('notice.syntheticDetail')}</p>
        </div>
      </div>

      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 outline-none">
        <Outlet />
      </main>

      <footer className="border-t bg-background">
        <div className="mx-auto grid max-w-7xl gap-3 px-4 py-5">
          <div role="note" className="flex items-start gap-3 text-base">
            <ShieldAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-primary" />
            <div>
              <p className="font-medium">{t('notice.clinical')}</p>
              <p className="text-muted-foreground">{t('notice.prototype')}</p>
            </div>
          </div>
          <ServiceStatus />
        </div>
      </footer>
    </div>
  )
}
