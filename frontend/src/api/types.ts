// The shapes of the answers from the Rozmarra API (docs/techstack.md, Section 10).

export type RiskWord = 'Low' | 'Moderate' | 'High'
export type IdfDarCategory = 'low' | 'moderate' | 'high'
export type PlanStatus = 'not_started' | 'draft' | 'approved'

export interface Chance {
  value: number
  percent: number
  word: RiskWord
}

export interface PatientRow {
  patient_id: string
  label: string
  name: string
  age: number
  source: string
  fast: string
  template_id: string
  fast_date: string
  fast_date_text: string
  idf_dar_total: number
  idf_dar_category: IdfDarCategory
  chance_of_low_during_fast: Chance
  dehydration_caution: boolean
  plan_status: PlanStatus
}

export interface ScheduledDose {
  time: string
  dose: number
  unit: string
}

export interface RecordMedicine {
  name: string
  display: string
  display_name_hi: string
  schedule: ScheduledDose[]
}

export interface PatientDetail {
  patient_id: string
  source: string
  label: string
  name: string
  age: number
  sex: 'female' | 'male'
  city: string
  language: string
  fast_word: string
  fasts_kept: string[]
  occupation: string
  years_with_diabetes: number
  hba1c_percent: number
  fasting_glucose_mg_dl: number
  egfr: number
  creatinine_mg_dl: number
  weight_kg: number
  height_cm: number
  bmi: number
  blood_pressure: string
  resting_heart_rate: number
  conditions: {
    hypertension: boolean
    chronic_kidney_disease: boolean
    heart_disease: string
  }
  medicines: RecordMedicine[]
  cyp2c9: {
    genotype: string
    activity_score: number
    clearance_factor: number
    sentence: string
  }
  planned_fast: {
    template_id: string
    date: string
    date_text: string
    note: string
  }
  data_sources: string[]
}

export interface IdfDarItem {
  key: string
  label: string
  points: number
  max_points: number
  detail: string
}

export interface IdfDar {
  patient_id: string
  total: number
  category: IdfDarCategory
  range: [number, number]
  missing: string[]
  items: IdfDarItem[]
  note: string | null
}

export interface TwinParameter {
  name: string
  label: string
  value: number
  log_sd: number
}

export interface Twin {
  patient_id: string
  donor: { patient_id: string | null; dataset: string | null; source: string }
  parameters: TwinParameter[]
  fixed: Record<string, number>
  fit_quality: {
    held_out_rmse_mg_dl: number | null
    held_out_mard_percent: number | null
    two_hour_forecast_rmse_mg_dl: number | null
    sentence: string | null
  }
}

export interface Signal {
  unit: string
  times: string[]
  values: (number | null)[]
}

export interface TimeseriesEvent {
  type: 'meal' | 'medicine' | 'insulin' | 'activity' | 'fast'
  start: string
  end: string
  details: Record<string, unknown>
}

export interface Timeseries {
  patient_id: string
  source: string
  signals: Record<string, Signal>
  events: TimeseriesEvent[]
}

export interface HistoryDay {
  date: string
  date_text: string
  glucose_readings: number
  mean_glucose_mg_dl: number | null
  lowest_glucose_mg_dl: number | null
  time_in_range_percent: number | null
  time_below_70_percent: number | null
  steps: number | null
  mean_heart_rate: number | null
  sleep_hours: number
}

export interface History {
  patient_id: string
  source: string
  start: string
  end: string
  days: HistoryDay[]
  summary: {
    days: number
    mean_glucose_mg_dl: number | null
    time_in_range_percent: number | null
    time_below_70_percent: number | null
    mean_daily_steps: number | null
    mean_sleep_hours: number
  }
}

export interface FastTemplate {
  id: string
  fast_type: string
  name: string
  name_hi: string
  short_name: string
  word_hi: string
  description: string
  water_allowed: boolean
  glucose_notes: string
}

export type FoodCategory = 'fast_absorbing' | 'mixed' | 'slow_absorbing'

export interface PlannedMeal {
  time: string
  label: string
  label_hi: string
  food_category: FoodCategory
  carbs_g: number
  breaks_fast: boolean
}

export interface PlannedMedicine {
  name: string
  dose: number
  time: string
  usual_dose: number | null
  usual_time: string | null
}

export interface PlannedActivity {
  start: string
  end: string
  label: string
  mets: number
}

export interface FastingPlan {
  patient_id: string
  plan_name: string
  template_id: string
  fast_type: string
  date: string
  city: string
  fast_start: string
  fast_end: string
  water_allowed: boolean
  meals: PlannedMeal[]
  medicines: PlannedMedicine[]
  activities: PlannedActivity[]
  status: 'draft' | 'approved'
  approved_by: string | null
  approved_on: string | null
  approved_contact?: string | null
  notes: string[]
}

