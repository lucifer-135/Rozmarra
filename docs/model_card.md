# Rozmarra: Model Card

This model card describes how Rozmarra makes its estimates, which assumptions it uses, and how the team tests it. Section 5 reports the fit of the physiology twin on real open data, and Section 6 reports the results of the prediction models.

| Item | Details |
|---|---|
| Version | 0.3, updated on 13 October 2026 with the prediction models |
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

### 5.7 Virtual patients

Each virtual patient joins a synthetic health record with the twin of a real donor patient (data card, Section 7.1). The "true" parameters generate the synthetic data, and the prediction models will use only the "estimated" parameters, because a real twin is only an estimate of the patient. The synthetic data also contains variation that the estimated twin does not know, such as unrecorded snacks and a slowly varying glucose disturbance. Results on simulated fasting days will still partly reflect the team's modelling assumptions.

The Kalman filter (FR-B8, a Should item) is not built. Every forecast uses the trend-matched start.

## 6. The prediction models

The results in this section come from `reports/metrics.json`, which the command `rozmarra model evaluate` wrote on 13 October 2026. The synthetic results partly reflect the team's modelling assumptions, because the same kind of twin that generated the synthetic data also provides some of the features.

### 6.1 Design

- **Targets.** E1 is low blood sugar within 60 minutes (Must), E1 within 120 minutes and E3 is glucose above 300 mg/dL within 60 minutes (both Should), and E2 is high blood sugar within 4 hours after the meal that breaks the fast, predicted 2 hours before the meal (Must). F1 is the whole-fast forecast (Must, Section 6.5).
- **Features.** The features cover CGM (the current value, changes, slope, lowest value, variability and missing readings), CGM history over 7 and 14 days, twin forecasts from the trend-matched start, wearables (heart rate against its usual level at that time of day, heart rate variability, steps, METs and sleep), the fasting context and the health record. The twin forecasts use only the estimated twin and the logged meals and doses.
- **Training.** Each model is a LightGBM classifier with 300 trees and a learning rate of 0.05. A comparison on the validation patients of the training group (never the test group) showed better results than the starting settings with stronger regularisation (15 leaves, at least 200 time points in each leaf, 60% of the features for each tree and an L2 penalty of 5) and with one extra feature, the twin's lowest forecast value in the next 60 minutes. On real data, the model leaves out the health record, because the real records are sparse and constant for each patient, and the same comparison showed better results without them.
- **Calibration and alerts.** Isotonic regression on the validation patients calibrates the chances. One millionth of the raw score breaks ties between time points in the same calibration step. Alert threshold A detects 80% of the positive time points on the validation patients, and threshold B is the point where sensitivity equals specificity. An alert is not repeated within 30 minutes unless the chance rises by 10 percentage points (FR-C7).
- **Risk words.** For the plan forecasts, a chance below 20% is Low, 20% to 50% is Moderate, and above 50% is High. Low blood sugar within 60 minutes is rare, so threshold A is a small chance (about 3.5%). For the 60-minute alert, the words are therefore tied to the alert level: below threshold A is Low, from threshold A to 20% is Moderate, and 20% or more is High. A clinical expert should review both sets of words.
- **Data completeness.** A prediction needs a current CGM reading and at least 70% of the expected readings in the last 2 hours. Otherwise, the dashboard shows the message in FR-C8.
- **Reasons.** The SHAP TreeExplainer finds the features that raised the chance the most. Each becomes a sentence from a fixed English and Hindi template, with at most one sentence from each group of similar features, such as the twin forecasts.

### 6.2 How the team tested the models

- **Synthetic fasting days.** The models learned on the 400 training virtual patients and were tested on the 100 test virtual patients, whose donor twins come only from the real test group.
- **Real normal days.** Five-fold cross-validation grouped by person, on the 89 real patients with a fitted twin. Each fold was tested only on the held-out days of its patients, on which the twins were not fitted. The real data contains no fasting days.
- **Intervals.** 95% intervals come from 1,000 bootstrap samples drawn by patient for the main results, and 200 for the baselines and the ablation study.

### 6.3 Low blood sugar 60 minutes ahead (E1) on synthetic fasting days

The test group had 71,141 usable time points from 100 patients, with 717 positive time points and 116 low blood sugar events.

