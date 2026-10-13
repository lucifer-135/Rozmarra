# Rozmarra: Model Card

This model card describes how Rozmarra makes its estimates, which assumptions it uses, and how the team tests it. Section 5 reports the fit of the physiology twin on real open data, and Section 6 reports the results of the prediction models.

| Item | Details |
|---|---|
| Version | 0.6, updated on 13 October 2026 with the alert level chosen by events, the Parkes error grid and the check on real meals |
| Status | The clinical score, the safety rules, the physiology twin and the prediction models are built. |
| Intended use | A research prototype that supports a doctor who plans a religious fast with a patient who has Type 2 Diabetes. It is not a certified medical device, and it must not be used for real patients. |
| Clinical review | No doctor or pharmacist has reviewed the clinical content of this prototype. |

## 1. The three layers

Rozmarra will use three layers that work together (`docs/prd.md`, Section 13):

1. A personalised physiology twin, which will answer "what if" questions about a fasting plan.
2. Prediction models (LightGBM), which will estimate the chance of each adverse event.
3. The IDF-DAR 2021 risk score and simple safety rules, which are built now.

## 2. The IDF-DAR 2021 risk score

The calculator in `backend/src/rozmarra/risk/idf_dar.py` follows the IDF-DAR 2021 risk score table (`docs/techstack.md`, Section 9). Unit tests check the four demo patients and every boundary.

The calculator makes these assumptions:

- **Several treatments.** If a patient takes more than one treatment, the calculator uses the highest treatment score. The guideline asks for a single treatment type.
- **Medicines that the table does not name.** Ordinary gliclazide and gliquidone score like gliclazide MR (0.5 points). Rapid-acting or regular insulin together with basal insulin counts as basal-bolus insulin (2.5 points).
- **Boundaries.** HbA1c from 7.5% to 9.0% inclusive scores 1 point. An eGFR from 30 to 44 scores 4 points, from 45 to 59 scores 2 points, and 60 or above scores 0 points. Ten or more years with diabetes scores 1 point. Sixteen or more fasting hours scores 1 point.
- **Fasting hours.** Rozmarra uses the longest time between two meals in the plan, because this measure works for every type of fast, including fasts with fruit and milk.
- **Missing information.** The calculator never guesses. It marks each missing item, scores the available items, and reports the range of totals that the missing items could produce.
- **Other fasts.** The IDF-DAR score was designed for Ramadan. Rozmarra applies it to other fasts as an approximation, and the dashboard will say so.

## 3. The dehydration caution (C1)

The rule in `backend/src/rozmarra/risk/rules.py` shows a caution when a fast without water lasts 12 hours or more and at least one of these is true: the patient takes an SGLT2 inhibitor or a diuretic, the eGFR is below 60 mL/min/1.73 m², or the patient is older than 65 years. This rule is a caution, not a prediction. A clinical expert should review it.

## 4. Medicine assumptions

The medicine catalogue in `backend/src/rozmarra/medicines.py` holds these assumptions:

- **Activity curves.** The time to peak, half-life and maximum duration for glimepiride, gliclazide MR, glibenclamide, metformin, the SGLT2 inhibitors and sitagliptin come from `docs/techstack.md`, Section 5.3. The team added starting values for ordinary gliclazide (3 hours, 12 hours and 24 hours), gliquidone (2 hours, 1.5 hours and 10 hours) and repaglinide (1 hour, 1 hour and 6 hours). Vildagliptin, teneligliptin and linagliptin reuse the sitagliptin curve, and canagliflozin reuses the dapagliflozin curve. The team will check all of these values against pharmacology references.
- **Medicines that the twin will not model in this phase.** Acarbose and voglibose act in the gut, pioglitazone acts over weeks, and liraglutide is a weekly or daily injection with a different action. The twin will record these medicines but will not model their effects.
- **Premixed insulin.** Each dose of premixed human insulin 30/70 is split into 30% regular insulin and 70% NPH insulin. Premixed 40/60 uses 40% and 60%. Biphasic insulin aspart 30 and 50 use 30% and 50% rapid-acting insulin, and the rest follows the NPH profile.
- **CYP2C9.** The clearance factor is c_cyp = 0.3 + 0.35 × the CPIC activity score, so \*1/\*1 gives 1.0, \*1/\*3 gives 0.65 and \*3/\*3 gives 0.3. The twin will divide the sulfonylurea half-life and maximum duration by this factor. This mapping is a modelling assumption.