export interface SavedPlans {
  status: PlanStatus
  plans: Record<string, FastingPlan>
}

export interface MedicineOption {
  name: string
  display_name: string
  display_name_hi: string
  medicine_class: string
  for_diabetes: boolean
  unit: string
  standard_dose: number
  max_single_dose: number
}

export interface PlanOptions {
  medicines: MedicineOption[]
  food_categories: { id: FoodCategory; label: string }[]
  activities: { id: string; label: string; mets: number; minutes: number }[]
}

export interface SimulationMarkers {
  fast: { start: string; end: string; water_allowed: boolean; hours: number }
  meals: {
    time: string
    label: string
    label_hi: string
    carbs_g: number
    food_category: FoodCategory
    breaks_fast: boolean
  }[]
  medicines: {
    time: string
    name: string
    display_name: string
    display_name_hi: string
    dose: number
    unit: string
    usual_dose: number | null
    changed: boolean
  }[]
  activities: { start: string; end: string; label: string; mets: number }[]
}

export interface Simulation {
  patient_id: string
  source: string
  plan: FastingPlan
  curve: {
    times: string[]
    p10: (number | null)[]
    p50: (number | null)[]
    p90: (number | null)[]
    most_likely: (number | null)[]
    average_patient: (number | null)[] | null
    samples: number
  }
  markers: SimulationMarkers
  summary: {
    chance_of_low_during_fast: Chance
    lowest_glucose_mg_dl: number
    lowest_glucose_time: string | null
    lowest_glucose_time_text: string | null
    expected_minutes_below_70: number
    chance_of_high_after_fast: Chance | null
  }
  dehydration_caution: { title: string; message: string; reasons: string[] } | null
  idf_dar: { total: number; category: IdfDarCategory }
  notes: string[]
}

export interface Comparison {
  plan_a: Simulation
  plan_b: Simulation
}

export interface ApprovalResult {
  plan: FastingPlan
  approval_text: string
}

export interface ReplayAlert {
  time: string
  chance: Chance
}

export interface ReplayOverview {
  fast_start: string
  fast_end: string
  times: string[]
  chances: number[]
  enough_data: boolean[]
  alert_threshold: number
  alerts: ReplayAlert[]
}

export interface Reason {
  feature: string
  contribution: number
  en: string
  hi: string
}

export interface ReplayMoment {
  patient_id: string
  source: string
  time: string
  time_text: string
  enough_data: boolean
  glucose: { times: string[]; values: (number | null)[] }
  heart_rate: { times: string[]; values: (number | null)[] }
  hrv_rmssd: { times: string[]; values: (number | null)[] }
  steps: { times: string[]; values: (number | null)[] }
  alerts_so_far: ReplayAlert[]
  message?: string
  chance_of_low_next_60_min?: Chance
  alert?: boolean
  above_alert_threshold?: boolean
  forecast?: {
    times: string[]
    p10: (number | null)[]
    p50: (number | null)[]
    p90: (number | null)[]
  }
  predicted_lowest_mg_dl?: number
  predicted_lowest_time?: string
  predicted_lowest_time_text?: string
  reasons?: Reason[]
}

export interface Metric {
  auroc?: number
  auprc?: number
  confidence_intervals_95?: { auroc?: [number, number]; auprc?: [number, number] }
}

export interface ThresholdResult {
  threshold: number
  event_sensitivity: number
  median_warning_minutes: number
  false_alerts_per_patient_day: number
}

export interface ModelCard {
  metrics: {
    created_on: string
    notes: string[]
    synthetic: {
      e1: Metric & {
        patients: number
        thresholds: { sensitivity_80: ThresholdResult; balanced: ThresholdResult }
        baselines: Record<string, Metric>
        ablation: Record<string, Metric>
      }
      e2: Metric & { baselines: Record<string, Metric> }
      f1: {
        f1_low: Metric & { twin_alone: Metric; idf_dar_alone: Metric }
        f1_high: Metric
      }
    }
    real: {
      e1: {
        all: Metric & { patients: number }
        baselines: Record<string, Metric>
        ablation: Record<string, Metric>
      }
      e2?: Metric & { meals: number; patients: number; baselines: Record<string, Metric> }
    }
  }
  twin_fit: {
    patients_fitted: number
    median_rmse_mg_dl: { fitted_days: number; held_out_days: number }
    median_forecast_rmse_mg_dl: Record<string, { twin: number; last_value: number }>
  } | null
  synthetic_cohort: {
    virtual_patients: number
    fasting_episodes: number
    episodes_with_low_blood_sugar: { share_with_low_blood_sugar: number }
  } | null
  data_sources: { id: string; name: string; type: string; licence: string; use: string }[]
  limitations: { id: string; text: string }[]
  notice: string
}
