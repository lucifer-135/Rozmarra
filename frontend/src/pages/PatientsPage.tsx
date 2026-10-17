import { useQuery } from '@tanstack/react-query'
import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { fetchPatients } from '@/api/client'
import {
  ChanceBadge,
  DehydrationBadge,
  IdfDarBadge,
  PlanStatusBadge,
} from '@/components/badges'
import { QueryState } from '@/components/QueryState'
import { Card, CardContent } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatDate } from '@/lib/format'
import { useFastName, usePatientName } from '@/lib/hooks'

/** Screen 1: the patients who plan to fast, sorted by the predicted chance of low blood sugar. */
export function PatientsPage() {
  const { t, i18n } = useTranslation()
  const fastName = useFastName()
  const patientName = usePatientName()
  const patients = useQuery({ queryKey: ['patients'], queryFn: fetchPatients })

  return (
    <div className="grid gap-5">
      <div className="grid gap-2">
        <h1 className="text-2xl font-semibold">{t('patients.title')}</h1>
        <p className="max-w-4xl text-base text-muted-foreground">{t('patients.intro')}</p>
      </div>
      <QueryState query={patients} loadingText={t('patients.loading')}>
        {(rows) => (
          <Card className="py-2">
            <CardContent className="px-2">
              <Table className="text-base">
                <TableCaption className="text-base">{t('patients.caption')}</TableCaption>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-base">{t('patients.columns.patient')}</TableHead>
                    <TableHead className="text-base">{t('patients.columns.fast')}</TableHead>
                    <TableHead className="text-base">{t('patients.columns.idfDar')}</TableHead>
                    <TableHead className="text-base whitespace-normal">
                      {t('patients.columns.chance')}
                    </TableHead>
                    <TableHead className="text-base">{t('patients.columns.status')}</TableHead>
                    <TableHead className="text-base">{t('patients.columns.notes')}</TableHead>
                    <TableHead className="text-base">
                      <span className="sr-only">{t('patients.columns.open')}</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((row) => (
                    <TableRow key={row.patient_id}>
                      <TableCell className="py-3">
                        <Link
                          to={`/patients/${row.patient_id}`}
                          className="font-medium text-primary underline-offset-4 hover:underline"
                        >
                          {t('patient.nameAndAge', { name: patientName(row), age: row.age })}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <div>{fastName(row.template_id, row.fast)}</div>
                        <div className="text-muted-foreground">
                          {formatDate(row.fast_date, i18n.language)}
                        </div>
                      </TableCell>
                      <TableCell>
                        <IdfDarBadge
                          category={row.idf_dar_category}
                          total={row.idf_dar_total}
                          named={false}
                        />
                      </TableCell>
                      <TableCell>
                        <ChanceBadge chance={row.chance_of_low_during_fast} />
                      </TableCell>
                      <TableCell>
                        <PlanStatusBadge status={row.plan_status} />
                      </TableCell>
                      <TableCell>
                        {row.dehydration_caution ? (
                          <DehydrationBadge />
                        ) : (
                          <span className="text-muted-foreground">{t('patients.noNotes')}</span>
                        )}
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        <Link
                          to={`/patients/${row.patient_id}/simulator`}
                          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-primary underline-offset-4 hover:underline"
                        >
                          {t('patients.testPlan')}
                          <span className="sr-only">
                            {t('patients.forPatient', { name: patientName(row) })}
                          </span>
                          <ChevronRight aria-hidden className="size-4" />
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </QueryState>
      <p className="max-w-4xl text-base text-muted-foreground">{t('patients.chanceNote')}</p>
    </div>
  )
}