## 5. The physiology twin

The twin in `backend/src/rozmarra/twin/` follows the equations in `docs/techstack.md`, Section 5.2.

### 5.1 Changes to the starting design

- **Inputs calculated in advance.** Glucose does not affect meal absorption, insulin absorption or the medicine activity curves. Rozmarra therefore calculates these inputs exactly in advance, and the solver integrates only plasma glucose, insulin action and plasma insulin. The results are the same as with the full set of states, and the simulation is much faster.
- **Liver term.** The model adds the term k_hgp × (I − I_b) for the direct effect of insulin on glucose production by the liver, with k_hgp = 0.02 mg/dL per minute per µU/mL. `docs/techstack.md`, Section 5.4, suggested this term, because the first check found that basal insulin had too weak an effect.
- **Calibration of liver glucose production.** P0 is calibrated so that glucose does not change at the fasting level on a usual morning, with the medicine levels of the usual plan. A plan that changes a dose on the day of the fast is therefore compared with the same patient, not with a different patient. A test in the code checks this case.
- **Meal categories for CGMacros.** CGMacros records the nutrients of each meal. Rozmarra treats a meal as fast-absorbing when fat, protein and twice the fibre add up to less than 0.3 times the carbohydrates, and as slow-absorbing when they add up to more than the carbohydrates. This rule is an assumption. ShanghaiT2DM meals count as mixed meals.
- **Missing meal sizes.** A ShanghaiT2DM meal without a carbohydrate estimate counts as the median of the patient's estimated meals, or 40 g when fewer than three estimates exist.

### 5.2 Fitting

The fit follows `docs/techstack.md`, Section 5.6:

- The first 70% of each patient's days are used for fitting, and the last 30% are held back.
- The fit works in 12-hour windows that start at 6:00 am and 6:00 pm with the trend-matched start.
- The squared error is multiplied by 3 for missed low and high readings, and slope errors have the same weight.
- Log-normal priors keep the parameters close to the population values. The typical size of an error of the model and the sensor is set to 15 mg/dL.
- The parameter uncertainty comes from the Jacobian of the fit (a Laplace approximation). The uncertainty of a parameter is never larger than its prior uncertainty.

The fit used 89 real patients: 75 ShanghaiT2DM recording periods without an insulin pump or intravenous insulin, and the 14 CGMacros participants with Type 2 Diabetes. The CGMacros files contain no medicine records, so their twins do not model medicines.

**Two fitting rounds.** The first round on 12 October 2026 used the starting values and ranges in `docs/techstack.md`, Section 5.3. Many twins reached a limit of their range. For example, 16 of the 18 twins whose patients take a sulfonylurea reached the lowest allowed sulfonylurea effect, and the meal-size factor reached its lowest value for 40 of 89 twins, including 10 of the 14 CGMacros twins with recorded carbohydrates. The second round therefore uses population values close to the first-round medians and wider ranges:

| Parameter | Population value | Range |
|---|---|---|
| S_G | 0.015 per minute | 0.003 to 0.05 |
| S_I | 3 × 10⁻⁴ per minute per µU/mL | 0.2 × 10⁻⁴ to 15 × 10⁻⁴ |
| β | 0.02 µU/mL per minute per mg/dL | 0.002 to 0.2 |
| Meal absorption factor | 0.8 | 0.3 to 2.0 |
| Meal-size factor | 0.7 | 0.3 to 2.0 |
| Sulfonylurea effect γ_su | 3 µU/mL per minute | 0.5 to 15 |

