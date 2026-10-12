import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  CircleAlert,
  CircleCheck,
  FlaskConical,
  LoaderCircle,
  ShieldAlert,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { fetchHealth } from '@/api/client'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LANGUAGES, type Language } from '@/i18n'

const SCREENS = ['patients', 'virtualPatient', 'simulator', 'monitor', 'plan', 'about'] as const

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
          onClick={() => void i18n.changeLanguage(language)}
        >
          {labels[language]}
        </Button>
      ))}
    </div>
  )
}

function ServiceStatus() {
  const { t } = useTranslation()
  const health = useQuery({ queryKey: ['health'], queryFn: fetchHealth, retry: false })

  // Each state has an icon and a word as well as a colour, so that the status
  // does not rely on colour alone.
  let badge = (
    <Badge variant="secondary">
      <LoaderCircle aria-hidden className="animate-spin" />
      {t('service.statusChecking')}
    </Badge>
  )
  let message = t('service.checking')
  if (health.isSuccess) {
    badge = (
      <Badge>
        <CircleCheck aria-hidden />
        {t('service.statusOnline')}
      </Badge>
    )
    message = t('service.online', { version: health.data.version })
  } else if (health.isError) {
    badge = (
      <Badge variant="destructive">
        <CircleAlert aria-hidden />
        {t('service.statusOffline')}
      </Badge>
    )
    message = t('service.offline')
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-3 text-lg">
          {t('service.title')}
          {badge}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p role="status" className="text-base">
          {message}
        </p>
      </CardContent>
    </Card>
  )
}

export default function App() {
  const { t } = useTranslation()

  return (
    <div className="min-h-screen bg-muted/40">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-4 py-5">
          <div className="flex items-start gap-3">
            <Activity aria-hidden className="mt-1 size-8 text-primary" />
            <div>
              <h1 className="text-2xl font-semibold">{t('app.name')}</h1>
              <p className="text-base text-muted-foreground">{t('app.subtitle')}</p>
            </div>
          </div>
          <LanguageSwitch />
        </div>
      </header>

      <main className="mx-auto grid max-w-5xl gap-6 px-4 py-8">
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant="outline">
            <FlaskConical aria-hidden />
            {t('notice.synthetic')}
          </Badge>
          <p className="text-base text-muted-foreground">{t('notice.syntheticDetail')}</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t('placeholder.title')}</CardTitle>
            <CardDescription className="text-base">{t('placeholder.body')}</CardDescription>
          </CardHeader>
          <CardContent>
            <h2 className="mb-2 text-base font-semibold">{t('placeholder.screensTitle')}</h2>
            <ol className="list-decimal space-y-1 pl-6 text-base">
              {SCREENS.map((screen) => (
                <li key={screen}>{t(`placeholder.screens.${screen}`)}</li>
              ))}
            </ol>
          </CardContent>
        </Card>

        <ServiceStatus />
      </main>

      <footer className="mx-auto max-w-5xl px-4 pb-10">
        <Alert>
          <ShieldAlert aria-hidden />
          <AlertDescription className="text-base">
            <p>{t('notice.clinical')}</p>
            <p>{t('notice.prototype')}</p>
          </AlertDescription>
        </Alert>
      </footer>
    </div>
  )
}
