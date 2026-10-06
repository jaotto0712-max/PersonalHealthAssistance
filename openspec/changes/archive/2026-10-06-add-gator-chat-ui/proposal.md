## Why

The brief's fourth build phase is a chat UI served locally with document upload. The backend capabilities aren't usable or demoable without it. It should look like a University of Florida project: Gator orange and blue, a friendly gator motif. It must still respect UF trademark rules and the offline requirement (no CDN fonts or assets).

## What Changes

- Build the React + Vite + TypeScript + Tailwind app on top of the shell from `setup-project-foundation`.
- Add a chat experience: message thread, streaming assistant responses, inline `[n]` citation chips, expandable sources, stop-generation, new chat.
- Add a document panel: drag-and-drop upload with progress and validation errors, document list with status, delete one, clear all (with confirmation).
- Add safety UI: a persistent disclaimer banner, a distinct emergency alert card when the backend flags an emergency, and model/Ollama status in the header.
- Add the UF-inspired theme: design tokens for UF Orange `#FA4616` and UF Blue `#0021A5`, a self-hosted font, an original gator mascot SVG, accessible contrast, and responsive layout.
- Serve the production build from FastAPI so the whole app runs at one local address.

## Capabilities

### New Capabilities
- `chat-ui`: The browser interface for chatting, viewing sources, managing documents, and seeing safety notices.
- `uf-theme`: The UF-inspired visual identity, accessibility, and offline-asset rules for the frontend.

### Modified Capabilities
<!-- none -->

## Impact

- `frontend/` gains components, hooks, an API client, a theme, and tests (Vitest + React Testing Library).
- New frontend deps: `@fontsource/source-sans-3` (or similar), `@microsoft/fetch-event-source` or a custom SSE-over-fetch reader, `react-markdown`.
- Backend: mount the built `frontend/dist` as static files at `/`.
- Depends on `add-local-document-rag` and `add-rag-chat-orchestration` API contracts.