The first round used only each patient's fitting days, so the held-out days stayed untouched. The population values do, however, use information from all 89 patients. Even after the second round, some twins still reach a limit, which shows that the model cannot capture every patient's pattern.

### 5.3 Results of the fit on real open data

These results come from `reports/twin_fit/summary.json`, which the command `rozmarra twin fit` wrote on 12 October 2026. Figures are in `reports/figures/twin_fit_summary.png`.

| Measure | Fitted days | Held-out days |
|---|---|---|
| Median RMSE in 12-hour windows | 29.7 mg/dL | 32.5 mg/dL |
| Median MARD in 12-hour windows | 18.0% | 19.2% |

The median RMSE on held-out days was 32.1 mg/dL for ShanghaiT2DM and 39.7 mg/dL for CGMacros. The T2DSim AI repository reports a median validation RMSE of about 29 mg/dL for its 40 twins. That value comes from a different method and different patients, so it is a reference point, not a direct comparison.

Forecasts on held-out days start from the measured CGM value with the trend-matched start, and they use the meals and doses recorded in the data:

| Horizon | Twin | Last value | Straight line | Patients where the twin beats the last value |
|---|---|---|---|---|
| 30 minutes | 14.5 mg/dL | 16.0 mg/dL | 19.3 mg/dL | 68 of 89 |
| 60 minutes | 23.9 mg/dL | 26.8 mg/dL | 37.6 mg/dL | 63 of 89 |
| 120 minutes | 30.2 mg/dL | 38.8 mg/dL | 68.6 mg/dL | 72 of 89 |

**Parkes error grid.** The command `rozmarra twin parkes` sorts each forecast into the zones of the Parkes consensus error grid for Type 2 Diabetes (Pfützner and colleagues, 2013). The team wrote the code from the published zone boundaries. The measured CGM value is the reference, and all forecasts of all patients are pooled. The figure is `reports/figures/parkes_30min.png`.

| Horizon | Forecast | Zone A | Zones A and B | Target in docs/prd.md |
|---|---|---|---|---|
| 30 minutes | Twin | 97.2% | 99.97% of 6,301 forecasts | 95% or more in zones A and B: met |
| 30 minutes | Last value | 95.5% | 99.98% | Reported |
| 120 minutes | Twin | 85.4% | 98.9% | Reported |
| 120 minutes | Last value | 75.5% | 98.2% | Reported |

No forecast fell in zone D or E at 30 minutes. Glucose changes little in 30 minutes, so the last value also meets the target. The share in zone A and the longer horizons show the differences between the forecasts more clearly.

The held-out days contain 69 12-hour windows with at least one reading below 70 mg/dL. The twin shows a value below 70 mg/dL in 14 of them. As in the T2DSim AI review, a twin alone can miss low blood sugar, so the alert model will also use the CGM readings directly.

### 5.4 The two weak points from the first check

With the median fitted parameters:

- **Large sweet meals.** A 110 g fast-absorbing meal after a 15-hour fast now peaks at about 299 mg/dL, compared with about 404 mg/dL with the starting values. A 60 g mixed meal raises glucose by about 77 mg/dL. Real CGMacros meals of 40 to 79 g raised glucose by a median of 85 mg/dL. Real meals of 80 g or more raised it by a median of 67 mg/dL, with a 90th percentile of 129 mg/dL. The rise after a large sweet meal (about 159 mg/dL) may therefore still be somewhat high.
- **Basal insulin.** Omitting one 18-unit dose of glargine now raises glucose by about 52 mg/dL a day later, compared with about 13 mg/dL with the starting values.

### 5.5 The sulfonylurea effect

The real data identifies the sulfonylurea effect poorly. The 18 ShanghaiT2DM patients with a sulfonylurea mostly take gliclazide, often together with insulin, and many of them were in hospital. Their fitted effect is small: the median γ_su is 0.5, the lowest allowed value. With that value, halving the glimepiride dose on a day without food raises the lowest glucose by only about 2 mg/dL in a test case. With the population value of 3, it raises the lowest glucose by about 7 mg/dL.

