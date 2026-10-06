## Context

The measurements are in the proposal. Every model in use degenerates sometimes on long open-ended answers, so the protection belongs in the orchestrator, applied whichever model is configured.

## Decisions

- **Sentence-level streaming** (a buffer up to `.`, `!`, `?` or a newline) lets each sentence be checked before the user sees it. The cost is that text appears a sentence at a time rather than a token at a time. That's acceptable: the first sentence usually arrives within about 1 s.
- **Normalization** for comparing sentences: lowercase, alphanumeric words only. Sentences under 5 words (e.g. "Yes.") are never treated as repeats.
- **Thresholds:** a repeated sentence stops immediately. The same 5-word opener stops at the 5th occurrence (legitimate lists rarely repeat an opener five times; v1's loops repeated one 17–20 times). A 40-word run without punctuation stops; no fixture or probe answer has a run over ~30 words.
- **Stopping** breaks out of the model stream, which closes the Ollama request (same path as a client disconnect) and saves tokens. The stopped note: "_(I stopped this answer early because it started repeating itself.)_"
- **Personal-question regex:** `\b(my|mine|am i|do i|did i|have i|should i|i have|i'm|i am)\b`, case-insensitive. The notice is decided per message from `retrieved_count == 0` and the store's chunk count.

## Risks

- [A false positive cuts off a good answer] → Conservative thresholds, unit tests on real good answers (probe outputs), and the note makes any stop visible.
- [Sentence buffering hides streaming smoothness] → The first-sentence delay is measured in the live check.
