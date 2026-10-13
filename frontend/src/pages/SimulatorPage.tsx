import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleCheck, Copy, FlaskConical, LoaderCircle, RotateCcw, TriangleAlert } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router'
import { useTranslation } from 'react-i18next'
import {
  approvePlan,
  comparePlans,
  fetchDefaultPlan,
  fetchSavedPlans,
  planFromTemplate,
  savePlan,
} from '@/api/client'
import type { FastTemplate, FastingPlan, PlanOptions } from '@/api/types'
import { LoadError, Loading } from '@/components/QueryState'
import { ApproveDialog } from '@/components/simulator/ApproveDialog'
import { planProblems } from '@/components/simulator/plan'
import { PlanForm } from '@/components/simulator/PlanForm'
import { comparisonSentence, type PlanKey, sharedScale } from '@/components/simulator/plan'
import {
  ComparisonTable,
  DehydrationCaution,
  PlanChart,
  PlanKeyLine,
} from '@/components/simulator/PlanResults'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { formatDate } from '@/lib/format'
import { usePlanOptions, useTemplates } from '@/lib/hooks'

type Plans = Record<PlanKey, FastingPlan>

const PLAN_IDS: Record<PlanKey, string> = { plan_a: 'plan-a', plan_b: 'plan-b' }
const KEYS: PlanKey[] = ['plan_a', 'plan_b']

/** The plan without its status and approval, to check whether the doctor changed it. */
function content(plan: FastingPlan): string {
  const {
    status: _status,
    approved_by: _by,
    approved_on: _on,
    approved_contact: _contact,
    ...rest
  } = plan
  return JSON.stringify(rest)
}

function asDraft(plan: FastingPlan): FastingPlan {
  return { ...plan, status: 'draft', approved_by: null, approved_on: null, approved_contact: null }
}

