import { useQuery } from '@tanstack/react-query'
import { ArrowDown, ChevronRight } from 'lucide-react'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { fetchPatients } from '@/api/client'
import {
  ChanceText,
  DehydrationBadge,
  IdfDarText,
  PlanStatusBadge,
} from '@/components/badges'
import { Lede, PageHeader } from '@/components/LearnMore'
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

/**
 * Screen 1: the patients who plan to fast, sorted by the predicted chance of low blood sugar.
 * The sorted column sits next to the name and is the strongest text in each row, so that the
 * eye follows the order of the list.
 */
export function PatientsPage() {
  const { t, i18n } = useTranslation()
  const fastName = useFastName()
  const patientName = usePatientName()
  const patients = useQuery({ queryKey: ['patients'], queryFn: fetchPatients })

  return (
    <div className="grid gap-8">
      <PageHeader title={t('patients.title')} lede={t('patients.intro')} />
      <QueryState query={patients} loadingText={t('patients.loading')}>
        {(rows) => (
          <Card className="py-2">
            <CardContent className="px-2">
              <Table className="text-[1rem]">
                <TableCaption className="text-base">{t('patients.caption')}</TableCaption>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-[1rem]">{t('patients.columns.patient')}</TableHead>
                    <TableHead className="text-[1rem] whitespace-normal" aria-sort="descending">
                      <span className="inline-flex max-w-[11rem] items-end gap-1">
                        {t('patients.columns.chance')}
                        <ArrowDown aria-hidden className="mb-1 size-4 shrink-0" />
                      </span>
                    </TableHead>
                    <TableHead className="text-[1rem]">{t('patients.columns.fast')}</TableHead>
                    <TableHead className="text-[1rem]">{t('patients.columns.idfDar')}</TableHead>
                    <TableHead className="text-[1rem]">{t('patients.columns.status')}</TableHead>
                    <TableHead className="text-[1rem]">{t('patients.columns.notes')}</TableHead>
                    {/* The shortcut column shows only on wide screens. On a narrower screen, such as a
                        projector, the table would cut it off, and the patient's name still opens
                        the patient. */}
                    <TableHead className="hidden text-[1rem] xl:table-cell">
                      <span className="sr-only">{t('patients.columns.open')}</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((row) => (
                    <TableRow key={row.patient_id}>
                      <TableCell className="py-3 whitespace-normal">
                        <Link
                          to={`/patients/${row.patient_id}`}
                          className="font-medium text-primary underline-offset-4 hover:underline"
                        >
                          {t('patient.nameAndAge', { name: patientName(row), age: row.age })}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <ChanceText chance={row.chance_of_low_during_fast} />
                      </TableCell>
                      <TableCell>
                        <div>{fastName(row.template_id, row.fast)}</div>
                        <div className="text-muted-foreground">
                          {formatDate(row.fast_date, i18n.language)}
                        </div>
                      </TableCell>
                      <TableCell>
                        <IdfDarText category={row.idf_dar_category} total={row.idf_dar_total} />
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
                      <TableCell className="hidden whitespace-nowrap xl:table-cell">
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
      <Lede text={t('patients.chanceNote')} className="max-w-[70ch] [&_p:first-child]:text-base" />
    </div>
  )
}
