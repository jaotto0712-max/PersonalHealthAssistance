## Context

This is the UI for a single local user. The audience is a patient-like user and course evaluators at a showcase, so the demo matters. The SSE chat contract and document endpoints are defined in earlier changes. Everything is served from localhost, with no remote assets.

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │ UF Blue header:  [gator svg] Personal Health Assistant   ● Model OK │
 ├──────────────────────────────────────────────────────────────────────┤
 │ ⚠ General info only — not medical advice. Emergency? Call 911.      │ ← orange-tinted banner
 ├───────────────┬──────────────────────────────────────────────────────┤
 │ MY DOCUMENTS  │                                                      │
 │ ┌───────────┐ │   🧑 Is my LDL high?                                 │
 │ │ drop files│ │                                                      │
 │ └───────────┘ │   🐊 Your LDL was 162 mg/dL [1], which is …          │
 │ labs.pdf  ✓ 🗑│      ▾ Sources (1)                                    │
 │ visit.txt ✓ 🗑│        [1] labs.pdf · p.2 · "LDL 162 mg/dL…"         │
 │ scan.pdf  ⚠ 🗑│                                                      │
 │ (needs OCR)   │  ┌────────────────────────────────────┐ [■ Stop]    │
 │ [Clear all]   │  │ Ask about your health…             │ [Send ▶]    │
 └───────────────┴──┴────────────────────────────────────┴─────────────┘
   mobile (<768px): documents panel becomes a slide-over drawer
```

## Goals / Non-Goals

**Goals:**
- A polished, recognizably "Gator" demo.
- Clear provenance for every answer.
- Safety notices impossible to miss.
- Accessible (WCAG AA).

**Non-Goals:**
- Accounts, chat persistence across reloads, or multi-conversation history (a possible stretch goal using localStorage).
- Dark mode (a nice-to-have, kept out of scope).
- Official UF logos, wordmarks, or the licensed "Gator head" mark.

## Decisions

**State: plain React (useReducer + context) instead of Redux or Zustand.** The app has a single page with two state slices (chat, documents). TanStack Query for the document list is optional. Start without it.

**SSE over fetch (POST).** The native `EventSource` only supports GET. Use `@microsoft/fetch-event-source` or a small `ReadableStream` parser. An `AbortController` powers the Stop button.

**Answer rendering:** Use `react-markdown` (no raw HTML) for model output. A post-processor turns `[n]` into clickable chips that scroll to and highlight the matching source. Streaming text renders progressively, and sources appear when the `sources` event arrives.

**Theme tokens (Tailwind `theme.extend.colors`):**
- `gator-orange #FA4616`, `gator-blue #0021A5`
- `blue-dark #002657` (UF secondary dark blue)
- neutrals
- `alert-red` for emergencies

Contrast rule: orange on white is about 3.3:1, which passes AA only for large text and UI components. So body text is never orange. Orange is used for buttons with white bold text ≥14px bold or 18px (an accepted large-text exception), and also for borders, icons, and accents. Blue on white is about 10:1 and safe for text.

**Font:** UF's brand typeface (Gentona) is licensed, so we use **Source Sans 3**, a free substitute in a similar humanist style, via `@fontsource`. It is bundled and works offline.

**Mascot:** An original, simple, friendly gator SVG drawn for this project (not UF's trademarked logo). The footer reads "UF AI Passport — Capstone Project. Not affiliated with or endorsed by UF Health." This avoids trademark issues while keeping the look.

**Emergency card:** When `meta.emergency` is true, render a red-bordered card with a large "Call 911" (and "Call or text 988" for self_harm) instead of the normal bubble. It is not styled as a chat message, so it reads as a system alert.

**Production serving:** `npm run build` produces `frontend/dist`. FastAPI mounts it with `StaticFiles(html=True)` at `/` after the `/api` routes. Then `make start` runs a single process at `http://127.0.0.1:8000`.

**Mock API for UI-first development.** The UI is built before `add-local-document-rag` and `add-rag-chat-orchestration` exist. `src/api/` therefore exposes one `ApiClient` interface with two implementations:
- `httpClient`: the real endpoints
- `mockClient`: in-memory documents, scripted streaming answers with citations, emergency detection for a few phrases, and simulated upload errors

`VITE_MOCK_API=true` (`npm run dev:mock`) selects the mock. The default build always uses the real client. The types in `src/api/types.ts` mirror the contracts in those two changes' specs:
- Document record: `{id, filename, size_bytes, pages, chunks, status: "indexed"|"needs_ocr", uploaded_at}`
- Health: `{status, version, llm?: "ok"|"unavailable"|"model_missing", model?}`
- SSE events: `meta`/`token`/`sources`/`done`/`error`

Alternative: MSW (Mock Service Worker). Rejected because it adds a service worker and a dependency to intercept only a handful of calls.

**Testing:** Vitest + React Testing Library for components and SSE parsing (with a mocked stream). Playwright for one end-to-end smoke test against the backend with FakeLLM. It's optional and fits better in `add-evaluation-suite`.

## Risks / Trade-offs

- [Orange accessibility] → Token usage rules above. Run an axe check in tests.
- [Perceived UF endorsement] → No official marks, plus a footer disclaimer of non-affiliation.
- [Markdown injection from model output or document snippets] → react-markdown without `rehype-raw`. Snippets render as text.
- [Long streaming answers cause jank] → Batch token appends per animation frame.

## Open Questions

- Should the chat thread survive a page reload (sessionStorage)? Default is no, for privacy. It's cleared on reload.
