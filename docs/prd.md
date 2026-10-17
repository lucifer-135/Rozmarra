# Rozmarra: Product Requirements Document

Rozmarra is a digital twin that helps doctors keep people with Type 2 Diabetes safe during religious fasts in India.

| Item | Details |
|---|---|
| Project name | Rozmarra |
| Full title | Rozmarra: A Digital Twin That Predicts Low and High Blood Sugar During Religious Fasting for People with Type 2 Diabetes in India |
| Hackathon | Digital Twin Challenge 2026 by Happiest Health, part of the Reimagining and Reforming Healthcare in India Summit 2026, Bengaluru |
| Submission deadline | 20 October 2026, 7:00 PM IST |
| Document version | 1.1, updated on 12 October 2026 with the answers to the open questions |
| Document status | Approved for building. The team will update this document when a decision changes. |
| Team | NOT_SOMEONE_IMPORTANT. The members are Shivansh Gautam (team leader; digital twin and prediction models), Aman Soni (data and application) and Divy Sharma (documentation, testing and presentation). The college is IIT (ISM) Dhanbad. |
| Repository name | Rozmarra |
| Related document | `techstack.md` describes the tools, data formats, models and code structure. |

---

## 1. Summary

Rozmarra is a proof-of-concept digital twin for adults with Type 2 Diabetes who keep religious fasts, such as Navratri, Karva Chauth, Ekadashi, Jain fasts and Ramadan. The twin is a virtual copy of one patient. It combines the patient's health record with data from a continuous glucose monitor (CGM) and a smartwatch.

Rozmarra helps the doctor in three ways:

1. **Before the fast**, the doctor tests a fasting plan on the virtual patient. Rozmarra shows when the risk of low blood sugar is highest. It also shows how a change in medicine dose or meal timing may change that risk.
2. **During the fast**, Rozmarra predicts low blood sugar at least 60 minutes before it happens. It also predicts high blood sugar after the fast is broken, at least 2 hours before it happens.
3. **After the doctor approves the plan**, Rozmarra prints a clear fasting plan for the patient in English or Hindi.

Rozmarra supports the doctor's decisions. It does not make treatment decisions, and it does not give religious advice.

## 2. About the name

Rozmarra (रोज़मर्रा) is a Hindi and Urdu word that means "everyday". The name reflects the aim of the project: safe fasting should be a normal, everyday part of diabetes care for people of every faith.

## 3. The problem

### 3.1 Diabetes is common in India

The ICMR-INDIAB study estimated that 101 million people in India have diabetes and that 136 million people have prediabetes (The Lancet Diabetes & Endocrinology, 2023).

### 3.2 Many people with diabetes fast, often without medical advice

A 2020 study surveyed 300 adults with Type 2 Diabetes at three clinics in North India (US Endocrinology, 2020). The study found the following:

- 49% of the participants had fasted at least once in the previous year.
- Only 1.35% had discussed their diet with a doctor or dietitian before fasting.
- Only about 4% had checked their glucose during their last fast.
- 47% of the Hindu women in the study observed Navratri, and 60% observed Karva Chauth.
- During these fasts, many participants ate sweets (62% during Navratri and 70% during Karva Chauth). Many also ate fried foods (48% during Navratri and 39% during Karva Chauth).

### 3.3 Fasting can change the risk of low and high blood sugar

- The EPIDIAR study included 12,243 people with diabetes in 13 countries. It found that 78.7% of the participants with Type 2 Diabetes fasted for at least 15 days during Ramadan. For people with Type 2 Diabetes, severe low blood sugar that needed hospital care was 7.5 times more common during Ramadan than in other months.
- Some medicines raise insulin levels, such as sulfonylureas and insulin. These medicines can cause low blood sugar when a person does not eat for many hours.
- Some fasts do not allow water, such as Karva Chauth and the daytime fast during Ramadan. These fasts may increase the risk of dehydration. The risk may be higher for people who take SGLT2 inhibitors or diuretics.
- The meal that breaks the fast is often large and rich in sugar and fat. This meal can cause high blood sugar in the hours that follow.

### 3.4 What doctors have today, and what is missing

Doctors can use the IDF-DAR 2021 risk score. This score uses information from the health record to place a person into low, moderate or high fasting risk. The score is useful, but it is calculated once and it does not change during the fast. The score cannot show the following:

- the time of day when the risk of low blood sugar is highest;
- how a change in medicine dose or timing may change the risk;
- what is happening to the patient during the fast; and
- how the meal that breaks the fast may affect blood sugar.

Rozmarra aims to fill these gaps. The IDF-DAR score was designed for Ramadan. Rozmarra will also apply it to other fasts as an approximation, and the dashboard will say so clearly.

## 4. Why this matters now

| Event | Date |
|---|---|
| Sharad Navratri | 11 to 20 October 2026 |
| Hackathon submission deadline | 20 October 2026 (Vijayadashami), 7:00 PM IST |
| Karva Chauth | 28 October 2026. Moonrise is at about 8:14 pm IST, and the time varies by city. |
| Summit showcase in Bengaluru | 20 November 2026 |
| Ramadan in India (expected) | About 9 February to 9 March 2027. The exact dates depend on the sighting of the moon. |

Several major fasts take place in the weeks before and after the summit. A tool such as Rozmarra could help doctors prepare their patients for each of them.

## 5. Goals and non-goals

### 5.1 Product goals

| ID | Goal |
|---|---|
| G1 | Rozmarra predicts low blood sugar during a fast at least 60 minutes before it happens. |
| G2 | Rozmarra predicts high blood sugar after the fast is broken at least 2 hours before it happens. |
| G3 | The doctor can test and compare fasting plans on the virtual patient before the fast begins. |
| G4 | Rozmarra explains every prediction in plain language. |
| G5 | Rozmarra produces a fasting plan for the patient in English and Hindi after the doctor approves it. |

### 5.2 Hackathon goals

| ID | Goal |
|---|---|
| H1 | The prototype shows the fusion of health record data and wearable data, as the challenge requires. |
| H2 | The team tests the models on real open data as well as synthetic data, and reports the results honestly. |
| H3 | The team submits every required item before 20 October 2026, 7:00 PM IST. |
| H4 | The team aims to reach the top 10 for the jury presentation and the top 5 for the summit showcase. |

### 5.3 Non-goals

- Rozmarra will not tell anyone whether they should fast. That decision belongs to the patient, their family, their doctor and, if they wish, their religious advisers.
- Rozmarra will not change medicine doses by itself. The doctor makes and approves every treatment decision.
- Rozmarra is a research prototype. It is not a certified medical device, and the team will not use it with real patients in this phase.
- The team will not use real patient data. All data will be open and anonymised, or synthetic.
- This phase does not cover Type 1 Diabetes, pregnancy (including gestational diabetes) or children.
- This phase does not connect to real devices. Rozmarra replays wearable data from files.

