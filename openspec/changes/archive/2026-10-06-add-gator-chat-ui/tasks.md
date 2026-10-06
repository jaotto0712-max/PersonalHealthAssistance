## 1. Theme foundation

- [x] 1.1 Add Tailwind theme tokens (gator-orange, gator-blue, blue-dark, neutrals, alert-red) and usage notes
- [x] 1.2 Bundle Source Sans 3 via `@fontsource` and set as base font
- [x] 1.3 Create original gator mascot SVG component and favicon
- [x] 1.4 Build layout shell: blue header with mascot + status, disclaimer banner, sidebar + main, footer with non-affiliation notice

## 2. API client

- [x] 2.1 Implement typed API client for health and documents endpoints
- [x] 2.2 Implement SSE-over-fetch chat stream parser with AbortController; unit test with mocked stream (meta/token/sources/done/error)
- [x] 2.3 Implement in-memory mock API client (documents, streamed cited answers, emergency, upload errors) selected by `VITE_MOCK_API`, with `npm run dev:mock`

## 3. Chat experience

- [x] 3.1 Implement chat state reducer (messages, streaming status, history derivation)
- [x] 3.2 Build MessageList, UserBubble, AssistantBubble (react-markdown, no raw HTML) with frame-batched token rendering
- [x] 3.3 Implement citation chip post-processing and SourcesDisclosure with highlight-on-click; separate "Related documents"
- [x] 3.4 Build Composer with Send/Stop, Enter-to-send, Shift+Enter newline, disabled state when model unavailable
- [x] 3.5 Build EmergencyAlert card (911; 988 for self_harm) rendered on `meta.emergency`
- [x] 3.6 Add New chat action and error toast for `error` events

## 4. Documents panel

- [x] 4.1 Build drag-and-drop upload zone with client-side type/size pre-check and progress
- [x] 4.2 Build document list with status badges (indexed, needs_ocr), delete, and Clear all with confirm dialog
- [x] 4.3 Make panel a slide-over drawer under 768px

## 5. Serving and quality

- [x] 5.1 Mount `frontend/dist` in FastAPI at `/` after API routes; add `make build` and `make start`
- [x] 5.2 Component tests (Vitest + RTL) for chat flow, citations, emergency card, upload errors
- [x] 5.3 Add axe accessibility test for main screen; fix contrast issues
- [x] 5.4 Verify no remote asset URLs in build (reuse foundation scan) and test with network disabled
- [x] 5.5 Capture screenshots for README and showcase