**Decision of 12 October 2026.** Clinical studies show that sulfonylureas cause low blood sugar during fasting. Virtual patients and demo patients therefore use the population value γ_su = 3 as their estimate, and their true value is drawn around it with a log-scale standard deviation of 0.5. The evaluation will repeat the analysis with the weaker fitted values. Even with γ_su = 3, the twin's sulfonylurea effect is modest: in the synthetic cohort, sulfonylurea users without insulin had low blood sugar in about the same share of fasting episodes as patients on neither medicine (data card, Section 7.6).

### 5.6 Simulating a fasting plan

A plan simulation starts one usual day before the plan, with the patient's usual medicines and a usual Indian meal routine of 50 g, 70 g, 20 g and 70 g of carbohydrate at 8:30 am, 1:30 pm, 5:00 pm and 8:30 pm. This routine is a starting value. The simulation draws 100 parameter samples to create the band from the 10th to the 90th percentile, and the first sample is always the most likely twin. The average-patient curve uses the median parameters of the fitted twins with the patient's own fasting glucose, body weight, kidney function, medicines and plan.

On the team's Windows laptop, one Karva Chauth day with 100 samples, the average patient and the usual day before it took a median of 0.66 seconds over five runs. The target is less than 1 second.

In the fasting plan simulator of the dashboard, the doctor can add four activities. Their intensities are approximate values from the Compendium of Physical Activities (Ainsworth and colleagues, 2011): walking at an ordinary pace at 3.5 METs, brisk walking at 4.3 METs, household work at 2.5 METs, and garba or dandiya dancing at 5.0 METs. The garba value matches the Navratri template.

Rozmarra does not simulate a plan in three cases: a dose is above the largest single dose in the medicine catalogue, the fast ends before it starts, or the plan covers more than 60 hours. The dashboard explains the problem to the doctor instead. These limits catch typing errors. They are not clinical dose limits.

The doctor's tested plans are saved as drafts. A patient has at most one approved plan. If the doctor approves another plan, the first plan becomes a draft again, and if the doctor changes an approved plan, the plan loses its approval.

### 5.7 Virtual patients

Each virtual patient joins a synthetic health record with the twin of a real donor patient (data card, Section 7.1). The "true" parameters generate the synthetic data, and the prediction models will use only the "estimated" parameters, because a real twin is only an estimate of the patient. The synthetic data also contains variation that the estimated twin does not know, such as unrecorded snacks and a slowly varying glucose disturbance. Results on simulated fasting days will still partly reflect the team's modelling assumptions.

The Kalman filter (FR-B8, a Should item) is not built. Every forecast uses the trend-matched start.

## 6. The prediction models

The results in this section come from `reports/metrics.json`, which the command `rozmarra model evaluate` wrote on 13 October 2026. The synthetic results partly reflect the team's modelling assumptions, because the same kind of twin that generated the synthetic data also provides some of the features.

### 6.1 Design