## 6. Users

### 6.1 Primary user: the doctor

Dr Ananya Rao is a fictional diabetologist in Bengaluru. She sees about 40 patients a day. During festival seasons, many patients ask her whether they can fast. She usually has about five minutes for this conversation.

Her needs are as follows:

- She needs to see quickly which patients have the highest fasting risk.
- She needs to understand when and why the risk rises during the fast.
- She needs to test a medicine change on the twin before she recommends it.
- She needs a clear plan that she can give to the patient and family.

### 6.2 Secondary users

- Diabetes educators and nurses use the printed fasting plan to teach patients and families.
- Patients and families read the printed plan. They do not use the dashboard in this phase.

### 6.3 Demo patients

All demo patients are synthetic. The team created them for the demonstration, and they do not represent real people. The last column describes the risk that each demo is designed to illustrate. The actual numbers will come from the model.

| Patient | Fast | Health record summary | Risk that the demo will illustrate |
|---|---|---|---|
| Sunita Sharma, Age 54, Delhi | Karva Chauth, with no food or water from sunrise to moonrise | She has had Type 2 Diabetes for 8 years. Her HbA1c is 8.4%. She takes glimepiride 2 mg, metformin and dapagliflozin (an SGLT2 inhibitor). She carries one reduced-function CYP2C9 gene variant. | Her IDF-DAR score is low. The twin is expected to show a higher chance of low blood sugar in the late afternoon. The long fast without water also triggers a dehydration caution. |
| Ramesh Patel, Age 62, Ahmedabad | Navratri, with one meal a day in the evening and garba dancing after the meal | He has had Type 2 Diabetes for 15 years. His HbA1c is 7.9% and his eGFR is 52. He takes premixed insulin twice a day and gliclazide MR. He has stable heart disease. | His IDF-DAR score is high. The twin is expected to show that his usual morning dose of premixed insulin, on a day with only one evening meal, raises the risk of low blood sugar in the afternoon. It will also show the effect of evening dancing. |
| Abdul Rahman, Age 58, Hyderabad | Ramadan, from dawn to sunset | He has had Type 2 Diabetes for 10 years. His HbA1c is 7.6%. He takes basal insulin (glargine) and metformin. He works in a shop and is on his feet for most of the day. He had low blood sugar once during the last Ramadan. | The twin is expected to show how the dose and timing of basal insulin change the risk of low blood sugar before iftar. It will also show how a large iftar meal may cause high blood sugar afterwards. |
| Kamla Devi, Age 71, Varanasi (Should) | Ekadashi, twice a month | She has had Type 2 Diabetes for 20 years. She takes glibenclamide, her eGFR is 48, and she lives alone. | Her IDF-DAR score is high because of her age, her kidney function, the medicine she takes and the lack of support at home. |

## 7. How Rozmarra meets the challenge requirements

| Challenge requirement | How Rozmarra meets it |
|---|---|
| Teams choose one chronic or lifestyle condition that is common in India. | Rozmarra focuses on Type 2 Diabetes, and on one specific situation: religious fasting. |
| Static or historical data: simulated health records with demographics, past diagnoses, lab results and genetic markers. | Synthetic health records in FHIR R4 format include age, sex, diagnoses, years with diabetes, HbA1c, eGFR, medicines, past episodes of low blood sugar, heart disease and a CYP2C9 genetic marker. |
| Dynamic data: time-series data from wearables or IoT sensors. | Rozmarra uses CGM glucose, heart rate, heart rate variability, steps, activity and sleep. This data comes from open datasets (ShanghaiT2DM, CGMacros and the BIG IDEAs Lab dataset) and from synthetic fasting days. |
| A working model combines both streams and predicts an adverse event. | A hybrid model combines a personalised physiology model with a machine learning model. It predicts low blood sugar 60 minutes ahead, and high blood sugar after the fast at least 2 hours ahead. |
| A conceptual dashboard shows how a doctor interacts with the virtual patient. | Rozmarra includes a working dashboard with a patient list, a virtual patient page, a fasting plan simulator, a live fasting monitor and a printable patient plan. |
| Teams use only anonymised, open-source or synthetic data. | Rozmarra uses only open anonymised datasets and synthetic data. It labels every record as real open data or synthetic data. |
| The digital twin helps to personalise treatment (from the challenge description). | The fasting plan simulator lets the doctor test medicine and meal changes on the twin before choosing a plan. |

## 8. How Rozmarra works

### 8.1 Before the fast: the doctor tests the plan

1. The doctor opens the patient's virtual twin. Rozmarra shows the health record summary, recent glucose and wearable data, and the IDF-DAR 2021 risk score.
2. The doctor enters the fasting plan. The plan includes the type of fast, the start and end times, the meals, whether water is allowed and the usual medicines.
3. The twin simulates the fast. It shows the expected glucose curve with an uncertainty band, and it marks the times when low or high blood sugar is likely.
4. The doctor changes one or more parts of the plan, for example the medicine dose or the time of a meal. The doctor then compares the two plans side by side.
5. The doctor approves the chosen plan. Rozmarra then prints the plan for the patient in English or Hindi.

### 8.2 During the fast: Rozmarra watches and warns

1. Rozmarra receives new readings from the CGM and the smartwatch every 5 to 15 minutes. In this prototype, Rozmarra replays these readings from files.
2. The twin updates its estimate of the patient's current state.
3. The prediction model estimates the chance of low blood sugar in the next 60 minutes. It also estimates the chance of high blood sugar after the fast is broken.
4. When a risk crosses the alert threshold, the dashboard shows an alert with the main reasons in plain language.

### 8.3 After the fast: the twin learns

1. The doctor reviews what happened during the fast and compares it with the prediction.
2. The twin uses the new data to update the patient's personal settings for the next fast. (Could)

## 9. Fasting patterns that Rozmarra supports

Practices vary between families, communities and regions. The patterns below are starting templates. The doctor can change every time, meal and water setting to match how the patient actually fasts.

