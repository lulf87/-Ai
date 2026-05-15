# Regulatory RAG Review MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hybrid keyword RAG review action that generates regulation-backed candidate findings from verified regulation attachments.

**Architecture:** A new backend service retrieves verified regulation text segments by module and keyword, asks the configured LLM provider for candidate findings, validates regulation citations against retrieved hits, and persists candidates as normal findings. The frontend adds one toolbar action and renders regulation evidence from the finding payload.

**Tech Stack:** FastAPI, SQLModel, SQLite lightweight migrations, deterministic fake LLM provider, React, TypeScript, Vite.

---

### Task 1: Backend Contract And Failing Tests

**Files:**
- Modify: `backend/tests/test_regulatory_demo.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`

- [ ] Add tests proving the endpoint only uses verified SHA-backed regulation attachments.
- [ ] Add tests proving each RAG candidate includes regulation title, locator, quote, attachment id, and SHA.
- [ ] Add tests proving the endpoint returns no candidates when no verified usable regulation source exists.
- [ ] Run the new tests and confirm they fail because the endpoint and fields do not exist yet.

### Task 2: RAG Retrieval Service

**Files:**
- Create: `backend/app/regulation_rag.py`
- Modify: `backend/app/ai_services.py`
- Modify: `backend/app/llm.py`

- [ ] Add a small retrieval dataclass for regulation hits.
- [ ] Build project query terms from project flags, master data, document text, and existing rule findings.
- [ ] Retrieve only verified regulations joined to usable attachments.
- [ ] Score segments by module match and keyword overlap; cap excerpts and result count.
- [ ] Add provider method `analyze_regulatory_rag` with a deterministic fake implementation and a JSON contract for the Codex CLI provider.
- [ ] Persist candidates as `source_type = regulatory_rag_candidate`, `review_status = pending_review`, with regulation evidence fields.

### Task 3: API And Database Migration

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/database.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`

- [ ] Add finding columns for regulation attachment id, title, filename, SHA, locator, and quote.
- [ ] Add SQLite lightweight migrations for those columns.
- [ ] Add `POST /projects/{project_id}/regulatory-rag-review`.
- [ ] Reuse `AIRiskAnalysisResponse` so frontend handling mirrors current AI analysis.

### Task 4: Frontend Flow

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] Extend the `Finding` type with regulation evidence fields and `regulatory_rag_candidate`.
- [ ] Add a `法规RAG审查` button to the risk toolbar with busy state.
- [ ] Render a `法规依据` block when regulation quote evidence exists.
- [ ] Allow pending RAG candidates to be confirmed or rejected.

### Task 5: Verification

**Files:**
- Verify only; update code if failures reveal defects.

- [ ] Run targeted backend tests for regulatory RAG.
- [ ] Run the full backend test suite.
- [ ] Run the frontend build.
- [ ] Start or refresh local backend and frontend servers.
- [ ] In a real browser, create or select a project, load sample documents, run extraction, rules, AI risk analysis, regulatory RAG review, confirm or reject at least one candidate, generate a report, and check console errors.
