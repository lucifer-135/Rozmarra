import { Plus, Trash2 } from 'lucide-react'
import { type ReactNode, useId } from 'react'
import { useTranslation } from 'react-i18next'
import type {
  FastTemplate,
  FastingPlan,
  FoodCategory,
  PlannedActivity,
  PlannedMeal,
  PlannedMedicine,
  PlanOptions,
} from '@/api/types'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  addDays,
  addMinutes,
  daysBetween,
  formatNumber,
  formatTime,
  joinDateTime,
  splitDateTime,
} from '@/lib/format'
import { cn } from '@/lib/utils'
import { planProblems } from './plan'

// The plan form of the fasting plan simulator (docs/prd.md, Screen 3). The form edits a
// plan in the format of the API. Rozmarra never changes a plan by itself: every change
// comes from the doctor.

const SELECT =
  'h-9 w-full rounded-md border border-input bg-background px-2 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50'
const DAY_OFFSETS = [-1, 0, 1, 2] as const


function DateTimeField({
  label,
  context,
  value,
  planDate,
  onChange,
  invalid,
}: {
  label: string
  // What the field belongs to, for example the name of a medicine, for screen readers.
  context?: string
  value: string
  planDate: string
  onChange: (value: string) => void
  invalid?: boolean
}) {
  const { t } = useTranslation()
  const id = useId()
  const { date, time } = splitDateTime(value)
  const offset = daysBetween(planDate, date)
  const name = context ? `${context}, ${label}` : label
  const offsets: number[] = DAY_OFFSETS.includes(offset as (typeof DAY_OFFSETS)[number])
    ? [...DAY_OFFSETS]
    : [...DAY_OFFSETS, offset]
  return (
    <fieldset className="grid gap-1">
      <legend className="mb-1 text-base font-medium">{label}</legend>
      <div className="grid grid-cols-[1fr_8.5rem] gap-2">
        <div>
          <label htmlFor={`${id}-day`} className="sr-only">
            {t('form.fieldDay', { name })}
          </label>
          <select
            id={`${id}-day`}
            className={SELECT}
            value={offset}
            onChange={(e) => onChange(joinDateTime(addDays(planDate, Number(e.target.value)), time))}
          >
            {offsets.map((o) => (
              <option key={o} value={o}>
                {t(`form.dayOffset.${o}`, { defaultValue: t('form.dayOffsetOther', { count: o }) })}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={`${id}-time`} className="sr-only">
            {t('form.fieldTime', { name })}
          </label>
          <Input
            id={`${id}-time`}
            type="time"
            className="text-base md:text-base"
            value={time}
            aria-invalid={invalid || undefined}
            onChange={(e) => e.target.value && onChange(joinDateTime(date, e.target.value))}
          />
        </div>
      </div>
    </fieldset>
  )
}

function NumberField({
  label,
  context,
  value,
  unit,
  step,
  min = 0,
  onChange,
  invalid,
  describedBy,
}: {
  label: string
  context?: string
  value: number
  unit: string
  step: number
  min?: number
  onChange: (value: number) => void
  invalid?: boolean
  describedBy?: string
}) {
  const id = useId()
  return (
    <div className="grid gap-1">
      <Label htmlFor={id} className="text-base">
        {label}
        {context && <span className="sr-only">, {context}</span>}
      </Label>
      <div className="flex items-center gap-2">
        <Input
          id={id}
          type="number"
          inputMode="decimal"
          className="text-base md:text-base"
          value={Number.isFinite(value) ? value : ''}
          step={step}
          min={min}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          onChange={(e) => onChange(e.target.value === '' ? Number.NaN : Number(e.target.value))}
        />
        <span className="shrink-0 text-base text-muted-foreground">{unit}</span>
      </div>
    </div>
  )
}

function Group({
  title,
  children,
  onAdd,
  addLabel,
}: {
  title: string
  children: ReactNode
  onAdd?: () => void
  addLabel?: string
}) {
  return (
    <section className="grid gap-3 border-t pt-4">
      <h3 className="text-lg font-semibold">{title}</h3>
      {children}
      {onAdd && (
        <Button type="button" variant="outline" className="w-fit text-base" onClick={onAdd}>
          <Plus aria-hidden />
          {addLabel}
        </Button>
      )}
    </section>
  )
}

function RemoveButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      aria-label={label}
      title={label}
      onClick={onClick}
    >
      <Trash2 aria-hidden />
    </Button>
  )
}

interface Props {
  plan: FastingPlan
  onChange: (plan: FastingPlan) => void
  options: PlanOptions
  templates: FastTemplate[]
  onTemplate: (templateId: string, date: string) => void
  templateBusy?: boolean
}

export function PlanForm({ plan, onChange, options, templates, onTemplate, templateBusy }: Props) {
  const { t, i18n } = useTranslation()
  const language = i18n.language
  const id = useId()
  const problems = planProblems(plan, options)
  const set = (patch: Partial<FastingPlan>) => onChange({ ...plan, ...patch })

  const setMeal = (i: number, patch: Partial<PlannedMeal>) =>
    set({ meals: plan.meals.map((m, k) => (k === i ? { ...m, ...patch } : m)) })
  const setMedicine = (i: number, patch: Partial<PlannedMedicine>) =>
    set({ medicines: plan.medicines.map((m, k) => (k === i ? { ...m, ...patch } : m)) })
  const setActivity = (i: number, patch: Partial<PlannedActivity>) =>
    set({ activities: plan.activities.map((a, k) => (k === i ? { ...a, ...patch } : a)) })

  const medicineOf = (name: string) => options.medicines.find((m) => m.name === name)
  const medicineName = (name: string) => {
    const m = medicineOf(name)
    if (!m) return name
    return language === 'hi' ? m.display_name_hi : m.display_name
  }
  const unitText = (unit: string) => t(`units.${unit}`, { defaultValue: unit })
  const templateName = (template: FastTemplate) =>
    language === 'hi' ? template.name_hi : template.name

  return (
    <form className="grid gap-4 text-base" onSubmit={(e) => e.preventDefault()}>
      <div className="grid gap-1">
        <Label htmlFor={`${id}-name`} className="text-base">
          {t('form.planName')}
        </Label>
        <Input
          id={`${id}-name`}
          className="text-base md:text-base"
          value={plan.plan_name}
          onChange={(e) => set({ plan_name: e.target.value })}
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-[1fr_11rem]">
        <div className="grid gap-1">
          <Label htmlFor={`${id}-template`} className="text-base">
            {t('form.template')}
          </Label>
          <select
            id={`${id}-template`}
            className={SELECT}
            value={plan.template_id}
            disabled={templateBusy}
            onChange={(e) => onTemplate(e.target.value, plan.date)}
          >
            {templates.map((template) => (
              <option key={template.id} value={template.id}>
                {templateName(template)}
              </option>
            ))}
          </select>
        </div>
        <div className="grid gap-1">
          <Label htmlFor={`${id}-date`} className="text-base">
            {t('form.date')}
          </Label>
          <Input
            id={`${id}-date`}
            type="date"
            className="text-base md:text-base"
            value={plan.date}
            disabled={templateBusy}
            onChange={(e) => e.target.value && onTemplate(plan.template_id, e.target.value)}
          />
        </div>
      </div>
      <p className="text-muted-foreground">{t('form.templateNote')}</p>

      <Group title={t('form.fastTitle')}>
        <div className="grid gap-3">
          <DateTimeField
            label={t('form.fastStart')}
            value={plan.fast_start}
            planDate={plan.date}
            onChange={(v) => set({ fast_start: v })}
          />
          <DateTimeField
            label={t('form.fastEnd')}
            value={plan.fast_end}
            planDate={plan.date}
            invalid={problems.includes('fastEnd')}
            onChange={(v) => set({ fast_end: v })}
          />
        </div>
        {problems.includes('fastEnd') && (
          <p role="alert" className="text-destructive">
            {t('form.problems.fastEnd')}
          </p>
        )}
        <div className="flex items-center gap-2">
          <Checkbox
            id={`${id}-water`}
            checked={plan.water_allowed}
            onCheckedChange={(checked) => set({ water_allowed: checked === true })}
          />
          <Label htmlFor={`${id}-water`} className="text-base font-normal">
            {t('form.waterAllowed')}
          </Label>
        </div>
      </Group>

      <Group
        title={t('form.mealsTitle')}
        addLabel={t('form.addMeal')}
        onAdd={() =>
          set({
            meals: [
              ...plan.meals,
              {
                time: plan.fast_end,
                label: t('form.newMeal'),
                label_hi: '',
                food_category: 'mixed',
                carbs_g: 40,
                breaks_fast: false,
              },
            ],
          })
        }
      >
        {plan.meals.length === 0 && <p className="text-muted-foreground">{t('form.noMeals')}</p>}
        {plan.meals.map((meal, i) => (
          <fieldset key={i} className="grid gap-3 rounded-lg border bg-background p-3">
            <legend className="px-1 font-medium">
              {t('form.mealNumber', { number: i + 1 })}
            </legend>
            <div className="flex items-end gap-2">
              <div className="grid flex-1 gap-1">
                <Label htmlFor={`${id}-meal-${i}-label`} className="text-base">
                  {t('form.mealLabel')}
                </Label>
                <Input
                  id={`${id}-meal-${i}-label`}
                  className="text-base md:text-base"
                  value={language === 'hi' && meal.label_hi ? meal.label_hi : meal.label}
                  onChange={(e) =>
                    setMeal(
                      i,
                      language === 'hi' && meal.label_hi
                        ? { label_hi: e.target.value }
                        : { label: e.target.value },
                    )
                  }
                />
              </div>
              <RemoveButton
                label={t('form.removeMeal', { number: i + 1 })}
                onClick={() => set({ meals: plan.meals.filter((_, k) => k !== i) })}
              />
            </div>
            <div className="grid gap-3">
              <DateTimeField
                label={t('form.time')}
                context={language === 'hi' && meal.label_hi ? meal.label_hi : meal.label}
                value={meal.time}
                planDate={plan.date}
                onChange={(v) => setMeal(i, { time: v })}
              />
              <NumberField
                label={t('form.carbs')}
                context={language === 'hi' && meal.label_hi ? meal.label_hi : meal.label}
                value={meal.carbs_g}
                unit="g"
                step={5}
                invalid={!Number.isFinite(meal.carbs_g)}
                onChange={(v) => setMeal(i, { carbs_g: v })}
              />
            </div>
            <div className="grid gap-1">
              <Label htmlFor={`${id}-meal-${i}-food`} className="text-base">
                {t('form.foodType')}
              </Label>
              <select
                id={`${id}-meal-${i}-food`}
                className={SELECT}
                value={meal.food_category}
                onChange={(e) => setMeal(i, { food_category: e.target.value as FoodCategory })}
              >
                {options.food_categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {t(`form.food.${c.id}`, { defaultValue: c.label })}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id={`${id}-meal-${i}-breaks`}
                checked={meal.breaks_fast}
                onCheckedChange={(checked) =>
                  // Only one meal can break the fast, so ticking one meal clears the others.
                  set({
                    meals: plan.meals.map((m, k) =>
                      k === i
                        ? { ...m, breaks_fast: checked === true }
                        : { ...m, breaks_fast: checked === true ? false : m.breaks_fast },
                    ),
                  })
                }
              />
              <Label htmlFor={`${id}-meal-${i}-breaks`} className="text-base font-normal">
                {t('form.breaksFast')}
              </Label>
            </div>
          </fieldset>
        ))}
      </Group>

      <Group
        title={t('form.medicinesTitle')}
        addLabel={t('form.addMedicine')}
        onAdd={() => {
          const first = options.medicines.find((m) => m.for_diabetes)
          if (!first) return
          set({
            medicines: [
              ...plan.medicines,
              {
                name: first.name,
                dose: first.standard_dose,
                time: plan.fast_start,
                usual_dose: null,
                usual_time: null,
              },
            ],
          })
        }}
      >
        {plan.medicines.length === 0 && (
          <p className="text-muted-foreground">{t('form.noMedicines')}</p>
        )}
        {plan.medicines.map((dose, i) => {
          const medicine = medicineOf(dose.name)
          const unit = unitText(medicine?.unit ?? '')
          const tooHigh = problems.includes(`dose:${i}`)
          const isNew = dose.usual_dose == null
          const helpId = `${id}-medicine-${i}-help`
          return (
            <fieldset key={i} className="grid gap-3 rounded-lg border bg-background p-3">
              <legend className="px-1 font-medium">
                {t('form.medicineNumber', { number: i + 1 })}
              </legend>
              <div className="flex items-end gap-2">
                <div className="grid flex-1 gap-1">
                  <Label htmlFor={`${id}-medicine-${i}-name`} className="text-base">
                    {t('form.medicine')}
                  </Label>
                  {isNew ? (
                    <select
                      id={`${id}-medicine-${i}-name`}
                      className={SELECT}
                      value={dose.name}
                      onChange={(e) => {
                        const chosen = medicineOf(e.target.value)
                        setMedicine(i, {
                          name: e.target.value,
                          dose: chosen?.standard_dose ?? dose.dose,
                        })
                      }}
                    >
                      {options.medicines
                        .filter((m) => m.for_diabetes)
                        .map((m) => (
                          <option key={m.name} value={m.name}>
                            {medicineName(m.name)}
                          </option>
                        ))}
                    </select>
                  ) : (
                    <p id={`${id}-medicine-${i}-name`} className="py-1 font-medium">
                      {medicineName(dose.name)}
                    </p>
                  )}
                </div>
                <RemoveButton
                  label={t('form.removeMedicine', {
                    number: i + 1,
                    name: medicineName(dose.name),
                  })}
                  onClick={() => set({ medicines: plan.medicines.filter((_, k) => k !== i) })}
                />
              </div>
              <div className="grid gap-3">
                <NumberField
                  label={t('form.dose')}
                  context={medicineName(dose.name)}
                  value={dose.dose}
                  unit={unit}
                  step={medicine?.unit === 'units' ? 1 : 0.5}
                  invalid={tooHigh}
                  describedBy={helpId}
                  onChange={(v) => setMedicine(i, { dose: v })}
                />
                <DateTimeField
                  label={t('form.time')}
                  context={medicineName(dose.name)}
                  value={dose.time}
                  planDate={plan.date}
                  onChange={(v) => setMedicine(i, { time: v })}
                />
              </div>
              <p id={helpId} className={cn('text-muted-foreground', tooHigh && 'text-destructive')}>
                {tooHigh && medicine
                  ? t('form.problems.dose', {
                      max: formatNumber(medicine.max_single_dose, language, 1),
                      unit,
                    })
                  : dose.usual_dose != null && dose.usual_time
                    ? t('form.usualDose', {
                        dose: formatNumber(dose.usual_dose, language, 1),
                        unit,
                        time: formatTime(dose.usual_time, language),
                      })
                    : t('form.addedMedicine')}
              </p>
            </fieldset>
          )
        })}
      </Group>

      <Group
        title={t('form.activitiesTitle')}
        addLabel={t('form.addActivity')}
        onAdd={() => {
          const preset = options.activities[0]
          const start = plan.fast_end
          set({
            activities: [
              ...plan.activities,
              {
                start,
                end: addMinutes(start, preset.minutes),
                label: preset.label,
                mets: preset.mets,
              },
            ],
          })
        }}
      >
        {plan.activities.length === 0 && (
          <p className="text-muted-foreground">{t('form.noActivities')}</p>
        )}
        {plan.activities.map((activity, i) => {
          const preset = options.activities.find((a) => a.label === activity.label)
          return (
            <fieldset key={i} className="grid gap-3 rounded-lg border bg-background p-3">
              <legend className="px-1 font-medium">
                {t('form.activityNumber', { number: i + 1 })}
              </legend>
              <div className="flex items-end gap-2">
                <div className="grid flex-1 gap-1">
                  <Label htmlFor={`${id}-activity-${i}-type`} className="text-base">
                    {t('form.activity')}
                  </Label>
                  <select
                    id={`${id}-activity-${i}-type`}
                    className={SELECT}
                    value={preset?.id ?? 'template'}
                    onChange={(e) => {
                      const chosen = options.activities.find((a) => a.id === e.target.value)
                      if (chosen) setActivity(i, { label: chosen.label, mets: chosen.mets })
                    }}
                  >
                    {!preset && <option value="template">{activity.label}</option>}
                    {options.activities.map((a) => (
                      <option key={a.id} value={a.id}>
                        {t(`form.activities.${a.id}`, { defaultValue: a.label })}
                      </option>
                    ))}
                  </select>
                </div>
                <RemoveButton
                  label={t('form.removeActivity', { number: i + 1 })}
                  onClick={() => set({ activities: plan.activities.filter((_, k) => k !== i) })}
                />
              </div>
              <div className="grid gap-3">
                <DateTimeField
                  label={t('form.activityStart')}
                  context={activity.label}
                  value={activity.start}
                  planDate={plan.date}
                  onChange={(v) => setActivity(i, { start: v })}
                />
                <DateTimeField
                  label={t('form.activityEnd')}
                  context={activity.label}
                  value={activity.end}
                  planDate={plan.date}
                  invalid={activity.end <= activity.start}
                  onChange={(v) => setActivity(i, { end: v })}
                />
              </div>
              <p className="text-muted-foreground">
                {t('form.intensity', { mets: formatNumber(activity.mets, language, 1) })}
              </p>
              {activity.end <= activity.start && (
                <p role="alert" className="text-destructive">
                  {t('form.problems.activityEnd')}
                </p>
              )}
            </fieldset>
          )
        })}
      </Group>
    </form>
  )
}
