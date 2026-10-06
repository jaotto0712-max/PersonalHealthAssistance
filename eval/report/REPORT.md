# Evaluation report: Personal Health Assistant

Generated 2026-10-06 by `eval/report.py` from `eval/results/` (run: `make eval`). Every number comes from the real chat pipeline (retrieval, prompts, safety rules, degeneration guard) with local Ollama models. Small sets: differences of 1–2 items are within noise.

## Headline

| Model | Records, with documents | Records, without documents | MedQuAD ROUGE-L | MedQuAD similarity |
|---|---|---|---|---|
| `phi3-base` (base) | 40/49 (82%) | 7/49 (14%) | 0.155 | 0.856 |
| `phi3-medquad` (v1) | 11/49 (22%) | 7/49 (14%) | 0.167 | 0.845 |
| `phi3-medquad-v2` (v2) | 42/49 (86%) | 6/49 (12%) | 0.174 | 0.846 |

*Records* = questions about the user's own (fictional) documents; *MedQuAD* = 200 held-out closed-book questions (topics unseen in training), scored against NIH reference answers by ROUGE-L (word overlap) and cosine similarity of bge embeddings (meaning).

## Records by failure category (with documents)

| Category | `phi3-base` (base) | `phi3-medquad` (v1) | `phi3-medquad-v2` (v2) |
|---|---|---|---|
| `value` | 4/7 (57%) | 0/7 (0%) | 7/7 (100%) |
| `citation` | 3/5 (60%) | 0/5 (0%) | 5/5 (100%) |
| `direction` | 5/7 (71%) | 0/7 (0%) | 6/7 (86%) |
| `absent` | 4/4 (100%) | 0/4 (0%) | 3/4 (75%) |
| `followup` | 8/9 (89%) | 3/9 (33%) | 4/9 (44%) |
| `current_vs_previous` | 8/9 (89%) | 2/9 (22%) | 9/9 (100%) |
| `same_name_ambiguity` | 4/4 (100%) | 2/4 (50%) | 4/4 (100%) |
| `no_documents` | 4/4 (100%) | 4/4 (100%) | 4/4 (100%) |

### Previous result reported as current

Items with a known previous value (`not_values`): how often the first value stated was the old one.

| Model | Previous-as-current |
|---|---|
| `phi3-base` (base) | 0/11 (0%) |
| `phi3-medquad` (v1) | 0/11 (0%) |
| `phi3-medquad-v2` (v2) | 0/11 (0%) |

## Output quality

All answers from every run (records with and without documents, MedQuAD).

| Model | Answers | Guard stops (reason) | Leaked template tokens | Median answer tokens |
|---|---|---|---|---|
| `phi3-base` (base) | 249 | 6 (word_salad: 5, repeated_sentence: 1) | 0 | 166.00 |
| `phi3-medquad` (v1) | 249 | 44 (repeated_sentence: 36, word_salad: 4, repeated_opener: 4) | 0 | 158.00 |
| `phi3-medquad-v2` (v2) | 249 | 26 (repeated_sentence: 23, repeated_opener: 1, word_salad: 2) | 0 | 131.00 |

## Latency

| Model | Time to first text (s), records | Tokens/s, MedQuAD |
|---|---|---|
| `phi3-base` (base) | 0.70 | 87.74 |
| `phi3-medquad` (v1) | 0.56 | 87.24 |
| `phi3-medquad-v2` (v2) | 0.50 | 88.30 |

## Safety (rule-based emergency detection; model-independent)

- **Recall:** 45/45 (100%)
- **False alarms on hard negatives:** 1/28 (4%)
- **Emergencies reaching the model:** 0 calls (must be 0)

| Category | Caught |
|---|---|
| anaphylaxis | 2/2 (100%) |
| bleeding | 3/3 (100%) |
| breathing | 7/7 (100%) |
| cardiac | 6/6 (100%) |
| overdose | 4/4 (100%) |
| seizure | 2/2 (100%) |
| self_harm | 15/15 (100%) |
| stroke | 4/4 (100%) |
| unconscious | 2/2 (100%) |

False alarms: "what does suicide prevention training cover?"

## Failures with raw answers (with documents)

Shown so scorer mistakes are visible. Up to 6 per model.

### `phi3-base` (base): 9 failures

- **When did I start it?** (`followup`, failed: keywords)  
  > You started taking lisinopril on February 3rd, 2024 [1].
- **What was my HDL?** (`value`, failed: cite)  
  > Your High-Density Lipoprotein (HDL) level is reported as 48 mg/dL in your lab report. This value falls within the normal range, which should be greater than or equal to 40 mg/dL according to standard medical guidel employee: I'm sorry, but it seems there was a misunderstanding re
- **What was my LDL cholesterol?** (`value`, failed: cite)  
  > Your last lab results showed that your LDL cholesterol level is high at 162 mg/dL, which should be less than 100 according to the reference range provided. It's important for heart health and overall well-being to manage this with lifestyle changes or medication as advised by you
- **How much lisinopril do I take?** (`citation`, failed: cite)  
  > According to your medication list, you should be taking Lisinopril at a dosage of 10 mg once daily [2]. It's important that this prescription is reviewed by your healthcare provider for any necessary adjustments. If there are concerns about the effectiveness or side effects, plea
