# P3.28 — AI Assistant / AI Analyst / AI Optimizer

Last updated: 2026-08-07

This document defines the controlled AI layer for RADAR BOURSE. The implementation is deterministic fallback/rule-based in this environment and does not require or store LLM credentials.

## 1. Architecture Boundary

```text
Market Data
  ↓
Data Trust / Provenance
  ↓
Domain / Market Service
  ↓
Filter / Strategy / Backtest
  ↓
AI Context Builder
  ↓
AI Assistant / Analyst / Optimizer
  ↓
Structured AI Result
  ↓
API
  ↓
Existing Consumer
```

AI does not connect directly to raw providers. It receives controlled context from existing services.

## 2. Runtime Owners

| Boundary | Path | Responsibility |
|---|---|---|
| Existing explainability | `backend/app/engines/ai_explainer.py` | Existing symbol entry/exit explanation. |
| Controlled AI service | `backend/app/services/ai_service.py` | Context builder, fallback provider and structured AI results. |
| API | `backend/app/api/routes.py` | `/api/ai/assistant`, `/api/ai/analyze`, `/api/ai/optimize`. |
| Data Trust | `backend/app/core/config.py`, `market_service.data_trust_context()` | Source/trust/provenance metadata used by AI. |
| Filter/Strategy/Backtest | P3.26/P3.27 modules | Inputs that AI can explain or suggest changes for. |

## 3. Provider Model

P3.28 uses a safe provider abstraction:

```text
AIService
  ↓
AIContextBuilder
  ↓
FallbackAIProvider
```

`FallbackAIProvider` is deterministic and explicitly labelled as fallback. It must not be represented as a live external LLM.

Future external LLM providers must use environment variables and must never accept API keys or secrets from client payloads.

## 4. AI Tasks

### Assistant

Explains current market/symbol/filter/backtest context. If context is missing it returns insufficient-data warnings.

### Analyst

Produces structured observations, risk flags, evidence and conclusion for existing market/symbol context.

### Optimizer

Suggests manual improvements for filters, parameters or scenario checks. It never modifies a strategy, repository, data or orders automatically.

## 5. Safety Rules

AI output must not claim:

- guaranteed profit
- guaranteed price prediction
- guaranteed signal
- risk-free strategy
- live-market validation when data is mock/synthetic

Every result includes:

- `data_trust`
- `confidence`
- `uncertainty`
- `warnings`
- `safety`
- `evidence`

## 6. API Contract

```text
POST /api/ai/assistant
POST /api/ai/analyze
POST /api/ai/optimize
```

Input:

```json
{
  "question": "...",
  "symbol": "فملی",
  "filter_expr": "buy_power > 1.5",
  "backtest_result": {},
  "language": "fa"
}
```

Output:

```json
{
  "ok": true,
  "task": "assistant|analyst|optimizer",
  "provider": "fallback",
  "title": "...",
  "summary": "...",
  "answer": "...",
  "data_trust": {},
  "key_observations": [],
  "risk_flags": [],
  "uncertainty": [],
  "evidence": [],
  "suggestions": [],
  "confidence": 0.0,
  "safety": {},
  "warnings": []
}
```

## 7. Alpha Boundary

AI is Alpha-ready as a backend API and deterministic fallback layer. It is not a production trading advisor and it is not connected to a live LLM provider in this environment.
