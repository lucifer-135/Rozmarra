# Rozmarra: Data Card

This data card describes the data that Rozmarra uses, how the team processes it, and every assumption that the processing makes. The team will update it as the work continues.

| Item | Details |
|---|---|
| Version | 0.1, written on 12 October 2026 |
| Data types | Open anonymised datasets and synthetic data. Rozmarra uses no real patient data from India. |
| Related documents | `docs/model_card.md` describes the models. `docs/techstack.md`, Section 4, describes the data formats. |

## 1. Datasets

| Dataset | Version and file | What Rozmarra uses | Licence |
|---|---|---|---|
| ShanghaiT2DM (Zhao and colleagues, Scientific Data, 2023) | Figshare article 21600933, version 5, file `diabetes_datasets.zip` (3.6 MB, MD5 `4bfb61cfa506b48155fd9e841ee48e21`) | The 109 recording periods in the `Shanghai_T2DM` folder and the file `Shanghai_T2DM_Summary.xlsx`. Rozmarra does not use the Type 1 Diabetes files. | The article uses CC BY 4.0. The data files do not state a separate licence. |
| CGMacros (PhysioNet) | Version 1.0.0, file `CGMacros_dateshifted365.zip` (626.7 MB) | The minute-level file of each of the 45 participants and the file `bio.csv`. | CC BY-NC-SA 4.0 |
| BIG IDEAs Lab Glycemic Variability and Wearable Device Data (PhysioNet) | Version 1.1.3. Rozmarra downloads 65 of the 130 files (396.6 MB): the Dexcom, heart rate, inter-beat interval and food log files of the 16 participants, and `Demographics.csv`. | Rozmarra will use the inter-beat intervals to calculate heart rate variability (a Should item). The loader is not built yet. | Open Data Commons Attribution License v1.0 |
| Synthetic health records | Created by the Rozmarra generator | The static data stream for all synthetic and virtual patients | Apache License 2.0, released with the code |

The repository does not contain any raw dataset. The command `rozmarra data download` fetches each file from its original source.

### 1.1 How the download works

PhysioNet sent data at only about 15 KB per second during the team's first attempt on 12 October 2026. PhysioNet also publishes its open datasets in an official public mirror on Amazon S3 (`physionet-open`), so the download script tries the mirror first. The script checks every file against the SHA-256 checksum that PhysioNet publishes for the cited version. If a mirrored file does not match, the script fetches it from PhysioNet instead.

The mirror holds version 1.1.2 of BIG IDEAs Lab, not version 1.1.3. On 12 October 2026, 62 of the 66 selected files were identical in both versions. The 4 food logs that version 1.1.3 corrected (participants 007, 013, 015 and 016) failed the checksum check and came from PhysioNet. Every downloaded file therefore matches version 1.1.3.

## 2. The standard format

The command `rozmarra data prepare` converts the open datasets into three Parquet files in `data/processed`:

- `timeseries.parquet` holds one reading in each row, with the columns in `docs/techstack.md`, Section 4.1.
- `events.parquet` holds meals, insulin doses and other medicines, with the details as JSON.
- `patients.parquet` holds the static information about each real patient or recording period.

The command also writes a summary to `reports/data_summary.json`.

These rules apply to every dataset:

- Every row has the source label `real_open`. Synthetic data has the label `synthetic`.
- The open datasets shift their dates for privacy. Rozmarra therefore uses the time of day and the day number, not the calendar date.
- Rozmarra never fills a gap in the data. Missing readings stay missing.

## 3. ShanghaiT2DM: processing decisions

