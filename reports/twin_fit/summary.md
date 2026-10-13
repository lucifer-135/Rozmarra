# Twin fit report

This report describes how well each twin fits the real open data. All patients in this report come from the open datasets ShanghaiT2DM and CGMacros. The command `rozmarra twin fit` creates it.

The team fitted 89 twins. The first 70% of each patient's days were used for fitting, and the last 30% were held back. Each simulation runs in 12-hour windows that start from the measured CGM value.

| Measure | Fitted days | Held-out days |
|---|---|---|
| Median RMSE in 12-hour windows | 29.7 mg/dL | 32.5 mg/dL |
| Median MARD in 12-hour windows | 17.4% | 19.2% |

The T2DSim AI repository reports a median validation RMSE of about 29 mg/dL for its 40 trained twins. This value is a reference point from a different method and different patients, not a direct comparison.

## Forecasts on held-out days

Each forecast starts from the measured CGM value with the trend-matched start. The forecasts use the meals and doses recorded in the data, in the same way that a fasting plan provides them. The values are the median RMSE across patients.

| Horizon | Twin | Last value | Straight line | Patients where the twin beats the last value |
|---|---|---|---|---|
| 30 minutes | 14.5 mg/dL | 16.0 mg/dL | 19.3 mg/dL | 68 of 89 |
| 60 minutes | 23.9 mg/dL | 26.8 mg/dL | 37.6 mg/dL | 63 of 89 |
| 120 minutes | 30.2 mg/dL | 38.8 mg/dL | 68.6 mg/dL | 72 of 89 |

## Parkes error grid

The Parkes consensus error grid for Type 2 Diabetes (Pfützner and colleagues, 2013) sorts each forecast into zones A to E by its possible effect on a treatment decision. Zones A and B mean no effect or little effect on the outcome. The PRD target is 95% or more of the 30-minute forecasts in zones A and B. The values below pool all forecasts of all patients.

Glucose changes little in 30 minutes, so the simple baselines also meet this target. The share in zone A and the longer horizons show the differences between the forecasts more clearly.

| Horizon | Forecast | Pairs | Zone A | Zone B | Zone C | Zone D | Zone E | Zones A and B |
|---|---|---|---|---|---|---|---|---|
| 30 minutes | Twin | 6,301 | 97.18% | 2.79% | 0.03% | 0.00% | 0.00% | 99.97% |
| 30 minutes | Last value | 6,301 | 95.52% | 4.46% | 0.02% | 0.00% | 0.00% | 99.98% |
| 30 minutes | Straight line | 6,301 | 91.14% | 8.84% | 0.02% | 0.00% | 0.00% | 99.98% |
| 60 minutes | Twin | 6,299 | 91.98% | 7.84% | 0.17% | 0.00% | 0.00% | 99.83% |
| 60 minutes | Last value | 6,299 | 87.59% | 12.18% | 0.24% | 0.00% | 0.00% | 99.76% |
| 60 minutes | Straight line | 6,299 | 74.55% | 24.24% | 1.19% | 0.02% | 0.00% | 98.79% |
| 120 minutes | Twin | 6,298 | 85.36% | 13.58% | 1.06% | 0.00% | 0.00% | 98.94% |
| 120 minutes | Last value | 6,298 | 75.48% | 22.69% | 1.81% | 0.02% | 0.00% | 98.17% |
| 120 minutes | Straight line | 6,298 | 52.10% | 39.28% | 8.29% | 0.33% | 0.00% | 91.38% |

## Low blood sugar

The held-out days contain 69 12-hour windows with at least one measured reading below 70 mg/dL. The twin shows a value below 70 mg/dL in 14 of them. A twin alone can therefore miss low blood sugar, which is why the alert model will also use the CGM readings directly.
