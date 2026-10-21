## 1. Data

- [x] 1.1 Lab documents in the app's extraction format (current lines, flags, older-results blocks, comments, no-range tests)
- [x] 1.2 Multi-turn examples: direction, neutral, range, previous, other test, medication, plan, comment, three-turn chains, topic switch, after "couldn't find", documents arriving mid-conversation
- [x] 1.3 No-range, absent-medication, off-topic and greeting examples
- [x] 1.4 MedQuAD: remove duplicated "Key Points" summaries
- [x] 1.5 Phrasing pools and several answer wordings per kind (367 distinct follow-up questions)
- [x] 1.6 Unit tests: labels and quoted references match the excerpts; history well formed; held-out eval follow-ups never generated; previous-result phrasings retrieve older results in the app

## 2. Training

- [x] 2.1 Notebook `VERSION = 3` (v2's recorded settings) and `Modelfile.medquad-v3`
- [x] 2.2 GPU run on HiPerGator (2× L4, 904 steps, best eval loss 0.473); GGUF exported and installed as `phi3-medquad-v3`

## 3. Evaluation

- [x] 3.1 8 held-out follow-up questions (`followup_heldout`); v2 baseline: 46/57 total, 4/8 held-out (base 6/8)
- [x] 3.2 Grounding probe and `records`/`medquad` eval for v3 vs v2; acceptance check. Probe: v3 16/16, 12/12, 16/16, 3/3 (scorers now accept "doesn't include"). Records: v3 54/57 (v2 46, base 47); held-out follow-ups 8/8; no category below v2. Accepted.
- [x] 3.3 `phi3-medquad-v3` made the app default; README, model card and report updated