- **Targets.** E1 is low blood sugar within 60 minutes (Must), E1 within 120 minutes and E3 is glucose above 300 mg/dL within 60 minutes (both Should), and E2 is high blood sugar within 4 hours after the meal that breaks the fast, predicted 2 hours before the meal (Must). F1 is the whole-fast forecast (Must, Section 6.5).
- **Features.** The features cover CGM (the current value, changes, slope, lowest value, variability and missing readings), CGM history over 7 and 14 days, twin forecasts from the trend-matched start, wearables (heart rate against its usual level at that time of day, heart rate variability, steps, METs and sleep), the fasting context and the health record. The twin forecasts use only the estimated twin and the logged meals and doses.
- **Training.** Each model is a LightGBM classifier with 300 trees and a learning rate of 0.05. A comparison on the validation patients of the training group (never the test group) showed better results than the starting settings with stronger regularisation (15 leaves, at least 200 time points in each leaf, 60% of the features for each tree and an L2 penalty of 5) and with one extra feature, the twin's lowest forecast value in the next 60 minutes. On real data, the model leaves out the health record, because the real records are sparse and constant for each patient, and the same comparison showed better results without them.
- **Calibration and alerts.** Isotonic regression on the validation patients calibrates the chances. One millionth of the raw score breaks ties between time points in the same calibration step. An alert is not repeated within 30 minutes unless the chance rises by 10 percentage points (FR-C7). The evaluation and the live fasting monitor use the same alert rules (`backend/src/rozmarra/ml/alerts.py`).
- **Alert levels.** Alert threshold A is the highest level at which the alerts detect at least 80% of the low blood sugar events of the validation patients, as `docs/prd.md`, Section 15.2, describes. An event counts as detected when at least one alert falls in the hour before it. Threshold B is the point where sensitivity equals specificity. Before 13 October 2026, threshold A detected 80% of the positive time points instead of 80% of the events, and the evaluation did not repeat an alert after a rise of 10 percentage points. That older level was a chance of about 3.5%, and it gave 2.5 false alerts per patient per fasting day with a median warning of 30 minutes.
- **The search for a better alert rule.** On the validation patients, the team compared longer pauses between alerts (30 to 120 minutes), alerts that need two or three time points in a row above the level, and many alert levels. No rule met all three alert targets at once: at least 80% of events detected, at most 2 false alerts per patient per fasting day and a median warning of at least 30 minutes. A rule with fewer false alerts gave a shorter warning, and a rule with a longer warning gave more false alerts.
- **Risk words.** For the plan forecasts, a chance below 20% is Low, 20% to 50% is Moderate, and above 50% is High. Low blood sugar within 60 minutes is rare, so threshold A is a small chance (about 8.9%). For the 60-minute alert, the words are therefore tied to the alert level: below threshold A is Low, from threshold A to 20% is Moderate, and 20% or more is High. A clinical expert should review both sets of words.
- **Data completeness.** A prediction needs a current CGM reading and at least 70% of the expected readings in the last 2 hours. Otherwise, the dashboard shows the message in FR-C8.
- **Reasons.** The SHAP TreeExplainer finds the features that raised the chance the most. Each becomes a sentence from a fixed English and Hindi template, with at most one sentence from each group of similar features, such as the twin forecasts.

### 6.2 How the team tested the models

- **Synthetic fasting days.** The models learned on the 400 training virtual patients and were tested on the 100 test virtual patients, whose donor twins come only from the real test group.
- **Real normal days.** Five-fold cross-validation grouped by person, on the 89 real patients with a fitted twin. Each fold was tested only on the held-out days of its patients, on which the twins were not fitted. The real data contains no fasting days.
- **Real meals.** The E2 model, trained only on synthetic fasting days, was applied without retraining to real meals after a night without food on the held-out days (Section 6.4).
- **Intervals.** 95% intervals come from 1,000 bootstrap samples drawn by patient for the main results, and 200 for the baselines and the ablation study.

### 6.3 Low blood sugar 60 minutes ahead (E1) on synthetic fasting days

The test group had 71,141 usable time points from 100 patients, with 717 positive time points and 116 low blood sugar events.

| Measure | Result | Target in docs/prd.md |
|---|---|---|
| AUROC | 0.990 (95% interval 0.984 to 0.994) | 0.85 or higher: met |
| AUPRC | 0.472 (0.372 to 0.590) | Not set |
| Brier score | 0.0069 (0.004 to 0.011) | Reported |
| Events detected in time at threshold A | 88% (84% to 95%), 102 of 116 events | At least 80%: met |
| False alerts at threshold A | 1.9 per patient per fasting day (1.1 to 2.9) | At most 2: met |
| Median warning time at threshold A | 25 minutes | At least 30 minutes: not met |
| Threshold B | 89% of events detected, 5.1 false alerts per patient per fasting day, median warning 25 minutes | Reported |

