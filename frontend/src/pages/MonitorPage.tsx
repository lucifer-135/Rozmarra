import { keepPreviousData, useQuery } from '@tanstack/react-query'
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  CircleDot,
  OctagonAlert,
  Pause,
  Play,
  SignalLow,
  SkipForward,
  TriangleAlert,
} from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import { useParams } from 'react-router'
import { useTranslation } from 'react-i18next'
import { fetchReplay, fetchReplayAt, fetchTimeseries } from '@/api/client'
import type { Chance, ReplayMoment, ReplayOverview } from '@/api/types'
import { ChanceChart } from '@/charts/ChanceChart'
import { type GlucoseLine, GlucoseChart } from '@/charts/GlucoseChart'
import { SignalChart } from '@/charts/SignalChart'
import { COLOURS } from '@/charts/theme'
import { ChanceBadge } from '@/components/badges'
import { LoadError, Loading, QueryState } from '@/components/QueryState'
import { Section } from '@/components/Section'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { addMinutes, formatDate, formatNumber, formatTime, toDate } from '@/lib/format'
import { useDebouncedValue } from '@/lib/hooks'
import { cn } from '@/lib/utils'

const STEP_MINUTES = 5
const HOURS_BEFORE = 6
const HOURS_AFTER = 2

function useMomentText() {
  const { t, i18n } = useTranslation()
  return (time: string) =>
    t('monitor.timeOn', {
      time: formatTime(time, i18n.language),
      date: formatDate(time, i18n.language),
    })
}

