import { useQuery } from '@tanstack/react-query'
import { Dna, Info } from 'lucide-react'
import { useParams } from 'react-router'
import { useTranslation } from 'react-i18next'
import { fetchHistory, fetchIdfDar, fetchPatient, fetchTimeseries, fetchTwin } from '@/api/client'
import type { History, IdfDar, PatientDetail, Twin } from '@/api/types'
import { DailyBarChart } from '@/charts/DailyBarChart'
import { GlucoseChart } from '@/charts/GlucoseChart'
import { SignalChart } from '@/charts/SignalChart'
import { COLOURS } from '@/charts/theme'
import { IdfDarBadge } from '@/components/badges'
import { QueryState } from '@/components/QueryState'
import { Facts, Section, StatTile } from '@/components/Section'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatDate, formatNumber, formatTime } from '@/lib/format'
import { useFastName, usePatientName, useMedicineName } from '@/lib/hooks'

function useDose() {
  const { t, i18n } = useTranslation()
  return (dose: number, unit: string) =>
    `${formatNumber(dose, i18n.language, 1)} ${t(`units.${unit}`, { defaultValue: unit })}`
}

function RecordSection({ patient }: { patient: PatientDetail }) {
  const { t, i18n } = useTranslation()
  const language = i18n.language
  const n = (v: number, digits = 0) => formatNumber(v, language, digits)
  const yesNo = (v: boolean) => (v ? t('common.yes') : t('common.no'))
  return (
    <Section title={t('virtual.record.title')} description={t('virtual.record.description')}>
      <Facts
        items={[
          [t('virtual.record.sex'), t(`virtual.record.sexValue.${patient.sex}`)],
          [t('virtual.record.city'), patient.city],
          [t('virtual.record.occupation'), patient.occupation],
          [
            t('virtual.record.fastWord'),
            <span key="fast-word" lang="hi">
              {patient.fast_word}
            </span>,
          ],
          [
            t('virtual.record.yearsWithDiabetes'),
            t('virtual.record.years', { count: patient.years_with_diabetes }),
          ],
          [t('virtual.record.hba1c'), `${n(patient.hba1c_percent, 1)}%`],
          [t('virtual.record.fastingGlucose'), `${n(patient.fasting_glucose_mg_dl)} mg/dL`],
          [t('virtual.record.egfr'), `${n(patient.egfr)} mL/min/1.73 m²`],
          [t('virtual.record.creatinine'), `${n(patient.creatinine_mg_dl, 2)} mg/dL`],
          [
            t('virtual.record.body'),
            t('virtual.record.bodyValue', {
              weight: n(patient.weight_kg),
              height: n(patient.height_cm),
              bmi: n(patient.bmi, 1),
            }),
          ],
          [t('virtual.record.bloodPressure'), patient.blood_pressure],
          [
            t('virtual.record.restingHeartRate'),
            t('virtual.record.beatsPerMinute', { value: n(patient.resting_heart_rate) }),
          ],
          [t('virtual.record.hypertension'), yesNo(patient.conditions.hypertension)],
          [t('virtual.record.kidneyDisease'), yesNo(patient.conditions.chronic_kidney_disease)],
          [
            t('virtual.record.heartDisease'),
            t(`virtual.record.heartDiseaseValue.${patient.conditions.heart_disease}`, {
              defaultValue: patient.conditions.heart_disease,
            }),
          ],
        ]}
      />
    </Section>
  )
}

function MedicinesSection({ patient }: { patient: PatientDetail }) {
  const { t, i18n } = useTranslation()
  const medicineName = useMedicineName()
  const dose = useDose()
  return (
    <Section title={t('virtual.medicines.title')} description={t('virtual.medicines.description')}>
      <ul className="grid gap-3">
        {patient.medicines.map((m) => (
          <li key={m.name}>
            <p className="font-medium">{medicineName(m.name)}</p>
            <p className="text-muted-foreground">
              {m.schedule
                .map((s) =>
                  t('virtual.medicines.doseAt', {
                    dose: dose(s.dose, s.unit),
                    time: formatTime(`2000-01-01T${s.time}`, i18n.language),
                  }),
                )
                .join(t('common.listSeparator'))}
            </p>
          </li>
        ))}
      </ul>
    </Section>
  )
}