| Fast | Usual timing | Food and water | Points that matter for blood sugar |
|---|---|---|---|
| Navratri | Navratri lasts nine days and takes place twice a year. Sharad Navratri 2026 runs from 11 to 20 October. | Many people avoid grains. They eat fruit, milk, curd, potatoes, sabudana, and flours such as kuttu (buckwheat) and singhara (water chestnut). Some people eat one meal a day, and others eat three times a day. Water is usually allowed. | Sabudana and potatoes can raise blood sugar quickly. Sweets and fried foods are common. Evening garba or dandiya dancing increases physical activity. |
| Karva Chauth | The fast lasts one day. In 2026, it falls on 28 October. | Women eat a meal called sargi before sunrise. They then take no food or water until moonrise. They usually break the fast with water and a meal that often includes sweets. | The fast without water lasts about 15 to 16 hours. The meal that breaks the fast is often large and sweet. |
| Ekadashi | Ekadashi takes place twice in each lunar month. | Many people avoid grains and beans. Some people eat fruit and milk, and some keep the fast without water, for example on Nirjala Ekadashi. | The fast repeats twice a month, so Rozmarra can learn a personal pattern over time. |
| Ramadan | Ramadan lasts about 29 or 30 days. Ramadan 2027 is expected to run from about 9 February to 9 March in India. | People eat suhoor before dawn. They take no food or water from dawn to sunset. They break the fast at sunset with iftar, which often begins with dates and water. | In February and March, the daily fast in India lasts about 12 to 14 hours. Sleep patterns change because of the meal before dawn and night prayers. |
| Jain fasts | Jain fasts take place at several times of the year, for example during Paryushan. | Upvas means no food for the whole day. Some people take only boiled water during daylight hours, and others take nothing. Ekasana means one meal a day. | Some fasts last more than one day. |
| Chhath Puja (Should) | The festival lasts four days, and the main fast comes near the end. | The main fast lasts about 36 hours without food or water. | This is one of the longest fasts without water, so the dehydration caution is especially important. |
| Custom fast | The doctor can choose any date and time. | The doctor sets the start and end times, the meals and the water setting. | Rozmarra can model fasts that are not in this list. |

## 10. Adverse events that Rozmarra predicts

| ID | Event | Definition | When Rozmarra predicts it | Priority |
|---|---|---|---|---|
| E1 | Low blood sugar during the fast (hypoglycaemia) | CGM glucose stays below 70 mg/dL for at least 15 minutes. Rozmarra marks the event as severe if glucose falls below 54 mg/dL. | Rozmarra predicts it at least 60 minutes before the event (Must), and at least 120 minutes before the event (Should). | Must |
| E2 | High blood sugar after the fast is broken (hyperglycaemia) | CGM glucose stays above 250 mg/dL for at least 15 minutes within 4 hours after the meal that breaks the fast. | Rozmarra predicts it at least 2 hours before the fast is broken, using the planned meal. | Must |
| E3 | Very high blood sugar during the fast | CGM glucose rises above 300 mg/dL. The IDF-DAR guide advises people to break the fast at this level. | Rozmarra predicts it at least 60 minutes before the event. | Should |
| F1 | Whole-fast risk forecast | Rozmarra estimates the chance of E1 at any time during the fast, the predicted lowest glucose value and its time, and the expected number of minutes below 70 mg/dL. The forecast uses the twin simulation together with the patient's CGM history from the past 7 to 14 days. | Rozmarra produces the forecast when the doctor tests a plan, before the fast begins. | Must |
| C1 | Dehydration caution | This caution is a rule, not a prediction. Rozmarra shows it when a fast without water lasts 12 hours or more and at least one of the following is true: the patient takes an SGLT2 inhibitor or a diuretic, the eGFR is below 60, or the patient is older than 65. A clinical expert should review this rule. | Rozmarra checks the rule when the doctor tests a plan. | Must |

The sources for these thresholds are as follows:

- The 70 mg/dL and 54 mg/dL levels and the 15-minute rule follow the international consensus on CGM metrics.
- The 250 mg/dL level is the consensus level for very high glucose (level 2).
- The advice to break the fast below 70 mg/dL or above 300 mg/dL follows the IDF-DAR guide for a safe fast.

## 11. Requirements

The priorities have the following meanings:

- **Must**: The team needs this item for the 20 October submission.
- **Should**: The team plans to build this item, but can drop it if time runs short.
- **Could**: The team will build this item only if time allows.

### 11.1 Data

| ID | Requirement | Priority |
|---|---|---|
| FR-A1 | Rozmarra loads the ShanghaiT2DM and CGMacros datasets. It converts them into one standard time-series format with glucose, heart rate, activity, meals and medicines. | Must |
| FR-A2 | Rozmarra creates synthetic health records for Indian patients in FHIR R4 format. The records include demographics, diagnoses, lab results, medicines, past episodes of low blood sugar, fasting habits and a CYP2C9 genotype. | Must |
| FR-A3 | Rozmarra creates synthetic fasting days for each fasting pattern in Section 9. Each day includes CGM glucose, heart rate, heart rate variability, steps and sleep. | Must |
| FR-A4 | Every record, chart and table shows whether its data comes from real open data or from synthetic data. | Must |
| FR-A5 | Rozmarra loads heart rate and inter-beat interval data from the BIG IDEAs Lab dataset to calculate heart rate variability. | Should |
| FR-A6 | The team uses Synthea to create the base medical history of the synthetic patients and then adds the India-specific fields. | Should |
| FR-A7 | The team applies for access to the AI-READI dataset. Rozmarra does not depend on this dataset for the 20 October submission. | Could |

### 11.2 Digital twin

| ID | Requirement | Priority |
|---|---|---|
| FR-B1 | Rozmarra builds a personalised glucose and insulin model for each patient. It fits the model to the patient's normal, non-fasting days. | Must |
| FR-B2 | The twin models the effects of diabetes medicines that are common in India. These include sulfonylureas (glimepiride, gliclazide and glibenclamide), metformin, DPP-4 inhibitors, SGLT2 inhibitors, basal insulin and premixed insulin. Each medicine taken by mouth follows a simple activity curve with a time to peak and a half-life. | Must |
| FR-B3 | The twin uses the CYP2C9 genotype to adjust how quickly the body clears sulfonylureas. | Must |
| FR-B4 | The twin simulates any fasting pattern from Section 9, including meals, water, physical activity and medicine changes. | Must |
| FR-B5 | Every simulation shows an uncertainty band from the 10th to the 90th percentile. | Must |
| FR-B6 | Rozmarra reports how well each twin fits the patient's real data. | Must |
| FR-B7 | The twin starts each forecast from the latest CGM value, and its starting slope matches the CGM trend of the last 30 minutes. | Must |
| FR-B8 | The twin updates its state as new readings arrive, using a Kalman filter. | Should |
| FR-B9 | The twin updates the patient's personal settings after each fast. | Could |

### 11.3 Risk and prediction