/** The alert panel: what the doctor would see at this moment of the fast. */
function AlertPanel({ moment, firstAlert }: { moment: ReplayMoment; firstAlert?: string }) {
  const { t, i18n } = useTranslation()
  const language = i18n.language
  if (!moment.enough_data) {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-slate-400 bg-slate-50 p-4">
        <SignalLow aria-hidden className="mt-0.5 size-6 shrink-0" />
        <div className="grid gap-1 text-base">
          <p className="text-lg font-semibold">{t('monitor.noPredictionTitle')}</p>
          <p>{t('monitor.notEnoughData')}</p>
        </div>
      </div>
    )
  }
  const chance = moment.chance_of_low_next_60_min as Chance
  const lowest = t('monitor.lowest', {
    value: formatNumber(moment.predicted_lowest_mg_dl ?? 0, language),
    time: moment.predicted_lowest_time ? formatTime(moment.predicted_lowest_time, language) : '',
  })
  const reasons = moment.reasons ?? []
  const style = moment.alert
    ? 'border-red-400 bg-red-50 text-red-950'
    : moment.above_alert_threshold
      ? 'border-amber-400 bg-amber-50 text-amber-950'
      : 'border-slate-300 bg-white'
  const title = moment.alert
    ? t('monitor.alertTitle')
    : moment.above_alert_threshold
      ? t('monitor.stillAboveTitle')
      : t('monitor.noAlertTitle')
  const Icon = moment.alert ? OctagonAlert : moment.above_alert_threshold ? TriangleAlert : CircleDot
  return (
    <div className={cn('flex items-start gap-3 rounded-xl border-2 p-4', style)}>
      <Icon aria-hidden className="mt-0.5 size-6 shrink-0" />
      <div className="grid gap-2 text-base">
        <p className="text-lg font-semibold">{title}</p>
        {moment.above_alert_threshold && !moment.alert && firstAlert && (
          <p>{t('monitor.stillAboveDetail', { time: formatTime(firstAlert, language) })}</p>
        )}
        <p className="flex flex-wrap items-center gap-2">
          {t('monitor.estimatedChance')} <ChanceBadge chance={chance} />
        </p>
        <p>{lowest}</p>
        {reasons.length > 0 && (
          <div>
            <p className="font-medium">{t('monitor.mainReasons')}</p>
            <ul className="list-disc pl-6">
              {reasons.map((r) => (
                <li key={r.feature}>{language === 'hi' ? r.hi : r.en}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}

function Monitor({ patientId, overview }: { patientId: string; overview: ReplayOverview }) {
  const { t, i18n } = useTranslation()
  const language = i18n.language
  const momentText = useMomentText()
  const sliderId = useId()
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [showAfter, setShowAfter] = useState(false)
  const last = overview.times.length - 1
  const settled = useDebouncedValue(index, playing ? 0 : 200)
  const now = overview.times[settled]

  const moment = useQuery({
    queryKey: ['replay-at', patientId, now],
    queryFn: () => fetchReplayAt(patientId, now),
    placeholderData: keepPreviousData,
    staleTime: Infinity,
  })
  const start = addMinutes(now, -HOURS_BEFORE * 60)
  const end = addMinutes(now, HOURS_AFTER * 60)
  const recorded = useQuery({
    queryKey: ['timeseries', patientId, overview.fast_start, overview.fast_end, 'monitor'],
    queryFn: () =>
      fetchTimeseries(
        patientId,
        addMinutes(overview.fast_start, -HOURS_BEFORE * 60),
        addMinutes(overview.fast_end, HOURS_AFTER * 60),
      ),
    enabled: showAfter,
    staleTime: Infinity,
  })

  // While playing, the replay moves forward by one step after each answer arrives.
  useEffect(() => {
    if (!playing || moment.isFetching) return
    const timer = window.setTimeout(() => {
      if (index + 1 >= last) setPlaying(false)
      setIndex(Math.min(last, index + 1))
    }, 600)
    return () => window.clearTimeout(timer)
  }, [playing, index, last, moment.isFetching])

  const alertsSoFar = overview.alerts.filter((a) => toDate(a.time) <= toDate(now))
  const nextAlert = overview.alerts.find((a) => toDate(a.time) > toDate(overview.times[index]))
  const jump = (minutes: number) =>
    setIndex((i) => Math.max(0, Math.min(last, i + Math.round(minutes / STEP_MINUTES))))
  const goTo = (time: string) => setIndex(Math.max(0, overview.times.indexOf(time)))

  const data = moment.data
  const lines: GlucoseLine[] = []
  if (data) {
    lines.push({
      id: 'cgm',
      name: t('monitor.readingsSoFar'),
      times: data.glucose.times,
      values: data.glucose.values,
      colour: COLOURS.measured,
      style: 'solid',
    })
    if (data.forecast) {
      lines.push({
        id: 'forecast',
        name: t('monitor.forecast'),
        times: data.forecast.times,
        values: data.forecast.p50,
        colour: COLOURS.planB,
        style: 'dashed',
        band: { name: t('monitor.forecastBand'), lower: data.forecast.p10, upper: data.forecast.p90 },
      })
    }
  }
  const later = recorded.data?.signals.glucose_cgm
  if (showAfter && later) {
    const from = toDate(now).getTime()
    const keep = later.times.map((time) => toDate(time).getTime() > from)
    lines.push({
      id: 'after',
      name: t('monitor.readingsAfter'),
      times: later.times.filter((_, i) => keep[i]),
      values: later.values.filter((_, i) => keep[i]),
      colour: COLOURS.average,
      style: 'dotted',
    })
  }

  return (
    <div className="grid gap-5">
      <p className="max-w-4xl text-base">{t('monitor.intro')}</p>

      <section className="grid gap-3 rounded-xl border bg-card p-4" aria-label={t('monitor.controls')}>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <label htmlFor={sliderId} className="text-lg font-semibold">
            {t('monitor.sliderLabel')}
          </label>
          <p className="text-lg font-semibold tabular-nums" aria-live="polite">
            {momentText(overview.times[index])}
          </p>
        </div>
        <input
          id={sliderId}
          type="range"
          min={0}
          max={last}
          step={1}
          value={index}
          aria-valuetext={momentText(overview.times[index])}
          onChange={(e) => {
            setPlaying(false)
            setIndex(Number(e.target.value))
          }}
          className="h-8 w-full accent-[var(--primary)]"
        />
        <div className="flex flex-wrap justify-between gap-2 text-base text-muted-foreground">
          <span>{t('monitor.fastStart', { time: momentText(overview.fast_start) })}</span>
          <span>{t('monitor.fastEnd', { time: momentText(overview.fast_end) })}</span>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" className="text-base" onClick={() => jump(-30)}>
            <ChevronsLeft aria-hidden />
            {t('monitor.back30')}
          </Button>
          <Button variant="outline" className="text-base" onClick={() => jump(-STEP_MINUTES)}>
            <ChevronLeft aria-hidden />
            {t('monitor.back5')}
          </Button>
          <Button className="text-base" onClick={() => setPlaying((p) => !p)} aria-pressed={playing}>
            {playing ? <Pause aria-hidden /> : <Play aria-hidden />}
            {playing ? t('monitor.pause') : t('monitor.play')}
          </Button>
          <Button variant="outline" className="text-base" onClick={() => jump(STEP_MINUTES)}>
            {t('monitor.forward5')}
            <ChevronRight aria-hidden />
          </Button>
          <Button variant="outline" className="text-base" onClick={() => jump(30)}>
            {t('monitor.forward30')}
            <ChevronsRight aria-hidden />
          </Button>
          <Button
            variant="outline"
            className="text-base"
            disabled={!nextAlert}
            onClick={() => nextAlert && goTo(nextAlert.time)}
          >
            <SkipForward aria-hidden />
            {t('monitor.nextAlert')}
          </Button>
        </div>
      </section>

      {moment.isError && <LoadError error={moment.error} onRetry={() => void moment.refetch()} />}
      {!data && moment.isPending && <Loading text={t('monitor.loading')} />}
      {data && (
        <div className={cn('grid gap-5', moment.isFetching && !playing && 'opacity-70')}>
          <div aria-live="polite">
            <AlertPanel moment={data} firstAlert={alertsSoFar.at(-1)?.time} />
          </div>

          <Section
            title={t('monitor.glucoseTitle')}
            description={t('monitor.glucoseDescription')}
            action={
              <div className="flex items-center gap-2">
                <Checkbox
                  id={`${sliderId}-after`}
                  checked={showAfter}
                  onCheckedChange={(checked) => setShowAfter(checked === true)}
                />
                <Label htmlFor={`${sliderId}-after`} className="text-base font-normal">
                  {t('monitor.showAfter')}
                </Label>
              </div>
            }
          >
            <GlucoseChart
              height={340}
              start={start}
              end={end}
              lines={lines}
              windows={[
                {
                  start: overview.fast_start,
                  end: overview.fast_end,
                  label: t('monitor.fastWindow'),
                },
              ]}
              moments={[{ time: now, label: t('monitor.now') }]}
              summary={
                data.enough_data
                  ? t('monitor.glucoseSummary', {
                      time: formatTime(now, language),
                      percent: data.chance_of_low_next_60_min?.percent ?? 0,
                      value: data.predicted_lowest_mg_dl ?? 0,
                    })
                  : t('monitor.notEnoughData')
              }
            />
          </Section>

          <Section title={t('monitor.timelineTitle')} description={t('monitor.timelineDescription')}>
            <ChanceChart
              times={overview.times}
              chances={overview.chances.map((c, i) =>
                i <= settled && overview.enough_data[i] ? c : null,
              )}
              threshold={overview.alert_threshold}
              alerts={alertsSoFar.map((a) => a.time)}
              now={now}
              start={overview.fast_start}
              end={overview.fast_end}
              summary={t('monitor.timelineSummary', { count: alertsSoFar.length })}
            />
            <div>
              <h3 className="text-lg font-semibold">{t('monitor.alertsSoFar')}</h3>
              {alertsSoFar.length === 0 ? (
                <p className="text-muted-foreground">{t('monitor.noAlertsYet')}</p>
              ) : (
                <ul className="mt-1 flex flex-wrap gap-2">
                  {alertsSoFar.map((a) => (
                    <li key={a.time}>
                      <Button variant="outline" className="text-base" onClick={() => goTo(a.time)}>
                        <OctagonAlert aria-hidden className="text-red-700" />
                        {t('monitor.alertAt', {
                          time: formatTime(a.time, language),
                          percent: a.chance.percent,
                        })}
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Section>

          <Section title={t('monitor.signalsTitle')} description={t('monitor.signalsDescription')}>
            <div className="grid gap-6 lg:grid-cols-3">
              {(
                [
                  ['heart_rate', 'monitor.heartRate', 'virtual.history.bpm'],
                  ['hrv_rmssd', 'monitor.hrv', 'monitor.ms'],
                  ['steps', 'monitor.steps', 'monitor.stepsUnit'],
                ] as const
              ).map(([key, title, unit]) => (
                <div key={key}>
                  <h3 className="mb-2 text-lg font-semibold">{t(title)}</h3>
                  <SignalChart
                    start={start}
                    end={end}
                    times={data[key].times}
                    values={data[key].values}
                    unit={t(unit)}
                    summary={t('monitor.signalSummary', { signal: t(title) })}
                  />
                </div>
              ))}
            </div>
          </Section>
        </div>
      )}
    </div>
  )
}

/** Screen 4: the live fasting monitor, which replays a recorded fasting day. */
export function MonitorPage() {
  const { id = '' } = useParams()
  const { t } = useTranslation()
  const overview = useQuery({
    queryKey: ['replay', id],
    queryFn: () => fetchReplay(id),
    staleTime: Infinity,
  })
  return (
    <div className="grid gap-4">
      <h2 className="sr-only">{t('screens.monitor')}</h2>
      <QueryState query={overview} loadingText={t('monitor.loadingDay')}>
        {(data) => <Monitor key={id} patientId={id} overview={data} />}
      </QueryState>
    </div>
  )
}