function GeneSection({ patient }: { patient: PatientDetail }) {
  const { t, i18n } = useTranslation()
  const usual = patient.cyp2c9.genotype === '*1/*1'
  return (
    <Section title={t('virtual.gene.title')} description={t('virtual.gene.description')}>
      <div className="flex items-start gap-3">
        <Dna aria-hidden className="mt-0.5 size-5 shrink-0 text-primary" />
        <div className="grid gap-2">
          <p>
            {t('virtual.gene.genotype')}{' '}
            <span className="font-semibold">CYP2C9 {patient.cyp2c9.genotype}</span>
          </p>
          <p>{usual ? t('virtual.gene.usual') : t('virtual.gene.reduced')}</p>
          {!usual && (
            <p className="text-muted-foreground">
              {t('virtual.gene.clearance', {
                percent: formatNumber(patient.cyp2c9.clearance_factor * 100, i18n.language),
              })}
            </p>
          )}
        </div>
      </div>
    </Section>
  )
}

function IdfDarSection({ score }: { score: IdfDar }) {
  const { t, i18n } = useTranslation()
  const n = (v: number) => formatNumber(v, i18n.language, 1)
  return (
    <Section
      title={t('idfDar.title')}
      description={t('idfDar.description')}
      action={<IdfDarBadge category={score.category} total={score.total} />}
    >
      <Table className="text-base">
        <TableHeader>
          <TableRow>
            <TableHead className="text-base">{t('idfDar.item')}</TableHead>
            <TableHead className="text-base">{t('idfDar.detail')}</TableHead>
            <TableHead className="text-right text-base">{t('idfDar.points')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {score.items.map((item) => (
            <TableRow key={item.key}>
              <TableCell className="font-medium whitespace-normal">
                {t(`idfDar.items.${item.key}`, { defaultValue: item.label })}
              </TableCell>
              <TableCell className="whitespace-normal text-muted-foreground">
                {item.detail}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {t('idfDar.pointsOf', { points: n(item.points), max: n(item.max_points) })}
              </TableCell>
            </TableRow>
          ))}
          <TableRow className="font-semibold">
            <TableCell colSpan={2}>{t('idfDar.total')}</TableCell>
            <TableCell className="text-right tabular-nums">{n(score.total)}</TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <p className="text-muted-foreground">{t('idfDar.bands')}</p>
      {score.missing.length > 0 && (
        <p>{t('idfDar.missing', { range: `${n(score.range[0])} to ${n(score.range[1])}` })}</p>
      )}
      {score.note && (
        <p className="flex items-start gap-2 text-muted-foreground">
          <Info aria-hidden className="mt-0.5 size-4 shrink-0" />
          {t('idfDar.otherFasts')}
        </p>
      )}
    </Section>
  )
}

function HistorySection({ patientId, history }: { patientId: string; history: History }) {
  const { t, i18n } = useTranslation()
  const language = i18n.language
  const n = (v: number | null, digits = 0) => (v == null ? '-' : formatNumber(v, language, digits))
  const series = useQuery({
    queryKey: ['timeseries', patientId, history.start, history.end],
    queryFn: () => fetchTimeseries(patientId, history.start, history.end),
  })
  const s = history.summary
  const range = {
    from: formatDate(history.days[0].date, language),
    to: formatDate(history.days[history.days.length - 1].date, language),
  }
  return (
    <Section
      title={t('virtual.history.title', { days: s.days })}
      description={t('virtual.history.description', range)}
    >
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatTile
          label={t('virtual.history.meanGlucose')}
          value={`${n(s.mean_glucose_mg_dl)} mg/dL`}
        />
        <StatTile label={t('virtual.history.timeInRange')} value={`${n(s.time_in_range_percent)}%`} />
        <StatTile
          label={t('virtual.history.timeBelow70')}
          value={`${n(s.time_below_70_percent, 1)}%`}
        />
        <StatTile
          label={t('virtual.history.meanSteps')}
          value={t('virtual.history.stepsValue', { value: n(s.mean_daily_steps) })}
        />
        <StatTile
          label={t('virtual.history.meanSleep')}
          value={t('virtual.history.hoursValue', { value: n(s.mean_sleep_hours, 1) })}
        />
      </div>
      <QueryState query={series} loadingText={t('virtual.history.loadingSignals')}>
        {(data) => {
          const glucose = data.signals.glucose_cgm
          const heart = data.signals.heart_rate
          return (
            <div className="grid gap-6">
              <div>
                <h3 className="mb-2 text-lg font-semibold">{t('virtual.history.glucoseTitle')}</h3>
                <GlucoseChart
                  multiDay
                  height={300}
                  start={history.start}
                  end={history.end}
                  lines={[
                    {
                      id: 'cgm',
                      name: t('chart.measuredGlucose'),
                      times: glucose?.times ?? [],
                      values: glucose?.values ?? [],
                      colour: COLOURS.measured,
                      style: 'solid',
                    },
                  ]}
                  summary={t('virtual.history.glucoseSummary', {
                    mean: n(s.mean_glucose_mg_dl),
                    inRange: n(s.time_in_range_percent),
                    below: n(s.time_below_70_percent, 1),
                    ...range,
                  })}
                />
              </div>
              <div className="grid gap-6 lg:grid-cols-3">
                <div>
                  <h3 className="mb-2 text-lg font-semibold">{t('virtual.history.heartTitle')}</h3>
                  <SignalChart
                    multiDay
                    start={history.start}
                    end={history.end}
                    times={heart?.times ?? []}
                    values={heart?.values ?? []}
                    unit={t('virtual.history.bpm')}
                    summary={t('virtual.history.heartSummary', range)}
                  />
                </div>
                <div>
                  <h3 className="mb-2 text-lg font-semibold">{t('virtual.history.stepsTitle')}</h3>
                  <DailyBarChart
                    dates={history.days.map((d) => d.date)}
                    values={history.days.map((d) => d.steps)}
                    unit={t('virtual.history.stepsUnit')}
                    summary={t('virtual.history.stepsSummary', {
                      value: n(s.mean_daily_steps),
                    })}
                  />
                </div>
                <div>
                  <h3 className="mb-2 text-lg font-semibold">{t('virtual.history.sleepTitle')}</h3>
                  <DailyBarChart
                    dates={history.days.map((d) => d.date)}
                    values={history.days.map((d) => d.sleep_hours)}
                    unit={t('virtual.history.hoursUnit')}
                    digits={1}
                    summary={t('virtual.history.sleepSummary', {
                      value: n(s.mean_sleep_hours, 1),
                    })}
                  />
                </div>
              </div>
            </div>
          )
        }}
      </QueryState>
    </Section>
  )
}

function scientific(value: number, language: string): string {
  if (value === 0 || (Math.abs(value) >= 0.01 && Math.abs(value) < 10_000)) {
    return formatNumber(value, language, 4)
  }
  const exponent = Math.floor(Math.log10(Math.abs(value)))
  const mantissa = value / 10 ** exponent
  const superscript = String(exponent).replace(/[-0-9]/g, (c) => '⁻⁰¹²³⁴⁵⁶⁷⁸⁹'['-0123456789'.indexOf(c)])
  return `${formatNumber(mantissa, language, 2)} × 10${superscript}`
}

function TwinSection({ twin }: { twin: Twin }) {
  const { t, i18n } = useTranslation()
  const q = twin.fit_quality
  const n = (v: number | null, digits = 1) =>
    v == null ? '-' : formatNumber(v, i18n.language, digits)
  return (
    <Section title={t('virtual.twin.title')} description={t('virtual.twin.description')}>
      <p>
        {t('virtual.twin.donor', {
          donor: twin.donor.patient_id ?? '-',
          dataset: twin.donor.dataset ?? '-',
        })}
      </p>
      {q.two_hour_forecast_rmse_mg_dl != null && (
        <p className="text-lg font-medium">
          {t('virtual.twin.fitSentence', { value: n(q.two_hour_forecast_rmse_mg_dl) })}
        </p>
      )}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatTile
          label={t('virtual.twin.twoHourError')}
          value={`${n(q.two_hour_forecast_rmse_mg_dl)} mg/dL`}
        />
        <StatTile label={t('virtual.twin.heldOutError')} value={`${n(q.held_out_rmse_mg_dl)} mg/dL`} />
        <StatTile label={t('virtual.twin.heldOutMard')} value={`${n(q.held_out_mard_percent)}%`} />
      </div>
      <p className="text-muted-foreground">{t('virtual.twin.reference')}</p>
      <details className="rounded-lg border bg-background p-4">
        <summary className="cursor-pointer font-medium">{t('virtual.twin.parameters')}</summary>
        <Table className="mt-3 text-base">
          <TableHeader>
            <TableRow>
              <TableHead className="text-base">{t('virtual.twin.parameter')}</TableHead>
              <TableHead className="text-right text-base">{t('virtual.twin.value')}</TableHead>
              <TableHead className="text-right text-base">{t('virtual.twin.spread')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {twin.parameters.map((p) => (
              <TableRow key={p.name}>
                <TableCell className="whitespace-normal">
                  {t(`virtual.twin.parameterNames.${p.name}`, { defaultValue: p.label })}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {scientific(p.value, i18n.language)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatNumber(p.log_sd, i18n.language, 2)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <p className="mt-3 text-muted-foreground">{t('virtual.twin.spreadNote')}</p>
      </details>
    </Section>
  )
}

function SourcesSection({ donor }: { donor: string }) {
  const { t } = useTranslation()
  return (
    <Section title={t('virtual.sources.title')}>
      <ul className="list-disc space-y-1 pl-6">
        <li>{t('virtual.sources.record')}</li>
        <li>{t('virtual.sources.twin', { donor })}</li>
        <li>{t('virtual.sources.history')}</li>
      </ul>
    </Section>
  )
}

/** Screen 2: what the twin knows about the patient. */
export function VirtualPatientPage() {
  const { id = '' } = useParams()
  const { t, i18n } = useTranslation()
  const fastName = useFastName()
  const patientName = usePatientName()
  const patient = useQuery({ queryKey: ['patient', id], queryFn: () => fetchPatient(id) })
  const score = useQuery({ queryKey: ['idf-dar', id], queryFn: () => fetchIdfDar(id) })
  const twin = useQuery({ queryKey: ['twin', id], queryFn: () => fetchTwin(id) })
  const history = useQuery({ queryKey: ['history', id], queryFn: () => fetchHistory(id) })

  return (
    <div className="grid gap-6">
      <h2 className="sr-only">{t('screens.virtualPatient')}</h2>
      <QueryState query={patient}>
        {(p) => (
          <>
            <p className="max-w-4xl text-base">
              {t('virtual.intro', {
                name: patientName(p),
                fast: fastName(p.planned_fast.template_id),
                date: formatDate(p.planned_fast.date, i18n.language),
              })}
              {p.planned_fast.note && ` ${p.planned_fast.note}`}
            </p>
            <div className="grid gap-6 lg:grid-cols-2">
              <RecordSection patient={p} />
              <div className="grid content-start gap-6">
                <MedicinesSection patient={p} />
                <GeneSection patient={p} />
              </div>
            </div>
          </>
        )}
      </QueryState>
      <QueryState query={history}>{(h) => <HistorySection patientId={id} history={h} />}</QueryState>
      <div className="grid gap-6 lg:grid-cols-2">
        <QueryState query={score}>{(s) => <IdfDarSection score={s} />}</QueryState>
        <div className="grid content-start gap-6">
          <QueryState query={twin}>
            {(tw) => (
              <>
                <TwinSection twin={tw} />
                <SourcesSection donor={tw.donor.patient_id ?? '-'} />
              </>
            )}
          </QueryState>
        </div>
      </div>
    </div>
  )
}
