import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { Link, NavLink, Outlet, useParams } from 'react-router'
import { useTranslation } from 'react-i18next'
import { fetchPatients } from '@/api/client'
import { DehydrationBadge, IdfDarBadge, PlanStatusBadge, SyntheticBadge } from '@/components/badges'
import { QueryState } from '@/components/QueryState'
import { formatDate } from '@/lib/format'
import { useFastName } from '@/lib/hooks'
import { cn } from '@/lib/utils'

const TABS = [
  { path: '', key: 'virtualPatient' },
  { path: 'simulator', key: 'simulator' },
  { path: 'monitor', key: 'monitor' },
  { path: 'plan', key: 'plan' },
] as const

const tabClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    '-mb-px border-b-2 px-3 py-2 text-base font-medium outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
    isActive
      ? 'border-primary text-foreground'
      : 'border-transparent text-muted-foreground hover:text-foreground',
  )

/** The heading of every patient screen, with the tabs that lead to the other screens. */
export function PatientLayout() {
  const { id = '' } = useParams()
  const { t, i18n } = useTranslation()
  const fastName = useFastName()
  const patients = useQuery({ queryKey: ['patients'], queryFn: fetchPatients })

  return (
    <QueryState query={patients}>
      {(rows) => {
        const row = rows.find((r) => r.patient_id === id)
        if (!row) {
          return (
            <div className="grid gap-4">
              <h1 className="text-2xl font-semibold">{t('patient.notFoundTitle')}</h1>
              <p className="text-base">{t('patient.notFound')}</p>
              <Link to="/patients" className="text-base text-primary underline">
                {t('patient.backToList')}
              </Link>
            </div>
          )
        }
        return (
          <div className="grid gap-6">
            <div className="grid gap-3">
              <Link
                to="/patients"
                className="inline-flex w-fit items-center gap-1 text-base text-primary underline-offset-4 hover:underline"
              >
                <ArrowLeft aria-hidden className="size-4" />
                {t('patient.backToList')}
              </Link>
              <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                <h1 className="text-2xl font-semibold">
                  {t('patient.nameAndAge', { name: row.name, age: row.age })}
                </h1>
                <p className="text-lg text-muted-foreground">
                  {t('patient.fastOn', {
                    fast: fastName(row.template_id, row.fast),
                    date: formatDate(row.fast_date, i18n.language),
                  })}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <SyntheticBadge />
                <IdfDarBadge category={row.idf_dar_category} total={row.idf_dar_total} />
                <PlanStatusBadge status={row.plan_status} />
                {row.dehydration_caution && <DehydrationBadge />}
              </div>
            </div>
            <nav aria-label={t('patient.screens')} className="flex flex-wrap gap-1 border-b">
              {TABS.map((tab) => (
                <NavLink
                  key={tab.key}
                  to={tab.path ? `/patients/${id}/${tab.path}` : `/patients/${id}`}
                  end
                  className={tabClass}
                >
                  {t(`screens.${tab.key}`)}
                </NavLink>
              ))}
            </nav>
            <Outlet />
          </div>
        )
      }}
    </QueryState>
  )
}
