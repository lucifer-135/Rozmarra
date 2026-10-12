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

## Low blood sugar

The held-out days contain 69 12-hour windows with at least one measured reading below 70 mg/dL. The twin shows a value below 70 mg/dL in 14 of them. A twin alone can therefore miss low blood sugar, which is why the alert model will also use the CGM readings directly.
