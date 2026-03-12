# Vite + React Frontend — Design Summary

**Date**: 2026-03-10
**Replaces**: `src/ui/app.py` (Streamlit, 980 lines)

## Stack

- Vite 7 + React 18 + TypeScript
- Lucide React for icons
- CSS Modules per component; CSS custom properties in `src/styles/globals.css`
- No external UI library

## Design

Warm dark amber palette: background `#0C0B09`, surface `#151410`, accent `#F5A623`.
Single-page layout: fixed 52px header, slide-in sidebar (300px), scrollable chat area,
persistent context row above input bar.

Font: JetBrains Mono (Google Fonts) for brand/monospace; system font stack for body.

## Architecture

| Layer | File | Responsibility |
|-------|------|---------------|
| API client | `src/api/client.ts` | Typed fetch with timeout + error normalization |
| Chat state | `src/hooks/useChat.ts` | useReducer, submit(), content extraction from payload |
| Agent health | `src/hooks/useAgentHealth.ts` | Parallel health polling, refresh trigger |
| Types | `src/types/index.ts` | All interfaces + `extractContent`, `extractDelegation`, `extractSpecialistFindings` |

### Key backend schema notes

- Health status values: `healthy` / `degraded` / `unhealthy` (not "unavailable")
- Response text lives in `response_card.payload.contextual_explanation` (symptom queries)
  or `response_card.payload.answer` (general queries)
- `is_symptom: bool` is sent in payload (not `query_type: string`)
- Specialist findings and delegation info are nested in `response_card.payload`

## Components

```
App
├── Header         — fixed bar, brand, 3 status pills
├── Sidebar        — slide-in, agent cards, refresh/index actions
└── main
    ├── ChatArea   — WelcomeState (empty) or message list
    │   ├── UserBubble
    │   └── AssistantBubble
    │       ├── RiskBadge, MetaBar, DelegationBadge
    │       ├── SourcesPanel (ExpandablePanel)
    │       ├── SpecialistPanel × n (ExpandablePanel)
    │       └── ReasoningChain (ExpandablePanel)
    ├── ContextRow — customer ID, scanner model, institution, location, query type toggle
    └── InputBar   — auto-resize textarea, send button, spinner during processing
```

## Dev

```bash
cd frontend && npm run dev   # http://localhost:5173
# Proxies: /api/gov → :8001, /api/hw → :8002, /api/tel → :8003
```
