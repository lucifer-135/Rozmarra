import { useQuery } from '@tanstack/react-query'
import { CircleCheck, ExternalLink, MessageSquareText, Printer } from 'lucide-react'
import { useId, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { useTranslation } from 'react-i18next'
import { documentUrl, fetchPlanMessage, fetchSavedPlans } from '@/api/client'
import { LoadError, Loading } from '@/components/QueryState'
import { Lede } from '@/components/LearnMore'
import { Section } from '@/components/Section'
import { Button } from '@/components/ui/button'
import { formatDate } from '@/lib/format'
import { cn } from '@/lib/utils'

type DocumentLanguage = 'en' | 'hi'

/** Screen 5: the printable patient fasting plan in English or Hindi (FR-E1 to FR-E5). */
export function PlanPage() {
  const { id = '' } = useParams()
  const { t, i18n } = useTranslation()
  const frame = useRef<HTMLIFrameElement>(null)
  const languageLabelId = useId()
  const [height, setHeight] = useState(1100)
  // The plan fades in after it loads, so that switching its language shows no white flash.
  const [loadedSrc, setLoadedSrc] = useState<string | null>(null)
  const saved = useQuery({ queryKey: ['saved-plans', id], queryFn: () => fetchSavedPlans(id) })
  const [searchParams] = useSearchParams()
  // A link such as "?lang=hi" opens the plan in that language.
  const [chosen, setChosen] = useState<DocumentLanguage | null>(() => {
    const asked = searchParams.get('lang')
    return asked === 'en' || asked === 'hi' ? asked : null
  })
  const approved = saved.data
    ? Object.entries(saved.data.plans).find(([, plan]) => plan.status === 'approved')
    : undefined
  // The plan opens in English, the language of the doctor's review, whatever the language of
  // the dashboard or of the patient. The doctor can switch it to Hindi before printing.
  const language: DocumentLanguage = chosen ?? 'en'
  const message = useQuery({
    queryKey: ['plan-message', id, approved?.[0], language],
    queryFn: () => fetchPlanMessage(id, approved![0], language),
    enabled: approved !== undefined,
  })

  if (saved.isError) return <LoadError error={saved.error} onRetry={() => void saved.refetch()} />
  if (saved.isPending) return <Loading />

  if (!approved) {
    return (
      <div className="grid max-w-3xl gap-3 rounded-[18px] bg-card p-8 ring-1 ring-black/[0.06]">
        <h2 className="text-2xl font-semibold">{t('planScreen.notApprovedTitle')}</h2>
        <p className="text-base">{t('planScreen.notApproved')}</p>
        <Link
          to={`/patients/${id}/simulator`}
          className="w-fit text-base font-medium text-primary underline-offset-4 hover:underline"
        >
          {t('planScreen.goToSimulator')}
        </Link>
      </div>
    )
  }

  const [planId, plan] = approved
  const src = documentUrl(id, planId, language)
  const labels: Record<DocumentLanguage, string> = {
    en: t('app.languageEnglish'),
    hi: t('app.languageHindi'),
  }

  return (
    <div className="grid gap-5">
      <div className="grid gap-2">
        <h2 className="text-3xl font-semibold">{t('planScreen.title')}</h2>
        <Lede text={t('planScreen.intro')} className="max-w-[70ch]" />
        <p className="inline-flex items-center gap-2 text-base font-medium text-emerald-800">
          <CircleCheck aria-hidden className="size-5" />
          {t('planScreen.approvedPlan', {
            plan: plan.plan_name,
            name: plan.approved_by,
            date: plan.approved_on ? formatDate(plan.approved_on, i18n.language) : '',
          })}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <span id={languageLabelId} className="text-base font-medium">
          {t('planScreen.language')}
        </span>
        <div role="group" aria-labelledby={languageLabelId} className="flex gap-2">
          {(['en', 'hi'] as const).map((lang) => (
            <Button
              key={lang}
              lang={lang}
              variant={language === lang ? 'default' : 'outline'}
              aria-pressed={language === lang}
              className="text-base"
              onClick={() => setChosen(lang)}
            >
              {labels[lang]}
            </Button>
          ))}
        </div>
        <Button className="text-base" onClick={() => frame.current?.contentWindow?.print()}>
          <Printer aria-hidden />
          {t('planScreen.print')}
        </Button>
        <a
          href={src}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-base font-medium text-primary underline-offset-4 hover:underline"
        >
          <ExternalLink aria-hidden className="size-4" />
          {t('planScreen.openNewTab')}
        </a>
      </div>

      <div className="overflow-hidden rounded-xl border bg-white shadow-xs">
        <iframe
          ref={frame}
          key={src}
          src={src}
          title={t('planScreen.frameTitle', { language: labels[language] })}
          className={cn(
            'block w-full transition-opacity duration-150 ease-out-strong',
            loadedSrc !== src && 'opacity-0',
          )}
          style={{ height }}
          onLoad={() => {
            const body = frame.current?.contentDocument?.body
            if (body) setHeight(body.scrollHeight + 32)
            setLoadedSrc(src)
          }}
        />
      </div>

      <Section
        title={t('planScreen.messageTitle')}
        description={t('planScreen.messageDescription')}
      >
        <div className="flex items-start gap-3 rounded-[14px] bg-parchment p-5">
          <MessageSquareText aria-hidden className="mt-1 size-5 shrink-0 text-muted-foreground" />
          {message.isPending ? (
            <Loading />
          ) : message.isError ? (
            <LoadError error={message.error} />
          ) : (
            <p lang={language} className="text-base whitespace-pre-line">
              {message.data}
            </p>
          )}
        </div>
      </Section>
    </div>
  )
}