| ID | Requirement | Priority |
|---|---|---|
| FR-C1 | Rozmarra calculates the IDF-DAR 2021 risk score from the health record. It shows the points for each item and lists any missing information. | Must |
| FR-C2 | Rozmarra predicts E1 at least 60 minutes ahead, and E2 at least 2 hours before the fast is broken. | Must |
| FR-C3 | Rozmarra predicts E1 at least 120 minutes ahead, and E3 at least 60 minutes ahead. | Should |
| FR-C4 | Rozmarra produces the whole-fast risk forecast (F1) for any fasting plan. | Must |
| FR-C5 | Each alert shows the three main reasons for the prediction in plain language. | Must |
| FR-C6 | Rozmarra shows the dehydration caution (C1) whenever its rule applies. | Must |
| FR-C7 | Rozmarra does not repeat the same alert within 30 minutes unless the risk rises further. | Should |
| FR-C8 | Rozmarra makes a prediction only when at least 70% of the expected CGM readings from the last 2 hours are present. Otherwise, the dashboard shows this message: "There is not enough recent CGM data to make a prediction. Please check that the sensor is working." | Must |
| FR-C9 | Rozmarra uses the patient's CGM history from the past 7 to 14 days, such as the time below 70 mg/dL, glucose variability and the number of low blood sugar events. | Must |

### 11.4 Doctor dashboard

| ID | Requirement | Priority |
|---|---|---|
| FR-D1 | The dashboard shows a list of patients who plan to fast, sorted by risk. | Must |
| FR-D2 | The dashboard shows a virtual patient page. The page includes the health record summary, the IDF-DAR score, recent glucose and wearable data, and the quality of the twin's fit. | Must |
| FR-D3 | The doctor can test a fasting plan and compare two plans side by side. | Must |
| FR-D4 | The dashboard replays a recorded fasting day with a time slider. It shows the forecasts and alerts as they would have appeared at each moment. | Must |
| FR-D5 | The doctor must approve a plan before Rozmarra can print it. An approved plan shows the text "Approved by Dr [name] on [date]". | Must |
| FR-D6 | Every screen shows a "Synthetic data" label where relevant. Every screen also shows this notice: "Rozmarra supports clinical decisions. It does not replace the judgement of a doctor." | Must |
| FR-D7 | One page explains how Rozmarra makes predictions, which data it uses, how well it performs and what its limits are. | Should |
| FR-D8 | The doctor can switch the dashboard between English and Hindi. | Could |
| FR-D9 | The fasting plan simulator also shows the curve for an average patient with the same plan. This curve shows how the patient's own twin differs from an average patient. | Should |

### 11.5 Patient fasting plan

| ID | Requirement | Priority |
|---|---|---|
| FR-E1 | Rozmarra produces a printable fasting plan in English and in Hindi. | Must |
| FR-E2 | The plan uses the patient's own word for the fast, such as व्रत, उपवास or रोज़ा. | Must |
| FR-E3 | The plan includes the times to check blood sugar, the rule for breaking the fast, the medicine changes that the doctor approved, advice for the meal that breaks the fast, advice on water where water is allowed, and the doctor's contact details. | Must |
| FR-E4 | All patient text comes from fixed templates that a person has reviewed. Rozmarra does not use AI to write medical advice. | Must |
| FR-E5 | Rozmarra produces a short version of the plan for SMS or WhatsApp. This feature is a concept only, and Rozmarra does not send any messages. | Could |

### 11.6 Documents and submission

| ID | Requirement | Priority |
|---|---|---|
| FR-F1 | The README contains every item that the challenge requires (see Section 19). | Must |
| FR-F2 | The repository includes an architecture diagram in PDF format and a presentation in PDF or PPT format. | Must |
| FR-F3 | The team records a demonstration video that lasts between 15 and 20 minutes. The team uploads it to YouTube as an unlisted video. | Must |
| FR-F4 | The repository includes a model card and a data card. | Must |
| FR-F5 | The repository includes an open-source licence file (Apache License 2.0). | Must |
| FR-F6 | A judge can run the demo with documented commands on Windows, macOS or Linux. | Must |
| FR-F7 | A hosted demo link lets judges try Rozmarra without installing anything. | Could |

## 12. Dashboard screens

The dashboard follows these design principles:

- The design is calm and clinical, and the doctor can read each screen at a glance.
- The design does not rely on colour alone. Every colour also has a text label or an icon.
- Every number shows its unit.
- Synthetic data is always labelled.

The numbers in the example text below are example values. The real values will come from the model.

### Screen 1: Patients who plan to fast

This screen helps the doctor see quickly which patients need attention first. It lists each patient's name and age, the type and date of the fast, the IDF-DAR category, the predicted chance of low blood sugar during the fast, and the plan status (Not started, Draft or Approved).

Example text: "Sunita Sharma, Age 54. Karva Chauth on 28 October 2026. IDF-DAR risk: Low. Predicted chance of low blood sugar during the fast: 41% (Moderate)."

### Screen 2: Virtual patient

This screen shows what the twin knows about the patient. It includes the following:

- the health record summary;
- the IDF-DAR score with the points for each item;
- the last 7 to 14 days of glucose, heart rate, steps and sleep data; and
- the quality of the twin's fit.

Example text: "On this patient's past data, the twin's 2-hour forecasts differed from the measured glucose by 18 mg/dL on average."

Example text: "This patient carries one reduced-function CYP2C9 gene variant. Glimepiride may stay in the body longer than usual."

### Screen 3: Test a fasting plan

This screen lets the doctor test and compare two plans before the fast. The left side holds the plan form: the fasting template, times, meals, water, medicines and activity. The right side shows the glucose curve with its uncertainty band for Plan A and Plan B. Summary cards show the following for each plan:

- the chance of low blood sugar during the fast;
- the predicted lowest glucose value and its time;
- the expected minutes below 70 mg/dL; and
- the chance of high blood sugar after the fast is broken.

A grey dotted line shows the curve for an average patient with the same plan, so the doctor can see how this patient differs. The screen also shows the dehydration caution when it applies, and an "Approve this plan" button.

Example text: "With Plan A, the predicted lowest glucose is 61 mg/dL at about 4:30 pm. With Plan B, the predicted lowest glucose is 84 mg/dL at about 5:00 pm."

### Screen 4: Live fasting monitor (replay)

This screen shows how Rozmarra would warn the doctor during a fast. A time slider moves through a recorded fasting day. The screen shows the glucose readings so far, the forecast, an alert timeline, and panels for heart rate, heart rate variability and steps.

Example alert: "Low glucose is likely within the next 60 minutes. Estimated chance: 74% (High). Predicted lowest value: 63 mg/dL at about 4:40 pm. Main reasons: glimepiride was taken at 8:00 am, no food has been eaten for 11 hours, and the heart rate has risen by 12 beats per minute without extra activity."