Threshold A is a chance of about 8.9%. It lies exactly on one step of the calibration, so a small change in the level can change the alert results noticeably. The interval for false alerts still reaches above 2, so the target is met by the estimate but not with certainty.

**At 54 mg/dL.** Against low blood sugar below 54 mg/dL, the same model reached an AUROC of 0.987 (0.979 to 0.995) and an AUPRC of 0.189 (0.100 to 0.342). At threshold A, it detected 44 of 54 severe events (81%) with a median warning of 22.5 minutes.

**Baselines and ablation (AUROC and AUPRC).**

| Model | AUROC | AUPRC |
|---|---|---|
| Full model (all streams) | 0.990 | 0.472 |
| Twin alone | 0.989 | 0.554 (0.425 to 0.658) |
| Model with CGM data only | 0.979 | 0.386 |
| CGM and wearables | 0.977 | 0.381 |
| Last glucose value | 0.944 | 0.279 |
| Straight-line trend | 0.921 | 0.198 |
| Health record alone | 0.772 | 0.028 |
| IDF-DAR score alone | 0.732 | 0.024 |
| Wearables alone | 0.615 | 0.056 |

The full model has a higher AUPRC than every model that uses a single data stream, which meets the target in `docs/prd.md`, Section 15.3. On the test patients, however, the twin alone reached a higher AUPRC than the full model, and the two intervals overlap. On the validation patients, the full model was slightly better than the twin alone. Because the twin also generated the synthetic data, the strength of the twin on synthetic data is partly circular.

**Subgroups (threshold A).** The share of events detected in time was 88% for patients on insulin (94 events), 85% for patients on a sulfonylurea without insulin (20 events), 86% for patients aged 65 or over (22 events), 84% for women (69 events) and 94% for men (47 events). Patients on insulin had 3.8 false alerts per patient per fasting day, and patients on a sulfonylurea without insulin had 1.6. No test patient had an eGFR below 60, so that subgroup has no result.

**Should targets.** E1 120 minutes ahead reached an AUROC of 0.986 and an AUPRC of 0.588, with 88% of events detected in time and 6.6 false alerts per patient per fasting day. E3 reached an AUROC of 0.995 and an AUPRC of 0.619, with 71% of events detected in time.

### 6.4 High blood sugar after the fast (E2) on synthetic fasting days

The test group had 288 meals that break a fast, and 149 of them were followed by E2. E2 is common because the meals that break a fast are large and often sweet.

| Measure | Result |
|---|---|
| AUROC | 0.958 (0.931 to 0.979). The target is 0.80 or higher: met. |
| AUPRC | 0.954 (0.916 to 0.981) |
| Threshold A | Sensitivity 74%, specificity 96% |
| Threshold B | Sensitivity 89%, specificity 91% |
| Twin peak alone | AUROC 0.970 |
| Planned carbohydrates alone | AUROC 0.706 |
| Glucose 2 hours before the meal | AUROC 0.673 |

As for E1, the twin's predicted peak alone did slightly better than the full model on synthetic data.

**Check on real meals.** The real data contains no festival fasts. The closest real case is the first meal after a night without food, usually breakfast. The team applied the E2 model, which learned only on synthetic fasting days, to real meals without retraining it. Each meal came after at least 8 hours without food, contained at least 20 g of carbohydrate and fell on a held-out day, on which the patient's twin was not fitted. The check covered 244 meals of 86 patients (217 meals from ShanghaiT2DM and 27 from CGMacros), and 34 of them were followed by E2.

| Measure | Result |
|---|---|
| AUROC | 0.828 (0.725 to 0.903) |
| AUPRC | 0.410 (0.253 to 0.600) |
| Brier score | 0.119 |
| Threshold A | Sensitivity 38%, specificity 93% |
| Threshold B | Sensitivity 47%, specificity 91% |
| Glucose 2 hours before the meal alone | AUROC 0.865 (0.779 to 0.930) |
| Twin peak alone | AUROC 0.821 (0.712 to 0.905) |
| Planned carbohydrates alone | AUROC 0.550 (0.412 to 0.696) |

