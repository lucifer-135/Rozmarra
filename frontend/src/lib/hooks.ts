import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchPlanOptions, fetchTemplates } from '@/api/client'
import type { FastTemplate, MedicineOption } from '@/api/types'

export function useTemplates() {
  return useQuery({ queryKey: ['templates'], queryFn: fetchTemplates, staleTime: Infinity })
}

export function usePlanOptions() {
  return useQuery({ queryKey: ['plan-options'], queryFn: fetchPlanOptions, staleTime: Infinity })
}

/** The short name of a fast in the language of the dashboard, for example "Karva Chauth". */
export function useFastName(): (templateId: string, fallback?: string) => string {
  const { i18n } = useTranslation()
  const templates = useTemplates()
  return (templateId, fallback = '') => {
    const template = templates.data?.find((t: FastTemplate) => t.id === templateId)
    if (!template) return fallback
    return i18n.language === 'hi' ? template.name_hi.split(':')[0] : template.short_name
  }
}

/** The name of a medicine in the language of the dashboard. */
export function useMedicineName(): (name: string) => string {
  const { i18n } = useTranslation()
  const options = usePlanOptions()
  return (name) => {
    const medicine = options.data?.medicines.find((m: MedicineOption) => m.name === name)
    if (!medicine) return name
    return i18n.language === 'hi' ? medicine.display_name_hi : medicine.display_name
  }
}

/** The value after it has stayed the same for a short time, to avoid a request for each step. */
export function useDebouncedValue<T>(value: T, delay = 200): T {
  const [settled, setSettled] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), delay)
    return () => window.clearTimeout(timer)
  }, [value, delay])
  return settled
}