### Screen 5: Patient fasting plan

This screen produces a printable plan that the patient and family can follow. The plan prints on A4 paper with large text.

Example text in English:

- "Please check your blood sugar at 12 noon, 3 pm and 5 pm."
- "Please break your fast immediately if your blood sugar is below 70 mg/dL or above 300 mg/dL, or if you feel unwell."
- "Your doctor has advised you to take 1 mg of glimepiride instead of 2 mg on the day of the fast."
- "Please start the meal that breaks the fast with water and a small portion of food. Please eat sweets only in a small amount."

Example text in Hindi:

- "कृपया दोपहर 12 बजे, 3 बजे और शाम 5 बजे अपनी शुगर की जाँच करें।"
- "अगर शुगर 70 mg/dL से कम या 300 mg/dL से ज़्यादा हो, या आपकी तबीयत ठीक न लगे, तो कृपया तुरंत व्रत खोल दें।"
- "आपके डॉक्टर ने सलाह दी है कि व्रत के दिन आप ग्लिमेपिराइड 2 mg की जगह 1 mg लें।"

A native Hindi speaker will review all Hindi text before the submission.

### Screen 6: How Rozmarra makes predictions

This screen is the model card in plain language. It explains which data Rozmarra uses, how the team tested it, what the results were and what its limits are.

## 13. Model approach

Rozmarra uses three layers that work together:

1. **Physiology twin.** This is a personalised model of glucose and insulin. It includes meals, medicines, physical activity and the effect of long fasts. The twin can answer "what if" questions, for example "What happens if the patient takes half the usual dose?"
2. **Prediction model.** This is a machine learning model (LightGBM). It uses the twin's forecasts together with CGM, wearable, health record and fasting information. It estimates the chance of each adverse event.
3. **Clinical score and safety rules.** These include the IDF-DAR 2021 score and simple rules such as the dehydration caution.

Rozmarra explains each prediction with SHAP values, which show how much each input contributed. The dashboard turns the largest contributions into plain-language reasons.

The team chose a hybrid design for two reasons. First, the physiology model can answer "what if" questions, and it stays sensible in situations with little data, such as a 36-hour fast. Second, the machine learning model can learn patterns that the physiology model misses, such as how the heart rate changes before low blood sugar.

Rozmarra also uses simple ideas from two published open-source projects. From the T2DSim AI project, it takes medicine activity curves, a starting state that matches the CGM trend, and a fitting method that gives extra weight to missed low and high glucose values. From the Stanford hypoglycemia forecasting project, it takes a rule for data completeness, reporting at 54 mg/dL, the use of recent CGM history, and a balanced alert threshold. Rozmarra uses these ideas in its own code, and the team cites both projects (Section 24).

`techstack.md` describes the equations, features and training methods in detail.

## 14. Data

| Dataset | What it contains | How Rozmarra uses it | Access and licence |
|---|---|---|---|
| ShanghaiT2DM (Scientific Data, 2023) | The dataset includes 100 adults with Type 2 Diabetes in Shanghai. The data includes CGM readings every 15 minutes for 3 to 14 days, meal records, insulin and other diabetes medicines, and lab results such as HbA1c and eGFR. | Rozmarra uses it to fit the twin's responses to medicines and meals, and to test predictions on real patients. This Asian group is closer to Indian physiology than most Western datasets. | The data is open on Figshare. The article uses the CC BY 4.0 licence, and the data files do not state a separate licence. The team will cite the dataset and will not copy it into the repository. |
| CGMacros (PhysioNet, 2025) | The dataset includes 45 adults in the United States: 15 healthy adults, 16 with prediabetes and 14 with Type 2 Diabetes. The data covers 10 days and includes two CGMs, minute-by-minute heart rate and activity from a Fitbit, meal nutrients and photos, lab results and demographics. | Rozmarra uses it to fit responses to meals and activity, and to test the fusion of CGM and smartwatch data on real people. | The data is open access under the CC BY-NC-SA 4.0 licence (non-commercial, share alike). |
| BIG IDEAs Lab Glycemic Variability and Wearable Device Data (PhysioNet) | The dataset includes 16 adults with high-normal glucose. The data covers 8 to 10 days and includes a Dexcom G6 CGM, an Empatica E4 wristband (heart rate, inter-beat intervals, skin temperature, electrodermal activity and movement) and food logs. | Rozmarra uses the inter-beat intervals to calculate heart rate variability. (Should) | The data is open access under the Open Data Commons Attribution License v1.0. |
| Synthetic health records | These records describe Indian patients with Type 2 Diabetes. The team's generator creates them, and Synthea may add to them if time allows. The distributions follow published Indian data such as ICMR-INDIAB. | These records provide the static data stream for all virtual patients. | The team creates this data and releases it with the code. |
| Synthetic fasting days | This data includes simulated CGM, heart rate, heart rate variability, steps and sleep for each fast in Section 9. | Rozmarra uses this data to train and test fasting predictions, because no open dataset contains CGM data from Indian festival fasts. | The team creates this data and releases it with the code. |
| AI-READI (optional) | This is a large Type 2 Diabetes dataset with CGM and smartwatch data, including sleep. Version 3 includes 2,280 participants. | This dataset could add real sleep and heart rate data in a later phase. | Access requires an approved data access request. The 20 October submission does not depend on it. |

The team will follow these data rules:

- The team will not commit raw datasets to the repository. Download scripts will fetch them from the original sources.
- The repository will include a small synthetic demo group of patients, so that the demo runs without the large datasets.
- The README and the data card will cite every dataset.

## 15. Validation plan and success measures

### 15.1 Two-part validation

No open dataset contains CGM data from Indian festival fasts. The team will therefore test Rozmarra in two parts and will state this clearly in all materials.

1. **Real data test.** The team will test glucose forecasts and event predictions on real patients from ShanghaiT2DM and CGMacros whose data was not used for training. These tests use normal days, not fasting days.
2. **Simulated fasting test.** The team will test predictions on simulated fasting days for virtual patients who were not used for training. The team will create the virtual test patients only from real patients in the test group.

### 15.2 Rules for fair testing