| Measure | Result | Target in docs/prd.md |
|---|---|---|
| AUROC | 0.990 (95% interval 0.984 to 0.994) | 0.85 or higher: met |
| AUPRC | 0.472 (0.372 to 0.590) | Not set |
| Brier score | 0.0069 (0.004 to 0.011) | Reported |
| Events detected in time at threshold A | 81% (75% to 91%), 94 of 116 events | At least 80%: met |
| False alerts at threshold A | 2.5 per patient per fasting day (1.6 to 3.6) | At most 2: not met |
| Median warning time at threshold A | 30 minutes | At least 30 minutes: met |
| Threshold B | 85% of events detected, 4.7 false alerts per patient per fasting day, median warning 25 minutes | Reported |

**At 54 mg/dL.** Against low blood sugar below 54 mg/dL, the same model reached an AUROC of 0.987 (0.979 to 0.995) and an AUPRC of 0.189 (0.100 to 0.342). At threshold A, it detected 43 of 54 severe events (80%) with a median warning of 20 minutes.

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

**Subgroups (threshold A).** The share of events detected in time was 82% for patients on insulin (94 events), 75% for patients on a sulfonylurea without insulin (20 events), 73% for patients aged 65 or over (22 events), 77% for women and 87% for men. Patients on insulin had 4.8 false alerts per patient per fasting day. No test patient had an eGFR below 60, so that subgroup has no result.

**Should targets.** E1 120 minutes ahead reached an AUROC of 0.986 and an AUPRC of 0.588, with 87% of events detected in time. E3 reached an AUROC of 0.995 and an AUPRC of 0.619, with 61% of events detected in time.

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

As for E1, the twin's predicted peak alone did slightly better than the full model on synthetic data. The check with real meals in `docs/prd.md`, Section 15.3, is not done.

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
| ShanghaiT2DM at threshold A | 75 of 77 events detected in time, median warning 45 minutes, 5.6 false alerts per patient per day | Reported |
| CGMacros at threshold A | 3 of 3 events detected in time, median warning 45 minutes, 0.5 false alerts per patient per day | Reported |
| At 54 mg/dL | AUROC 0.935 (0.839 to 0.984), 28 positive time points | Reported |

On real data, the model with CGM data only reached a higher AUPRC (0.311) than the full model (0.247), and the model with CGM and wearables reached 0.278. The real data therefore does not show that combining the data streams adds value. Only the 14 CGMacros participants have smartwatch data, and they had very few low readings. The twin alone reached an AUROC of 0.928 and an AUPRC of 0.232, and the last glucose value reached 0.917 and 0.144.

### 6.7 Sensitivity analysis with the weaker sulfonylurea effect

The command `rozmarra model sensitivity` repeated the synthetic cohort and the E1 evaluation with the virtual patients' sulfonylurea effect centred on γ_su = 0.5, the median fitted on real data. Low blood sugar then occurred in 10.8% of the fasting episodes (11.4% in the main cohort), and in 7.0% of the episodes of sulfonylurea users without insulin (8.6% in the main cohort). The E1 model reached an AUROC of 0.989 (0.984 to 0.994) and an AUPRC of 0.477 (0.381 to 0.579), against 0.990 and 0.472 in the main analysis. The results therefore do not depend on the size of the sulfonylurea effect, which also shows that the twin's sulfonylurea effect is modest in both cohorts.

### 6.8 What these results mean

- The real-data results describe normal days in China and the United States, not fasting days in India.
- The synthetic results depend on the team's modelling assumptions. In particular, the twin generated the synthetic data, so twin features look stronger on synthetic data than they may be in real life.
- The false alert rate at threshold A is above the target of 2 per patient per fasting day on synthetic data, and much higher on the 15-minute ShanghaiT2DM data. A clinical team would need to choose an alert level that balances missed events and false alerts.
- The Parkes error grid, the Kalman filter and the LSTM comparison are not done.

## 7. Ideas from other projects

Rozmarra uses several simple ideas from two published open-source projects. The team writes its own code for every idea, and the repository contains no code or trained models from either project.

- From T2DSim AI (Roquemen-Echeverri and Mosquera-Lopez, Oregon Health & Science University), Rozmarra takes medicine activity curves, a starting state that matches the CGM trend, fitting with safety weights and slope matching in 12-hour windows, and an average-patient curve in the simulator.
- From the Stanford hypoglycemia forecasting project (Giammarino and colleagues), Rozmarra takes a 70% data completeness rule, reporting at 54 mg/dL, recent CGM history features and a balanced alert threshold.

## 8. Limitations

- The real data comes from China and the United States, not from India.
- No open dataset contains CGM data from Indian festival fasts. The fasting results will therefore come from simulated fasting days, which reflect the team's modelling assumptions.
- The thresholds, plan templates and medicine assumptions come from cited guidelines and studies, but no clinician has reviewed them.
- A real product would need clinical studies with Indian patients and approval as a medical device.
