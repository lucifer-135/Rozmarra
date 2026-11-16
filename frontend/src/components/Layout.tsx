import { useQuery } from '@tanstack/react-query'
import { Activity, CircleAlert, CircleCheck, LoaderCircle, ShieldAlert } from 'lucide-react'
import { Link, NavLink, Outlet, useMatch } from 'react-router'
import { useTranslation } from 'react-i18next'
import { fetchHealth } from '@/api/client'
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
    <div role="group" aria-label={t('app.language')} className="flex gap-1 rounded-full bg-black/[0.04] p-1">
      {LANGUAGES.map((language) => (
        <Button
          key={language}
          variant={i18n.language === language ? 'default' : 'ghost'}
          aria-pressed={i18n.language === language}
          lang={language}
          className="h-9 px-4 text-base"
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
    'shrink-0 rounded-full px-3 py-1.5 text-base whitespace-nowrap outline-none transition-colors hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50',
    isActive ? 'font-semibold text-foreground' : 'text-muted-foreground',
  )

export function Layout() {
  const { t } = useTranslation()
  // The home page is a stack of full-width bands, so it brings its own width and spacing.
  const isHome = useMatch('/') !== null
  return (
    <div className="flex min-h-screen flex-col bg-parchment">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:ring-3 focus:ring-ring/50"
      >
        {t('app.skipToContent')}
      </a>
      {/* A slim bar that stays at the top and lets the page show through, like frosted glass. */}
      <header className="sticky top-0 z-40 border-b border-black/[0.06] bg-parchment/80 backdrop-blur-xl backdrop-saturate-150">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2">
          <Link
            to="/"
            title={t('app.subtitle')}
            className="flex items-center gap-2 rounded-full outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            <Activity aria-hidden className="size-6 text-primary" />
            <span className="text-xl font-semibold tracking-[-0.015em]">{t('app.name')}</span>
          </Link>
          <nav
            aria-label={t('nav.main')}
            className="order-last flex w-full gap-1 overflow-x-auto md:order-none md:w-auto md:flex-1"
          >
            <NavLink to="/" end className={navLinkClass}>
              {t('nav.home')}
            </NavLink>
            <NavLink to="/patients" className={navLinkClass}>
              {t('nav.patients')}
            </NavLink>
            <NavLink to="/about" className={navLinkClass}>
              {t('nav.about')}
            </NavLink>
          </nav>
          <div className="ml-auto md:ml-0">
            <LanguageSwitch />
          </div>
        </div>
      </header>

      <main
        id="main"
        tabIndex={-1}
        className={cn(
          'w-full flex-1 outline-none',
          !isHome && 'mx-auto max-w-7xl px-4 py-10 md:py-14',
        )}
      >
        <Outlet />
      </main>

      <footer className="border-t border-black/[0.06] bg-parchment">
        <div className="mx-auto grid max-w-7xl gap-3 px-4 py-8 text-muted-foreground">
          <div role="note" className="flex items-start gap-3 text-base">
            <ShieldAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-primary" />
            <div>
              <p className="font-medium text-foreground">{t('notice.clinical')}</p>
              <p>{t('notice.prototype')}</p>
            </div>
          </div>
          <ServiceStatus />
        </div>
      </footer>
    </div>
  )
}
