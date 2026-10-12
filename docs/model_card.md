# Rozmarra: Model Card

This model card describes how Rozmarra makes its estimates, which assumptions it uses, and how the team tests it. Section 5 reports the fit of the physiology twin on real open data. The team will add the results of the prediction models after the evaluation runs.

| Item | Details |
|---|---|
| Version | 0.2, updated on 12 October 2026 with the physiology twin |
| Status | The clinical score, the safety rules and the physiology twin are built. The prediction models are not built yet. |
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

The real data identifies the sulfonylurea effect poorly. The 18 ShanghaiT2DM patients with a sulfonylurea mostly take gliclazide, often together with insulin, and many of them were in hospital. Their fitted effect is small: the median γ_su is 0.5, the lowest allowed value. With that value, halving the glimepiride dose on a day without food raises the lowest glucose by only about 2 mg/dL in a test case. With the population value of 3, it raises the lowest glucose by about 7 mg/dL. The team will decide how the virtual patients handle this effect, and the decision will appear in this card.

### 5.6 Simulating a fasting plan

A plan simulation starts one usual day before the plan, with the patient's usual medicines and a usual Indian meal routine of 50 g, 70 g, 20 g and 70 g of carbohydrate at 8:30 am, 1:30 pm, 5:00 pm and 8:30 pm. This routine is a starting value. The simulation draws 100 parameter samples to create the band from the 10th to the 90th percentile, and the first sample is always the most likely twin. The average-patient curve uses the median parameters of the fitted twins with the patient's own fasting glucose, body weight, kidney function, medicines and plan.

On the team's Windows laptop, one Karva Chauth day with 100 samples, the average patient and the usual day before it took a median of 0.66 seconds over five runs. The target is less than 1 second.

## 6. The prediction models (planned)

The team will build the prediction models on 16 October 2026, as `docs/techstack.md`, Sections 6 to 8, describes. The team will then add these items to this card:

- the event rates in the synthetic fasting days;
- the results on real patients and on simulated fasting days, with 95% confidence intervals, baselines and the ablation study;
- the results for low blood sugar at 70 mg/dL and at 54 mg/dL, at two alert thresholds; and
- the subgroup results.

The team will report the measured values honestly, even if they fall short of the targets in `docs/prd.md`, Section 15.3.

## 7. Ideas from other projects

Rozmarra uses several simple ideas from two published open-source projects. The team writes its own code for every idea, and the repository contains no code or trained models from either project.

- From T2DSim AI (Roquemen-Echeverri and Mosquera-Lopez, Oregon Health & Science University), Rozmarra takes medicine activity curves, a starting state that matches the CGM trend, fitting with safety weights and slope matching in 12-hour windows, and an average-patient curve in the simulator.
- From the Stanford hypoglycemia forecasting project (Giammarino and colleagues), Rozmarra takes a 70% data completeness rule, reporting at 54 mg/dL, recent CGM history features and a balanced alert threshold.

## 8. Limitations

- The real data comes from China and the United States, not from India.
- No open dataset contains CGM data from Indian festival fasts. The fasting results will therefore come from simulated fasting days, which reflect the team's modelling assumptions.
- The thresholds, plan templates and medicine assumptions come from cited guidelines and studies, but no clinician has reviewed them.
- A real product would need clinical studies with Indian patients and approval as a medical device.
