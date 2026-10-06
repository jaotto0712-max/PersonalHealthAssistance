## Why

The app's suggested question "What does my cholesterol result mean?", asked with no documents uploaded, produced an answer that repeated one paragraph until the length limit, with wrong medical claims and no "I can't see your results". Measured at the app's settings (temperature 0.2, 36 samples, no documents):
- **Degeneration:** `phi3-medquad-v2` looped 5/36 times; the base `phi3-base` produced word salad 2/36 times. Long free-form answers from a small 4-bit model are intermittently unstable. A larger repeat-penalty window removed the loops but caused word salad, so decoding settings only move the symptom.
- **No-documents honesty:** neither model said it couldn't see the user's results (0/12 each), despite the no-context instruction.

## What Changes

- **Degeneration guard:** the backend streams answers sentence by sentence. It stops generation when a sentence repeats, a sentence opener repeats ≥5 times, or ≥40 words arrive without punctuation. The repeated or garbled text is never shown, and the answer ends with a short note. The `done` event reports `stopped_early`.
- **Personal-question notice:** when nothing is retrieved for a first-person question, the answer starts with a fixed sentence. With no uploaded documents: "You haven't uploaded any documents yet…". With documents but no match: "I couldn't find information about this in your documents…", matching v2's training data.
- UI: no change needed. The notice arrives as text, and the stopped note is rendered by the existing markdown.

## Capabilities

### New Capabilities
- `generation-guards`: Model-independent protections on generated answers (degeneration stop, personal-question notice).

### Modified Capabilities
<!-- chat-orchestration lives in the unarchived change add-rag-chat-orchestration; behaviour is additive -->

## Impact

- New `backend/pha/chat/guard.py`; small changes in `backend/pha/chat/orchestrator.py`; tests. No new dependencies.