On real meals, the glucose value 2 hours before the meal alone did slightly better than the model, and the intervals overlap. The model overestimated the chance for the meals it rated highest: their average estimated chance was 70%, and 43% of them were followed by E2. The thresholds, which were chosen on synthetic meals, found fewer than half of the real E2 meals. These meals end a night without food, not a festival fast, so the check shows how the model behaves on real glucose data, not how it would behave after a real fast.

### 6.5 The whole-fast forecast (F1)

Before the fast, the estimated twin simulates the plan with 30 parameter samples. A logistic regression combines the twin's view with the CGM history of the 14 days before the fast and the health record (`backend/src/rozmarra/ml/episodes.py`). It was tested on the 300 fasting episodes of the 100 test virtual patients.

| Forecast | AUROC | AUPRC | Twin alone (AUROC) |
|---|---|---|---|
| Low blood sugar during the fast (36 episodes with an event) | 0.973 (0.945 to 0.992) | 0.877 | 0.815 |
| High blood sugar after the fast (155 episodes with an event) | 0.972 (0.954 to 0.986) | 0.975 | 0.942 |

The IDF-DAR score alone reached an AUROC of 0.750 for low blood sugar during the fast. The twin's predicted peak is capped at 600 mg/dL, because a few twins with extreme fitted parameters predicted peaks above 1,000 mg/dL, which is not physiological.

### 6.6 Low blood sugar 60 minutes ahead (E1) on real normal days

The held-out days had 30,896 usable time points from 89 patients, with 337 positive time points.

| Measure | Result | Target |
|---|---|---|
| AUROC | 0.943 (0.919 to 0.964) | 0.80 or higher: met |
| AUPRC | 0.247 (0.121 to 0.382) | Not set |
| Brier score | 0.0094 | Reported |
| ShanghaiT2DM at threshold A | 61 of 77 events detected in time (79%), median warning 45 minutes, 1.6 false alerts per patient per day | Reported |
| CGMacros at threshold A | 2 of 3 events detected in time, median warning 22.5 minutes, 0.2 false alerts per patient per day | Reported |
| At 54 mg/dL | AUROC 0.935 (0.839 to 0.984), 28 positive time points | Reported |

On real data, the model with CGM data only reached a higher AUPRC (0.311) than the full model (0.247), and the model with CGM and wearables reached 0.278. The real data therefore does not show that combining the data streams adds value. Only the 14 CGMacros participants have smartwatch data, and they had very few low readings. The twin alone reached an AUROC of 0.928 and an AUPRC of 0.232, and the last glucose value reached 0.917 and 0.144.

### 6.7 Sensitivity analysis with the weaker sulfonylurea effect

The command `rozmarra model sensitivity` repeated the synthetic cohort and the E1 evaluation with the virtual patients' sulfonylurea effect centred on γ_su = 0.5, the median fitted on real data. Low blood sugar then occurred in 10.8% of the fasting episodes (11.4% in the main cohort), and in 7.0% of the episodes of sulfonylurea users without insulin (8.6% in the main cohort). The E1 model reached an AUROC of 0.989 (0.984 to 0.994) and an AUPRC of 0.477 (0.381 to 0.579), against 0.990 and 0.472 in the main analysis. At its own threshold A, it detected 95 of 117 events in time (81%), with 1.5 false alerts per patient per fasting day and a median warning of 25 minutes. The results therefore do not depend on the size of the sulfonylurea effect, which also shows that the twin's sulfonylurea effect is modest in both cohorts.

### 6.8 What these results mean

