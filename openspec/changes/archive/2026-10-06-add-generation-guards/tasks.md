## 1. Guard

- [x] 1.1 `pha/chat/guard.py`: sentence buffer + repeat, opener and word-salad detection
- [x] 1.2 Unit tests: repeat, opener loop, salad, normal text untouched (incl. real probe answers), split-token boundaries, flush at end

## 2. Orchestrator

- [x] 2.1 Stream through the guard; stop generation and append the note; `done.stopped_early` + reason
- [x] 2.2 Personal-question notice (empty store vs no match); tests
- [x] 2.3 Live check: 36 no-document samples with phi3-medquad-v2 through /api/chat: 0 visible loops or word salad (4 degenerate answers stopped with the note; 3 flagged by the 4-gram metric were parallel lists, checked by hand); notice 24/24 on personal questions, 0/12 on general; first text visible median 0.01 s, p90 1.9 s