| Topic | Decision |
|---|---|
| Identifiers | Each recording period becomes one patient identifier, for example "SH-2010-0" for the file `2010_0_20220111`. Some patients have two recording periods, which keep separate identifiers. |
| CGM | The CGM readings come every 15 minutes. The team records the device as the FreeStyle Libre H, which the dataset article describes. |
| Fingerstick glucose and ketones | Rozmarra keeps them as the signals `glucose_fingerstick` and `blood_ketone`. |
| HbA1c | The summary gives HbA1c in mmol/mol. Rozmarra converts it to % with the IFCC to NGSP master equation: % = mmol/mol ÷ 10.929 + 2.15. |
| Fasting insulin | The summary gives insulin in pmol/L. Rozmarra divides by 6.0 to get µU/mL. This factor is an assumption, because some laboratories use 6.945. |
| Creatinine | The summary gives creatinine in µmol/L. Rozmarra divides by 88.4 to get mg/dL. |
| Column names | The column names vary slightly between files. Two files use "CGM" without units, and one file has a Chinese column name for the insulin pump basal rate. The loader matches columns by their start. |
| Insulin names | The loader maps 16 insulin names to the medicine catalogue, including the spelling "insulin glarigine". For example, "Humulin 70/30" and "Novolin 30R" become premixed human insulin 30/70, and "insulin aspart 70/30" becomes biphasic insulin aspart 30. |
| Gliclazide | The records do not say whether gliclazide is the modified-release form. Rozmarra treats doses in multiples of 30 mg as gliclazide MR and other doses as ordinary gliclazide. This rule is an assumption. |
| Dose units | Some records give a dose in grams where milligrams are meant, for example "empagliflozin 10 g". When a dose in grams is implausible and the same number in milligrams is plausible, Rozmarra reads it as milligrams. This happened for 121 doses, mostly voglibose. A dose is plausible from a tenth of the standard dose to three times the largest single dose. |
| Doses that stay implausible | Rozmarra keeps 86 doses as recorded and marks them "outside the expected range". Examples are "metformin 50 mg" (33 records), "voglibose 100 mg" (40 records) and "linagliptin 0.1 g" (13 records). These are probably recording errors in the source. |
| Insulin pumps and intravenous insulin | 34 recording periods include insulin pump doses, and 5 include intravenous insulin given in hospital. Rozmarra keeps these doses and marks the periods in the patients table, so that the twin fit can treat them separately. |
| Meals | The dataset records meals as text, such as "Rice 100 g", and gives no carbohydrates. Rozmarra estimates the carbohydrates from a table of typical carbohydrate content per 100 g of about 100 foods (`backend/src/rozmarra/data/foods.py`). The table uses approximate values for cooked foods. A food that the table does not know counts as 8 g of carbohydrate per 100 g, and a line without an amount counts as 100 g. Of all food lines, 8.2% are not in the table. Of 3,808 meals, 745 say "data not available" and have no estimate. The median estimate is 34 g of carbohydrate per meal. The twin will fit a personal meal-size factor, which absorbs part of the error in these estimates. |
| Extreme values | The summary contains some extreme values, for example an eGFR of 257 mL/min/1.73 m² and a fasting insulin of 348 µU/mL. Rozmarra keeps them as recorded. The twin fit will limit each parameter to a plausible range. |

## 4. CGMacros: processing decisions

| Topic | Decision |
|---|---|
| Identifiers | Each participant becomes one identifier, for example "CG-001". |
| Groups | The participants are grouped by HbA1c, as in the dataset: below 5.7% is healthy (15 participants), 5.7% to 6.4% is prediabetes (16 participants), and 6.5% or above is Type 2 Diabetes (14 participants). |
| CGM | The dataset gives both CGMs at 1-minute intervals. Rozmarra keeps the Dexcom G6 Pro as the main CGM signal (`glucose_cgm`), averaged over 5-minute intervals. It keeps the FreeStyle Libre Pro as a second signal (`glucose_cgm_secondary`), averaged over 15-minute intervals. |
| Heart rate and activity | Rozmarra averages heart rate and METs over 5-minute intervals. The dataset stores METs multiplied by 10, so Rozmarra divides by 10. |
| Intensity instead of METs | Eleven participants have a Fitbit intensity level instead of METs. Rozmarra turns each level into approximate METs: sedentary is 1.0, light is 2.5, fairly active is 4.5 and very active is 7.0. This mapping is an assumption. |
| Steps | One participant (CG-007) has steps, which Rozmarra adds up over 5-minute intervals. |
| Meals | Rozmarra keeps the recorded calories, carbohydrates, protein, fat and fibre. When the file gives the share of the meal that was eaten, Rozmarra scales the nutrients by that share. |
| Medicines | The files do not contain medicine records. |
| Time zone | The study took place in Texas, so Rozmarra records the time zone as America/Chicago. |
| Body size | The file `bio.csv` gives weight in pounds and height in inches. Rozmarra converts them to kilograms and centimetres. |

## 5. Summary of the converted real data

These numbers describe the converted data on 12 October 2026. They come from `reports/data_summary.json`.

| Measure | ShanghaiT2DM | CGMacros |
|---|---|---|
| Patients or recording periods | 109 | 45 |
| CGM readings | 112,462 | 126,618 |
| Median days of CGM | 12.7 | 9.9 |
| Share of CGM readings below 70 mg/dL | 2.34% | 0.38% |
| Share of CGM readings below 54 mg/dL | 0.77% | 0.12% |
| Meals | 3,808 | 1,706 |
| Meals with carbohydrates | 3,063 (estimated) | 1,706 (recorded) |

