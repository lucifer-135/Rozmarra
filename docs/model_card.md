# Rozmarra: Model Card

This model card describes how Rozmarra makes its estimates, which assumptions it uses, and how the team will test it. The team will add the results after the evaluation runs. No model results exist yet.

| Item | Details |
|---|---|
| Version | 0.1, written on 12 October 2026 |
| Status | The clinical score and the safety rules are built. The physiology twin and the prediction models are not built yet. |
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

## 5. The physiology twin and the prediction models (planned)

The team will build the twin and the prediction models from 14 to 16 October 2026, as `docs/techstack.md`, Sections 5 to 8, describes. The team will then add these items to this card:

- the fit of each twin on real patients, with the RMSE and the mean absolute relative difference on held-out days;
- the event rates in the synthetic fasting days;
- the results on real patients and on simulated fasting days, with 95% confidence intervals, baselines and the ablation study;
- the results for low blood sugar at 70 mg/dL and at 54 mg/dL, at two alert thresholds; and
- the subgroup results.

The team will report the measured values honestly, even if they fall short of the targets in `docs/prd.md`, Section 15.3.

## 6. Ideas from other projects

Rozmarra uses several simple ideas from two published open-source projects. The team writes its own code for every idea, and the repository contains no code or trained models from either project.

- From T2DSim AI (Roquemen-Echeverri and Mosquera-Lopez, Oregon Health & Science University), Rozmarra takes medicine activity curves, a starting state that matches the CGM trend, fitting with safety weights and slope matching in 12-hour windows, and an average-patient curve in the simulator.
- From the Stanford hypoglycemia forecasting project (Giammarino and colleagues), Rozmarra takes a 70% data completeness rule, reporting at 54 mg/dL, recent CGM history features and a balanced alert threshold.

## 7. Limitations

- The real data comes from China and the United States, not from India.
- No open dataset contains CGM data from Indian festival fasts. The fasting results will therefore come from simulated fasting days, which reflect the team's modelling assumptions.
- The thresholds, plan templates and medicine assumptions come from cited guidelines and studies, but no clinician has reviewed them.
- A real product would need clinical studies with Indian patients and approval as a medical device.