- The team will split training and test data by patient, so the same person never appears in both groups.
- The team will compare every result with simple baselines: the last glucose value, a straight-line trend, the IDF-DAR score alone, a model that uses only CGM data, and the twin alone.
- An ablation study will compare models that use one data stream each with the full model that combines all streams. This test shows whether combining the data streams adds value.
- The results will include 95% confidence intervals from bootstrapping by patient.
- The team will report results for these subgroups: medicine type, age 65 and over, eGFR below 60, and sex.
- The team will score a prediction only when at least 70% of the expected CGM readings are present, both before the prediction and in the period that the prediction covers.
- The team will report E1 results at 70 mg/dL and also at 54 mg/dL, which is the level for clinically significant low blood sugar.
- The team will report results at two alert thresholds. The first threshold detects 80% of events. The second threshold is the point where sensitivity equals specificity.

### 15.3 Success measures

These numbers are targets. The team will report the measured values honestly, even if they fall short of the targets.

| Measure | Data | Target |
|---|---|---|
| How well the model separates E1 events from non-events 60 minutes ahead (AUROC) | Real patients held out from training | 0.80 or higher |
| The same measure (AUROC) | Simulated fasting days | 0.85 or higher |
| The share of E1 events detected in time (sensitivity) | Simulated fasting days | At least 80%, with no more than 2 false alerts per patient per day |
| The median warning time before E1 | Both | At least 30 minutes |
| How well the model separates E2 events from non-events 2 hours ahead (AUROC) | Simulated fasting days, with real meals as a check | 0.80 or higher |
| Glucose forecast error (RMSE) at 30, 60 and 120 minutes | Real patients held out from training | Lower than the last-value and straight-line baselines at every time horizon |
| The share of 30-minute forecasts in zones A and B of the Parkes error grid for Type 2 Diabetes | Real patients held out from training | 95% or more |
| The value of combining data streams | Both | The full model has a higher AUPRC than every model that uses a single data stream |
| Calibration (Brier score and calibration plot) | Both | The team reports both for every model |
| Simulation speed | A laptop | One fasting day with an uncertainty band takes less than 1 second |
| Dashboard speed | A laptop | Every screen loads in less than 2 seconds |

## 16. Non-functional requirements

- **Privacy.** Rozmarra uses only open anonymised data and synthetic data. The repository contains no personal data. This approach follows the data rules of the challenge, which refer to the DPDP Act and HIPAA.
- **Safety.** Rozmarra supports decisions only. The doctor must approve every plan. Every plan shows the rule for breaking the fast, and Rozmarra never changes medicines by itself.
- **Transparency.** Rozmarra explains every prediction. The model card describes the data, the tests, the results and the limits. Synthetic data is always labelled.
- **Accessibility.** The dashboard meets WCAG 2.1 AA. It uses colour-blind-safe colours, a minimum text size of 16 pixels and full keyboard support. It displays Hindi text correctly.
- **Language.** All text follows the writing standard in Section 17.
- **Performance.** Rozmarra meets the speed targets in Section 15.3.
- **Reproducibility.** The code uses fixed random seeds and pinned package versions. One command rebuilds the demo.
- **Portability.** Rozmarra runs on Windows 10 or 11, macOS and Linux without a graphics card. The demo works without an internet connection.

## 17. Writing standard for the whole project

This standard applies to all text that a person reads in this project. This includes the README, the documents, the dashboard text, alerts, patient plans, the presentation, the video script, commit messages and code comments. Code names, such as variable and function names, may use standard technical terms.

In this project, simple language means complete, plain and professional sentences that anyone can read once and understand exactly. Judges, doctors, patients and families should all understand the text. Clarity is more important than brevity.

### 17.1 Rules

1. **Write full sentences with a subject.** Say who does what.
   - Not: "Twin simulates fast. Risk shown."
   - Instead: "The twin simulates the fast. The dashboard then shows the risk for each hour."
2. **Do not use slang, shorthand or casual verbs.** Use the precise plain word.
   - Use "low blood sugar" or "hypoglycaemia", not "hypo".
   - Use "medicines", not "meds". Use "patient", not "pt".
   - Use "approves", not "signs off".
3. **Spell out examples fully.**
   - Not: "Dose?"
   - Instead: "What dose of glimepiride does the patient take each morning?"
4. **Make labels say what the feature does,** not give it a catchy name.
   - Use "Fasting plan simulator", not "Fast Lab".
   - Use "Live fasting monitor", not "Watchtower".
5. **Be careful and honest with claims.**
   - Use "may reduce", "helps identify" and "estimated chance" instead of absolute promises.
   - Write plans in the future tense: "We will test the model on real patients whose data was not used for training. Our target is an AUROC of 0.80 or higher." Do not write "Tested on real patients" before the test has run.
   - Give every statistic a clear subject and a source: "A 2020 study of 300 adults with Type 2 Diabetes in North India found that 49% had fasted in the previous year."
6. **Do not criticise other teams or products.** Describe what Rozmarra does in positive terms.
   - Not: "Other tools ignore fasting."
   - Instead: "Rozmarra is designed for the days when patients fast."
7. **Prefer neutral, accurate verbs over dramatic ones.**
   - Use "The model estimates", not "The AI decides".
   - Use "The doctor approves", not "The doctor signs off".
8. **Make app and patient text polite and complete.**
   - Not: "Don't eat sweets!"
   - Instead: "Please eat sweets only in a small amount."
   - Not: "Sugar low – break fast"
   - Instead: "Your blood sugar is below 70 mg/dL. Please break your fast now."
   - Show patient names with their age: "Sunita Sharma, Age 54".
9. **Write subtitles as full descriptive sentences.**
   - For example: "Rozmarra helps doctors plan safer fasts for people with Type 2 Diabetes."
10. **Do not add speaker notes to slides** unless the team asks for them.

**Layout.** Full sentences are longer than fragments. Make text boxes larger, or split one long sentence into two sentences. Do not cut sentences into fragments to make them fit.

### 17.2 Words for doctors and words for patients

| Topic | Text for doctors | Text for patients |
|---|---|---|
| Low glucose | hypoglycaemia, or low glucose | low blood sugar (शुगर कम होना) |
| High glucose | hyperglycaemia, or high glucose | high blood sugar (शुगर ज़्यादा होना) |
| Glucose reading | glucose, in mg/dL | blood sugar, in mg/dL |
| The fast | the fast | the patient's own word: व्रत, उपवास or रोज़ा |
| Medicines | the generic name, for example "glimepiride" | the name on the strip with the dose, for example "Glimepiride 1 mg" |

### 17.3 Words to avoid

| Avoid | Use instead |
|---|---|
| hypo, hypos | low blood sugar (for patients), or hypoglycaemia (for doctors) |
| hyper, spike | high blood sugar, or a sharp rise in glucose |
| BG, BGL, sugars | blood glucose, or blood sugar |
| SU, OHA | sulfonylurea; oral diabetes medicine |
| pt, pts, meds, Rx | patient, patients, medicines, prescription |
| w/, w/o, approx. | with, without, about |
| ASAP | as soon as possible |
| guaranteed, prevents, 100% accurate | may reduce, helps identify, or the measured accuracy |
| AI decides, AI knows | the model estimates |
| Exclamation marks in alerts | a full stop |