The real data contains few readings below 70 mg/dL, especially in CGMacros. The requirements document lists this as a risk, and the team will report the real-data results for low blood sugar with confidence intervals.

## 6. Synthetic health records

The command `rozmarra ehr generate` creates synthetic records, and `rozmarra demo build` saves the four demo patients. Each record is saved as a FHIR R4 Bundle. Every resource in the Bundle carries the HL7 security tag HTEST ("test health data"), so the synthetic label travels with the data.

### 6.1 Starting distributions of the generator

Every value in this table is a starting value and a modelling assumption. The team will compare the medicine proportions with published Indian prescribing studies.

| Item | Starting value |
|---|---|
| Community | Hindu 72%, Muslim 17%, Jain 3%, Sikh 4% and Christian 4% |
| Sex | Female 50% and male 50% |
| Age | Normal distribution with a mean of 56 years and a standard deviation of 10 years, limited to 35 to 80 years |
| Years with diabetes | Mostly 1 to 25 years, and never more than the age minus 25 years |
| Height | Men: a mean of 166 cm. Women: a mean of 153 cm. |
| BMI | A mean of 26 kg/m², limited to 18.5 to 40 kg/m². The team reads BMI with the cut-offs for Asian populations. |
| HbA1c | A mean of 8.0%, limited to 6.5% to 11% |
| Fasting glucose | Derived from HbA1c with the estimated average glucose formula, multiplied by 0.85, with random variation |
| eGFR | Falls with age and with years of diabetes, limited to 30 to 115 mL/min/1.73 m². Creatinine comes from the CKD-EPI 2021 equation in reverse. |
| Hypertension | 35% at age 35, rising by 0.6 percentage points for each year of age |
| Heart disease | None, stable or unstable. Stable and unstable disease become more common with age (17% and 2% at age 35). |
| Insulin | More likely with a higher HbA1c and a longer duration. About a quarter of the patients take insulin: 60% of them premixed insulin twice a day, and 40% basal insulin at night. |
| Metformin | 88% of patients, unless the eGFR is below 30 |
| Sulfonylureas | 55% of patients (30% of those on premixed insulin): glimepiride 60%, gliclazide MR 33% and glibenclamide 7%. Glibenclamide is replaced by gliclazide MR when the eGFR is below 60. |
| DPP-4 inhibitors | 35% of patients: teneligliptin 50%, sitagliptin 30% and vildagliptin 20% |
| SGLT2 inhibitors | 25% of patients, unless the eGFR is below 30 |
| Other medicines | Telmisartan for hypertension, with hydrochlorothiazide for 20% of them. Atorvastatin and aspirin for heart disease. Metoprolol for half of the patients with heart disease and 10% of the patients with hypertension. |
| Low blood sugar history | Patients on insulin or sulfonylureas: none 55%, less than once a week 32%, several times a week 7%, a recent severe episode 4% and unawareness 2%. Other patients have lower rates. |
| Self-monitoring | As needed 30%, less than needed 50%, and needed but not done 20% |
| Occupation and physical work | Chosen from a fixed list. Each occupation has a level of physical work for the IDF-DAR score. 70% of patients aged 62 or over are retired. |
| Frailty and support at home | 10% of patients older than 70 are frail. 20% of patients older than 65 live without support at home. |
| Previous fasting experience | 12% overall negative |
| CYP2C9 genotype | Allele frequencies of 85% for \*1, 5% for \*2 and 10% for \*3 (see Section 6.2) |
| Fasting habits | Hindu patients: Navratri 50%, Karva Chauth 60% of women, Ekadashi 30% and Chhath Puja 5%. Muslim patients: Ramadan 85%. Jain patients: a Jain upvas or ekasana. Other patients: a custom fast 30%. |
| Word for the fast | Hindu patients: व्रत 70% and उपवास 30%. Muslim patients: रोज़ा. Jain and other patients: उपवास. |
| Names and cities | Chosen from fixed lists of Indian names and 16 Indian cities |

The generator links fasting patterns to communities with simple probabilities. Real practice varies widely between families and regions, and the doctor can change every plan.

### 6.2 CYP2C9 allele frequencies

Studies of Indian populations report the \*2 allele at about 4% to 7% and the \*3 allele at about 8% to 13%. For example, Sistonen and colleagues reported 4.4% for \*2 and 9.6% for \*3 in Gujarati volunteers, and a 2021 study in Pharmacogenomics and Personalized Medicine of 36 Indian populations reported about 13% for \*3. The generator uses 5% for \*2 and 10% for \*3.