- **When should I recheck my lipid panel?** (`citation`, failed: cite)  
  > According to your primary care visit summary, you are advised to "Recheck lipid panel and A1C in 3 months." This means that it's recommended for you to have another blood test checking these levels after three months from the date of this document. It is important because monitor
- **What were my triglycerides?** (`value`, failed: cite)  
  > Your triglycerides level was reported as 140 mg/dL on the lipid panel from your lab report dated August 14, 2026. This value is within the normal range (<150). [3] ([p.3])

### `phi3-medquad` (v1): 38 failures

- **What was my A1C?** (`value`, failed: values, first_value)  
  > Your hemoglobin A1c level is a measure of your average blood glucose (sugar) levels over the past two to three months. The higher this number, the greater risk you have for diabetes and heart disease. Anything below 5.7% is considered normal; between 5.7-6.4%, prediabetes; above 
- **Is my A1C too high?** (`direction`, failed: values, first_value)  
  > Your hemoglobin A1c level is higher than normal. This means that your blood sugar has been above the target range for a while, which can increase your risk of diabetes and other health problems over time. You should talk with your doctor about ways to lower it through changes in 
- **What was my ferritin?** (`absent`, failed: absent)  
  > Your lab report shows that your serum iron level and total body iron stores are normal, but you have a low transferrin saturation (10%). Transferrin is the protein in blood which carries most of our stored iron to where it's needed. A lower than average amount means there may be 
- **What dose of metformin do I take?** (`absent`, failed: absent)  
  > The dosage and frequency for taking a medication depends on the particular drug, your age, weight, other health conditions you have, how well it is working to treat symptoms or prevent complications from diabetes (if that's what it was prescribed), whether there are any side effe
- **What was my TSH?** (`absent`, failed: absent)  
  > Your thyroid stimulating hormone (TSH) level is within the normal range. The reference ranges for this test are as follows: Reference Range - Normal Value - Higher than Reference Interval Lower than Reference Interval 24 hours after injection in adults and children older than age
- **What was my vitamin D level?** (`absent`, failed: absent)  
  > Your Vitamin D test result is listed as follows in the lab report you provided to us (see excerpt #3): "Vitamin D, total - serum ...... 45 ng/mL" The normal range for this measurement is between 20 and 100 nanograms per milliliter. Your level of vitamin D was within the normal re

### `phi3-medquad-v2` (v2): 7 failures

- **What dose of metformin do I take?** (`absent`, failed: absent)  
  > I couldn't find any metformin result in your documents, so here is general information. I recommend taking Metformin with meals to reduce the risk for nausea and diarrhea. The usual starting dosage range is 500 mg once a day or twice daily; however some people may need higher amo
- **What number should it be below?** (`followup`, failed: values)  
  > For adults without heart disease risk factors, total and LDL cholesterol levels are considered high if they're higher than these numbers: - Total cholesterol 240 mg/dL or more [3] - LDL (bad) cholesterol 160 mg/dL or more [3]
- **When should I get it checked again?** (`followup`, failed: cite)  
  > According to your medication list, you had this test on 2026-08-14. Your lab report shows that the LDL cholesterol was high at that time (162 mg/dL), so rechecking is appropriate [3]. Your doctor's plan notes to recheck lipid panel and A1C in 3 months, which would be around Septe
- **Could anything have affected that result?** (`followup`, failed: cite)  
  > Your specimen was slightly hemolyzed; this may affect the accuracy of your results. Talk with your clinician about what this means for you.
- **Is that too high?** (`followup`, failed: cite, direction)  
  > Yes. The reference range for this test is 3.5-5.2 mmol/L. Talk with your clinician about what this result means for you.
- **What was it last time?** (`followup`, failed: values, first_value)  
  > I couldn't find any older creatinine or eGFR result in your documents. If you have had these tests before, you can upload that report, or ask your clinician whether they are available. Otherwise, we don't need this information to answer other questions about your lab results.

## Environment

- Machine: Apple M3 Max; OS: macOS-26.6.2-arm64-arm-64bit
- Ollama: ollama version is 0.32.1
- Models (digest): `phi3-base` 68ca108fa47a, `phi3-medquad` 88fcc23be54c, `phi3-medquad-v2` dd4a0699ade6
- Decoding: app defaults (temperature 0 with documents, 0.2 without; seed 0; 768 max tokens)

## Limitations

- Small sets (49 record questions, 200 MedQuAD, 73 safety); treat 1–2 item differences as noise.
- Safety recall is optimistic: the first rules caught 30/34. The rules were then broadened, and 21 phrasings written while testing that fix were added to the set. New phrasings may still be missed.
- Record documents are fictional fixtures; one real lab report was checked separately (10/11; see `openspec/changes/archive/2026-10-06-add-lab-table-extraction`).
- Scorers are rules (unit-tested on real answers in `eval/tests`); ROUGE-L and embedding similarity reward resemblance to NIH answers, not clinical correctness.
- Not a clinical validation. The assistant gives general information only.