- The real-data results describe normal days in China and the United States, not fasting days in India.
- The synthetic results depend on the team's modelling assumptions. In particular, the twin generated the synthetic data, so twin features look stronger on synthetic data than they may be in real life.
- At threshold A, the model meets the targets for events detected and for false alerts on synthetic data, but its median warning of 25 minutes is shorter than the target of 30 minutes. No alert rule met all three alert targets on the validation patients. A clinical team would need to choose an alert level that balances missed events, false alerts and warning time.
- On real meals after a night without food, the E2 model ranked the meals reasonably well, but the glucose value before the meal alone ranked them slightly better, and the model overestimated the highest chances.
- The Kalman filter and the LSTM comparison are not done.

## 7. The live fasting monitor and the patient plan

### 7.1 The live fasting monitor

The live fasting monitor replays the recorded demo fasting day of each patient. At each 5-minute step, it shows only what the model knew at that moment: the glucose readings so far, the forecast of the twin for the next 2 hours with its band, and the estimated chance of low glucose within the next 60 minutes. The alerts follow the rules in Section 6.1, and each alert lists the three main reasons from SHAP. The monitor makes no prediction when there is no current CGM reading or when less than 70% of the readings of the last 2 hours are present. It then asks the doctor to check the sensor.

For the demonstration, the doctor can show the readings that came after the chosen moment. These readings are labelled clearly, and the model never uses them.

When the API starts, it prepares the simulations of the usual plans, the features of the recorded fasting days and the SHAP explainer in the background, which took about 7 seconds on the team's Windows laptop. After that, each request of the dashboard took less than 0.2 seconds, and testing two plans took about 1.3 seconds, within the target of 2 seconds for each screen.

### 7.2 The patient plan

The printable patient plan comes only from fixed Jinja2 templates in English and Hindi. Rozmarra fills in the patient's own facts: the name, the date, the patient's word for the fast, the times of the fast and the meals, the doses and the doctor's approval. The plan states each medicine with the name on the strip and the dose, for example "Glimepiride 1 mg", as `docs/prd.md`, Section 17.2, describes. A usual dose that the approved plan no longer contains appears as a dose that the doctor advised the patient not to take.

The plan asks the patient to check blood sugar at times that follow fixed rules:

1. During the fast, the first check is 2 hours after the fast starts, and one check follows every 3 hours.
2. One check is 1 hour before the fast ends.
3. One check is 30 minutes before the time at which the twin predicts the lowest glucose, when that time falls inside the fast.
4. One check is 2 hours after the meal that breaks the fast.

Checks from rules 1 to 3 fall only between 6:00 am and 10:00 pm. Each time is rounded to the nearest half hour, and when two checks are less than 75 minutes apart, only one stays, in the order of priority rule 4, rule 2, rule 3 and rule 1. The IDF-DAR 2021 guidelines recommend several checks on each day of Ramadan. These rules apply the same idea to every fast. A clinical expert should review them.

The plan always shows the rule for breaking the fast from the IDF-DAR 2021 guidelines: below 70 mg/dL or above 300 mg/dL, or when the patient feels unwell. The short message for SMS or WhatsApp is a concept only, and Rozmarra does not send any messages.

## 8. Ideas from other projects

Rozmarra uses several simple ideas from two published open-source projects. The team writes its own code for every idea, and the repository contains no code or trained models from either project.

- From T2DSim AI (Roquemen-Echeverri and Mosquera-Lopez, Oregon Health & Science University), Rozmarra takes medicine activity curves, a starting state that matches the CGM trend, fitting with safety weights and slope matching in 12-hour windows, and an average-patient curve in the simulator.
- From the Stanford hypoglycemia forecasting project (Giammarino and colleagues), Rozmarra takes a 70% data completeness rule, reporting at 54 mg/dL, recent CGM history features and a balanced alert threshold.

## 9. Limitations

- The real data comes from China and the United States, not from India.
- No open dataset contains CGM data from Indian festival fasts. The fasting results therefore come from simulated fasting days, which reflect the team's modelling assumptions.
- The thresholds, plan templates and medicine assumptions come from cited guidelines and studies, but no clinician has reviewed them.
- A real product would need clinical studies with Indian patients and approval as a medical device.