### 6.3 Codes in the FHIR records

| Item | Code |
|---|---|
| Type 2 Diabetes, hypertension, chronic kidney disease and coronary arteriosclerosis | SNOMED CT 44054006, 38341003, 709044004 and 53741008 |
| HbA1c, fasting glucose, insulin and creatinine | LOINC 4548-4, 1558-6, 20448-7 and 2160-0 |
| eGFR (CKD-EPI 2021) | LOINC 98979-8 |
| Weight, height, BMI, blood pressure and heart rate | LOINC 29463-7, 8302-2, 39156-5, 85354-9 (with 8480-6 and 8462-4) and 8867-4 |
| Occupation | LOINC 11341-5 |
| CYP2C9 genotype | LOINC 84413-4 with the component 48018-6 and the gene HGNC:2623, following the HL7 Genomics Reporting guidance in a simplified form |
| Medicines | WHO ATC codes, with Rozmarra's own catalogue name |
| IDF-DAR inputs | Rozmarra's own code system (`urn:rozmarra:idf-dar-input`), because no standard codes exist for them |

On 12 October 2026, the team checked the codes for eGFR, the genotype, the gene and CYP2C9 against published sources. The team will check the remaining codes in the official SNOMED CT and LOINC browsers before the submission.

### 6.4 Demo patients

The four demo patients follow the summaries in `docs/prd.md`, Section 6.3. The details that the requirements leave open are team choices that give the IDF-DAR totals in `docs/techstack.md`, Section 9. For example, Kamla Devi's HbA1c of 7.2% and Abdul Rahman's eGFR of 82 mL/min/1.73 m² are team choices. Ramesh Patel's usual word for the fast is उपवास, which is common in Gujarat. The Ekadashi date for Kamla Devi (5 November 2026) is an example date, and the doctor should check the local calendar.

## 7. Fasting templates

The fasting templates in `backend/src/rozmarra/fasting/templates.py` are starting points. The doctor can change every time, meal and water setting.

- Each time follows the clock, dawn, sunrise, sunset or moonrise for the patient's city. Rozmarra calculates the sun times with the NOAA solar position equations, which are accurate to about 2 minutes.
- Dawn for Ramadan uses the sun at 18 degrees below the horizon, which is the convention in many Indian timetables.
- For Karva Chauth, Rozmarra uses the published moonrise time in Delhi on 28 October 2026 (about 8:14 pm). In other cities, the plan asks the doctor to enter the local moonrise time.
- The meal sizes are starting values. For example, the meal that breaks the Karva Chauth fast has 110 g of carbohydrate, and the Navratri evening meal has 100 g.
- For the "fasting hours" item of the IDF-DAR score, Rozmarra uses the longest time between two meals in the plan.

## 8. Limitations

- The real data comes from China and the United States, not from India.
- The synthetic records and the synthetic fasting days reflect the team's modelling assumptions.
- The carbohydrate values in ShanghaiT2DM are rough estimates from the meal text.
- No doctor or pharmacist has reviewed the clinical content of this prototype.

## 9. Citations

1. Zhao Q, et al. Chinese diabetes datasets for data-driven machine learning (ShanghaiT1DM and ShanghaiT2DM). Scientific Data, 2023;10:35.
2. CGMacros: a scientific dataset for personalized nutrition and diet monitoring. PhysioNet, version 1.0.0, 2025.
3. BIG IDEAs Lab Glycemic Variability and Wearable Device Data. PhysioNet, version 1.1.3.
4. Goldberger A, et al. PhysioBank, PhysioToolkit, and PhysioNet: components of a new research resource for complex physiologic signals. Circulation, 2000.
5. Sistonen J, et al. Pharmacogenetic variation at CYP2C9, CYP2C19, and CYP2D6 at global and microgeographic scales. Pharmacogenetics and Genomics, 2009. The team took the Gujarati frequencies from a study of a diabetic cohort in Gujarat that cites this work (Indian Journal of Pharmaceutical Sciences): https://www.ijpsonline.com/articles/investigating-the-role-of-plasma-glucose-concentration-as-a-phenotypic-marker-for-cyp2c9-genetic-variants-in-the-diabeti.pdf
6. CYP2C9 variations and their pharmacogenetic implications among diverse South Asian populations. Pharmacogenomics and Personalized Medicine, 2021, volume 14. https://www.dovepress.com/cyp2c9-variations-and-their-pharmacogenetic-implications-among-diverse-peer-reviewed-fulltext-article-PGPM