### 17.4 Formats

- **Spelling.** Use Indian English, which follows British spelling, for example "hypoglycaemia", "personalised" and "colour". Library names and code keep their original spelling.
- **Units.** Always show the unit, for example "70 mg/dL", "12 beats per minute" or "15 minutes".
- **Times.** Use the 12-hour clock with am and pm, for example "4:40 pm". All times are in Indian Standard Time.
- **Dates.** Write dates in full, for example "28 October 2026".
- **Chances.** Show a percentage and a word, for example "74% (High)".
- **Large numbers.** Write "101 million", not "101M".

## 18. Ethics, safety and respect for faith

- Fasting has deep meaning for many people. Rozmarra helps people fast more safely. It never judges the decision to fast.
- Many faith traditions allow people who are unwell to delay, shorten or skip a fast. Rozmarra leaves this decision to the patient, their family, their doctor and, if they wish, their religious advisers.
- The doctor stays in control. Rozmarra suggests options, and the doctor decides and approves.
- Every plan shows the rule for breaking the fast: the patient should break the fast if blood sugar is below 70 mg/dL or above 300 mg/dL, or if they feel unwell.
- All data is open and anonymised, or synthetic. Synthetic patients are clearly labelled.
- The model has known limits. The real data comes from China and the United States, not from India. The simulated fasting data reflects the team's modelling assumptions. The model card states these limits.
- A real product would need clinical studies with Indian patients. It would also need approval as a medical device, for example from the Central Drugs Standard Control Organisation (CDSCO) in India.

## 19. Deliverables and submission checklist

The challenge requires the README to include the following items:

- the team details and the college or incubator information;
- the project title;
- the problem statement and the healthcare use case;
- the technical stack and the AI/ML model or framework details;
- a video of 15 to 20 minutes that explains and demonstrates the prototype (an unlisted YouTube video or a recorded PowerPoint presentation);
- the open-source licence details;
- an architecture diagram in PDF or PPT format; and
- a presentation in PDF or PPT format with the project details and outcome.

The challenge also gives these submission instructions:

- The folder name must follow the format "Team Name_College Name".
- The GitHub repository must be public, and the evaluation team must be able to open every file and link.
- On Unstop, the team leader submits only their name, phone number, email address and the public GitHub repository link.

The team will also add a model card, a data card and step-by-step instructions for running the demo.

## 20. Timeline

| Date | Planned outcome |
|---|---|
| Monday 12 October (evening) | The team approves this document. The team installs the tools, creates the repository and starts the dataset downloads. |
| Tuesday 13 October | The data loaders, synthetic health records, fasting templates and IDF-DAR calculator are ready. |
| Wednesday 14 October | The twin is fitted to real patients, and a fit report is ready. |
| Thursday 15 October | The synthetic fasting days, wearable signals and event labels are ready. |
| Friday 16 October | The prediction models are trained and evaluated, and the API is ready. |
| Saturday 17 October | Dashboard screens 1 to 3 work. |
| Sunday 18 October | Dashboard screens 4 to 6 and the patient plan work. The team stops adding features at the end of the day. |
| Monday 19 October | The architecture diagram, presentation, model card and data card are complete. The team records and uploads the video. |
| Tuesday 20 October | The team completes the final checks and makes the repository public. The team leader submits on Unstop by 2:00 PM IST, five hours before the 7:00 PM deadline. |

## 21. Risks and mitigations

| Risk | Effect | Mitigation |
|---|---|---|
| The team does not have enough time to finish everything. | Required items may be missing. | The team builds "Must" items first, stops adding features on 18 October, and records the video on 19 October. |
| The open data contains few real events of low blood sugar. | The real-data results for E1 may be weak. | The team reports the results honestly with confidence intervals. The team uses simulated fasting days to test E1 in more detail and explains the difference. |
| The simulated wearable responses follow the team's own assumptions. | Results on simulated data may look better than results in real life. | The team states this clearly. The team uses real CGMacros and BIG IDEAs data to check how much wearable signals add in real life. |
| The ShanghaiT2DM files are harder to read than expected, for example because some fields contain Chinese text. | The data work may be delayed. | The team uses a small translation table for medicine names. If the meal text is hard to read, the team uses the meal times with a default meal size, and the twin fits a personal meal-size factor. |
| Large downloads are slow. | The data work may be delayed. | The team downloads only the files it needs and starts the downloads on the first evening. |
| The React dashboard takes longer than planned. | The demo may be weak. | All logic stays in the Python package. If screens 1 to 3 do not work by the evening of 17 October, the team switches to a Streamlit dashboard that uses the same package. |
| The Hindi text contains errors. | Doctors and patients may lose trust. | A native Hindi speaker reviews every Hindi sentence. |
| The clinical content contains errors. | Judges and doctors may lose trust. | The team bases every threshold, plan template and medicine assumption on a cited guideline or study. No doctor or pharmacist will review the content before the submission, so the README and the model card will state this clearly. |
| Registration closes before the team registers. | The team cannot submit. | The team confirms its registration on Unstop by 13 October. |
| Some tools fail on Windows because the folder path contains spaces. | Setup may be delayed. | The team runs tools such as Synthea from a path without spaces. |

## 22. Open questions

The team answered all the open questions on 12 October 2026.

| Question | Answer |
|---|---|
| What is the team name? | The team name is NOT_SOMEONE_IMPORTANT. |
| What is the college? | The college is the Indian Institute of Technology (Indian School of Mines) Dhanbad, also known as IIT (ISM) Dhanbad. |
| Who are the members, and what are their roles? | Shivansh Gautam is the team leader and leads the digital twin and the prediction models. Aman Soni leads the data and the application. Divy Sharma leads documentation, testing and the presentation. |
| Is the team registered on Unstop? | Yes. The team is registered. |
| What will the repository be called? | The team will name the repository Rozmarra, after the project title. |
| Can a doctor or pharmacist review the clinical content before 19 October? | No. The README and the model card will state that no clinician has reviewed the clinical content. |
| Who will review the Hindi text? | Shivansh Gautam will review the Hindi text. |
| Who will present in the video, and in which language? | Shivansh Gautam will present the video in simple, clear English. |

No questions are open at present. The team will add new questions to this section as they arise.

## 23. Glossary

