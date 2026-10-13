import { useQuery } from '@tanstack/react-query'
import { CircleCheck, ExternalLink, MessageSquareText, Printer } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { useTranslation } from 'react-i18next'
import { documentUrl, fetchPatient, fetchPlanMessage, fetchSavedPlans } from '@/api/client'
import { LoadError, Loading } from '@/components/QueryState'
import { Section } from '@/components/Section'
import { Button } from '@/components/ui/button'
import { formatDate } from '@/lib/format'

type DocumentLanguage = 'en' | 'hi'

/** Screen 5: the printable patient fasting plan in English or Hindi (FR-E1 to FR-E5). */
export function PlanPage() {
  const { id = '' } = useParams()
  const { t, i18n } = useTranslation()
  const frame = useRef<HTMLIFrameElement>(null)
  const [height, setHeight] = useState(1100)
  const patient = useQuery({ queryKey: ['patient', id], queryFn: () => fetchPatient(id) })
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
  // The plan opens in the patient's own language, and the doctor can switch it.
  const language: DocumentLanguage = chosen ?? (patient.data?.language === 'hi' ? 'hi' : 'en')
  const message = useQuery({
    queryKey: ['plan-message', id, approved?.[0], language],
    queryFn: () => fetchPlanMessage(id, approved![0], language),
    enabled: approved !== undefined,
  })

  if (saved.isError) return <LoadError error={saved.error} onRetry={() => void saved.refetch()} />
  if (saved.isPending || patient.isPending) return <Loading />

  if (!approved) {
    return (
      <div className="grid max-w-3xl gap-3 rounded-xl border bg-card p-6">
        <h2 className="text-xl font-semibold">{t('planScreen.notApprovedTitle')}</h2>
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
        <h2 className="text-xl font-semibold">{t('planScreen.title')}</h2>
        <p className="max-w-4xl text-base">{t('planScreen.intro')}</p>
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
        <div role="group" aria-label={t('planScreen.language')} className="flex gap-2">
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
          className="block w-full"
          style={{ height }}
          onLoad={() => {
            const body = frame.current?.contentDocument?.body
            if (body) setHeight(body.scrollHeight + 32)
          }}
        />
      </div>

      <Section
        title={t('planScreen.messageTitle')}
        description={t('planScreen.messageDescription')}
      >
        <div className="flex items-start gap-3 rounded-lg border bg-muted/50 p-4">
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