function Workspace({
  patientId,
  usualPlan,
  initial,
  options,
  templates,
}: {
  patientId: string
  usualPlan: FastingPlan
  initial: Plans
  options: PlanOptions
  templates: FastTemplate[]
}) {
  const { t, i18n } = useTranslation()
  const language = i18n.language
  const queryClient = useQueryClient()
  const [plans, setPlans] = useState<Plans>(initial)
  const [active, setActive] = useState<PlanKey>('plan_a')
  const [tested, setTested] = useState<Plans | null>(null)
  const [approving, setApproving] = useState<PlanKey | null>(null)

  const compare = useMutation({
    mutationFn: (snapshot: Plans) => comparePlans(patientId, snapshot.plan_a, snapshot.plan_b),
  })
  const template = useMutation({
    mutationFn: ({ templateId, date }: { templateId: string; date: string }) =>
      planFromTemplate(patientId, templateId, date),
  })
  const approve = useMutation({
    mutationFn: ({
      key,
      plan,
      doctor,
      contact,
    }: {
      key: PlanKey
      plan: FastingPlan
      doctor: string
      contact: string
    }) => approvePlan(patientId, PLAN_IDS[key], plan, doctor, contact),
  })

  const refreshLists = () => {
    void queryClient.invalidateQueries({ queryKey: ['patients'] })
    void queryClient.invalidateQueries({ queryKey: ['saved-plans', patientId] })
  }

  const run = (save: boolean) => {
    const snapshot = plans
    compare.mutate(snapshot, {
      onSuccess: () => {
        setTested(snapshot)
        if (save) {
          // The doctor's tested plans are saved as drafts, so the patient list shows "Draft".
          void Promise.all(KEYS.map((k) => savePlan(patientId, PLAN_IDS[k], snapshot[k]))).then(
            refreshLists,
          )
        }
      },
    })
  }

  // The usual plan and the saved plans are simulated once when the screen opens. This first
  // run does not save anything.
  const started = useRef(false)
  useEffect(() => {
    if (started.current) return
    started.current = true
    run(false)
    // The first run uses the plans as they are when the screen opens, so it runs only once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const update = (key: PlanKey, plan: FastingPlan) =>
    setPlans((current) => ({ ...current, [key]: asDraft(plan) }))

  const onTemplate = (key: PlanKey, templateId: string, date: string) => {
    template.mutate(
      { templateId, date },
      { onSuccess: (plan) => update(key, { ...plan, plan_name: plans[key].plan_name }) },
    )
  }

  const problems = KEYS.flatMap((k) => planProblems(plans[k], options))
  const stale =
    tested !== null && KEYS.some((k) => content(tested[k]) !== content(plans[k]))
  const result = compare.data
  const scale = result ? sharedScale(result) : null

  const onApprove = async (key: PlanKey, doctor: string, contact: string) => {
    if (!tested) return
    setApproving(key)
    try {
      const answer = await approve.mutateAsync({ key, plan: tested[key], doctor, contact })
      // Only one plan can be approved, so the other plan goes back to a draft.
      setPlans((current) => {
        const other: PlanKey = key === 'plan_a' ? 'plan_b' : 'plan_a'
        return { ...current, [key]: answer.plan, [other]: asDraft(current[other]) }
      })
      refreshLists()
    } finally {
      setApproving(null)
    }
  }

  const approvalStatus = (key: PlanKey) => {
    const plan = plans[key]
    if (plan.status === 'approved' && plan.approved_by) {
      return (
        <p className="inline-flex items-center gap-1.5 text-base font-medium text-emerald-800">
          <CircleCheck aria-hidden className="size-4" />
          {t('approve.approvedText', {
            name: plan.approved_by,
            date: plan.approved_on ? formatDate(plan.approved_on, language) : '',
          })}
        </p>
      )
    }
    return (
      <ApproveDialog
        planName={plans[key].plan_name}
        disabled={!tested || stale || compare.isPending}
        busy={approving === key}
        error={approve.isError && approve.variables?.key === key ? approve.error.message : null}
        onApprove={(doctor, contact) => onApprove(key, doctor, contact)}
      />
    )
  }

  return (
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(24rem,30rem)_1fr]">
      <Card className="gap-4 py-4 xl:sticky xl:top-4 xl:max-h-[calc(100vh-2rem)] xl:overflow-y-auto">
        <CardContent className="grid gap-4 px-4">
          <h2 className="text-xl font-semibold">{t('simulator.formTitle')}</h2>
          <p className="text-base text-muted-foreground">{t('simulator.formIntro')}</p>
          <Button
            className="h-11 text-base"
            disabled={compare.isPending || problems.length > 0}
            onClick={() => run(true)}
          >
            {compare.isPending ? (
              <LoaderCircle aria-hidden className="animate-spin" />
            ) : (
              <FlaskConical aria-hidden />
            )}
            {t('simulator.run')}
          </Button>
          {problems.length > 0 && (
            <p role="alert" className="text-base text-destructive">
              {t('simulator.fixProblems')}
            </p>
          )}
          <Tabs value={active} onValueChange={(v) => setActive(v as PlanKey)}>
            <TabsList className="h-11 w-full">
              {KEYS.map((key) => (
                <TabsTrigger key={key} value={key} className="h-9 text-base">
                  <PlanKeyLine plan={key} />
                  {t(`simulator.tab.${key}`)}
                </TabsTrigger>
              ))}
            </TabsList>
            {KEYS.map((key) => (
              <TabsContent key={key} value={key} className="mt-3 grid gap-3">
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    className="text-base"
                    onClick={() =>
                      update(key, {
                        ...usualPlan,
                        plan_name: key === 'plan_a' ? usualPlan.plan_name : plans[key].plan_name,
                      })
                    }
                  >
                    <RotateCcw aria-hidden />
                    {t('simulator.reset')}
                  </Button>
                  {key === 'plan_b' && (
                    <Button
                      variant="outline"
                      className="text-base"
                      onClick={() =>
                        update('plan_b', { ...plans.plan_a, plan_name: plans.plan_b.plan_name })
                      }
                    >
                      <Copy aria-hidden />
                      {t('simulator.copyA')}
                    </Button>
                  )}
                </div>
                {template.isError && (
                  <p role="alert" className="text-base text-destructive">
                    {template.error.message}
                  </p>
                )}
                <PlanForm
                  plan={plans[key]}
                  onChange={(plan) => update(key, plan)}
                  options={options}
                  templates={templates}
                  templateBusy={template.isPending}
                  onTemplate={(templateId, date) => onTemplate(key, templateId, date)}
                />
              </TabsContent>
            ))}
          </Tabs>
        </CardContent>
      </Card>

      <div className="grid min-w-0 gap-5" aria-live="polite" aria-busy={compare.isPending}>
        <h2 className="text-xl font-semibold">{t('simulator.resultsTitle')}</h2>
        {compare.isPending && <Loading text={t('simulator.running')} />}
        {compare.isError && <LoadError error={compare.error} onRetry={() => run(false)} />}
        {stale && !compare.isPending && (
          <p
            role="status"
            className="flex items-start gap-2 rounded-lg border border-amber-400 bg-amber-50 p-3 text-base text-amber-950"
          >
            <TriangleAlert aria-hidden className="mt-0.5 size-5 shrink-0" />
            {t('simulator.stale')}
          </p>
        )}
        {result && scale && (
          <div className={compare.isPending ? 'grid gap-5 opacity-50' : 'grid gap-5'}>
            <Card className="gap-3 py-4">
              <CardContent className="grid gap-3 px-4">
                <p className="text-lg font-medium">{comparisonSentence(result, t, language)}</p>
                <ComparisonTable comparison={result} />
              </CardContent>
            </Card>
            <DehydrationCaution comparison={result} />
            {KEYS.map((key) => (
              <PlanChart
                key={key}
                planKey={key}
                simulation={result[key]}
                yMax={scale.yMax}
                start={scale.start}
                end={scale.end}
                action={approvalStatus(key)}
              />
            ))}
            <div className="grid gap-2 text-base text-muted-foreground">
              <p>{t('simulator.explainBand')}</p>
              <p>{t('simulator.explainAverage')}</p>
              <p>{t('simulator.explainChance')}</p>
              {result.plan_a.plan.fast_type !== 'ramadan' && <p>{t('idfDar.otherFasts')}</p>}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/** Screen 3: the doctor tests and compares two fasting plans before the fast. */
export function SimulatorPage() {
  const { id = '' } = useParams()
  const { t } = useTranslation()
  const usual = useQuery({ queryKey: ['default-plan', id], queryFn: () => fetchDefaultPlan(id) })
  const saved = useQuery({
    queryKey: ['saved-plans', id],
    queryFn: () => fetchSavedPlans(id),
    staleTime: Infinity,
  })
  const options = usePlanOptions()
  const templates = useTemplates()
  const queries = [usual, saved, options, templates]
  const failed = queries.find((q) => q.isError)
  if (failed) return <LoadError error={failed.error} onRetry={() => void failed.refetch()} />
  if (!usual.data || !saved.data || !options.data || !templates.data) return <Loading />

  const planB = saved.data.plans['plan-b'] ?? {
    ...usual.data,
    plan_name: t('simulator.planBName'),
  }
  return (
    <Workspace
      key={id}
      patientId={id}
      usualPlan={usual.data}
      initial={{ plan_a: saved.data.plans['plan-a'] ?? usual.data, plan_b: planB }}
      options={options.data}
      templates={templates.data}
    />
  )
}