- **AUPRC (area under the precision–recall curve)** is a measure of how well a model finds rare events while avoiding false alerts.
- **AUROC (area under the receiver operating characteristic curve)** is a measure of how well a model separates events from non-events. A value of 0.5 means that the model is no better than chance, and a value of 1.0 means that it is perfect.
- **Balanced accuracy** is the average of sensitivity and specificity.
- **A CGM (continuous glucose monitor)** is a small sensor worn on the skin. It measures glucose every 5 to 15 minutes.
- **CYP2C9** is a liver enzyme that breaks down sulfonylureas. Some people carry gene variants that make this enzyme work more slowly.
- **A digital twin** is a computer model of one patient. It updates with the patient's data and can simulate what may happen under different choices.
- **eGFR (estimated glomerular filtration rate)** is a measure of kidney function.
- **FHIR R4** is an international standard format for health records. India's Ayushman Bharat Digital Mission also uses FHIR R4.
- **HbA1c** is a blood test that shows the average blood sugar over about three months.
- **Heart rate variability (HRV)** is the variation in time between heartbeats. It often falls when the body is under stress.
- **IDF-DAR** refers to the International Diabetes Federation and the Diabetes and Ramadan International Alliance. Together, they publish guidance on safe fasting for people with diabetes.
- **The Parkes error grid** is a chart that shows whether glucose forecast errors could lead to wrong treatment decisions.
- **RMSE (root mean square error)** is the typical size of a forecast error.
- **SGLT2 inhibitors** are a group of diabetes medicines, such as dapagliflozin and empagliflozin, that remove glucose through the urine.
- **Sensitivity** is the share of real events that the model detects in time.
- **SHAP** is a method that shows how much each input contributed to a prediction.
- **Specificity** is the share of periods without an event that the model correctly leaves without an alert.
- **Sulfonylureas** are a group of diabetes medicines, such as glimepiride, gliclazide and glibenclamide. They make the pancreas release more insulin, even when blood sugar is already low.

## 24. References

1. Anjana RM, et al. Metabolic non-communicable disease health report of India: the ICMR-INDIAB national cross-sectional study (ICMR-INDIAB-17). The Lancet Diabetes & Endocrinology, 2023. https://researcher.manipal.edu/en/publications/metabolic-non-communicable-disease-health-report-of-india-the-icm/
2. Gupta L, et al. Dietary practices during common religious fasts in people with type 2 diabetes mellitus among different religions in North India: a questionnaire-based study. US Endocrinology, 2020;16(1):36–40. https://touchendocrinology.com/diabetes/journal-articles/dietary-practices-during-common-religious-fasts-in-people-with-type-2-diabetes-mellitus-among-different-religions-in-north-india-a-questionnaire-based-study/
3. Salti I, et al. A population-based study of diabetes and its characteristics during the fasting month of Ramadan in 13 countries: results of the EPIDIAR study. Diabetes Care, 2004. Summary: https://www.clinicalcorrelations.org/2011/02/25/ramadan-fasting-and-diabetes/
4. Hassanein M, et al. Diabetes and Ramadan: Practical Guidelines 2021. International Diabetes Federation and DAR International Alliance. https://idf.org/about-diabetes/resources/diabetes-and-ramadan-practical-guidelines-2021/
5. IDF-DAR 2021 risk score table, as reproduced in the World Journal of Diabetes. https://www.wjgnet.com/1948-9358/tables/v16/i11/110007.htm
6. IDF and DAR International Alliance. Guide to a safe fast (patient leaflet), 2024. https://idf.org/media/uploads/2024/08/DAR-guide-to-safe-fast-EN.pdf
7. Battelino T, et al. Clinical targets for continuous glucose monitoring data interpretation: recommendations from the international consensus on time in range. Diabetes Care, 2019.
8. Battelino T, et al. Continuous glucose monitoring and metrics for clinical trials: an international consensus statement. The Lancet Diabetes & Endocrinology, 2023.
9. Zhao Q, et al. Chinese diabetes datasets for data-driven machine learning (ShanghaiT1DM and ShanghaiT2DM). Scientific Data, 2023;10:35. https://www.nature.com/articles/s41597-023-01940-7. Data: https://doi.org/10.6084/m9.figshare.c.6310860
10. CGMacros: a scientific dataset for personalized nutrition and diet monitoring. PhysioNet, version 1.0.0, 2025. https://physionet.org/content/cgmacros/
11. BIG IDEAs Lab Glycemic Variability and Wearable Device Data. PhysioNet, version 1.1.3, 2026. https://physionet.org/content/big-ideas-glycemic-wearable/
12. Alkhateeb M, et al. Temporal and behaviour-aware multimodal modelling for hour-ahead hypoglycaemia prediction during Ramadan fasting in type 1 diabetes. Sensors, 2026;26(8):2552. https://elmi.hbku.edu.qa/en/publications/temporal-and-behaviour-aware-multimodal-modelling-for-hour-ahead-/
13. Ragia G, et al. Presence of CYP2C9*3 allele increases risk for hypoglycemia in type 2 diabetic patients treated with sulfonylureas. Pharmacogenomics, 2009. https://www.futuremedicine.com/doi/abs/10.2217/pgs.09.96
14. Bergman RN, et al. Quantitative estimation of insulin sensitivity. American Journal of Physiology, 1979.
15. Dalla Man C, Rizza RA, Cobelli C. Meal simulation model of the glucose-insulin system. IEEE Transactions on Biomedical Engineering, 2007.
16. Synthea synthetic patient generator. https://github.com/synthetichealth/synthea
17. AI-READI dataset documentation. https://docs.aireadi.org
18. Digital Twin Challenge 2026, Unstop. https://unstop.com/hackathons/crp-digital-twin-challenge-2026-happiest-health-1757873
19. Festival dates: Sharad Navratri 2026 (https://www.indianeagle.com/traveldiary/sharad-navratri-2026-dates-puja-rituals-fasting-colours/), Karva Chauth 2026 (https://www.smartpuja.com/blog/karwa-chauth-2026-date-moonrise-puja-vidhi/) and Ramadan 2027 (https://blog.wego.com/ramadan-2027/).
20. Roquemen-Echeverri V, Mosquera-Lopez C. T2DSim AI: Hybrid Neural Digital-Twin Framework for Type 2 Diabetes. GitHub repository, 2024 to 2026, with a related article in Biocybernetics and Biomedical Engineering, 2026. https://github.com/mosqueralopez/T2DSim_AI
21. Giammarino F, et al. A machine learning model for week-ahead hypoglycemia prediction from continuous glucose monitoring data. Journal of Diabetes Science and Technology, 2024. https://doi.org/10.1177/19322968241236208. Code: https://github.com/flaviagiammarino/stanford-hypoglycemia-forecasting
