# Regulation Library Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a preset regulation library for Class II and Class III active medical device registration, plus web and docx/pdf import flows.

**Architecture:** Extend `RegulationRecord` with source, coverage, attachment file, and text-preview metadata while preserving the current rule boundary: only manually verified regulations can be cited by findings. Add focused backend helpers for seed loading, web text extraction, file import, and regulation text segments; then surface the data in the existing React app.

**Tech Stack:** FastAPI, SQLModel/SQLite, built-in `urllib`/`html.parser`, existing docx/pdf text extraction, React/Vite.

---

### Task 1: Backend Data Model And Seed Loading

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/database.py`
- Create: `backend/app/regulations.py`
- Modify: `knowledge_base/regulations_seed.json`

- [x] Add regulation source fields, source file manifest, coverage classes, and text preview.
- [x] Add a `RegulationTextSegment` model for imported regulation text.
- [x] Add lightweight SQLite migrations for the new columns.
- [x] Load preset regulations from `knowledge_base/regulations_seed.json` without overwriting user-verified records.

### Task 2: Backend Import APIs

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/storage.py`
- Modify: `backend/tests/test_regulatory_demo.py`

- [x] Add `/regulations/import/web` for URL import with source text SHA.
- [x] Add `/regulations/import/file` for docx/pdf/txt/md file import with file SHA.
- [x] Add `/regulations/{id}/segments` for traceable imported text review.
- [x] Keep verification blocked unless official URL and file SHA evidence exist.

### Task 3: Frontend Regulation Library UX

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [x] Show preset/import/manual source labels, coverage classes, modules, SHA evidence, and status.
- [x] Add separate web import and file import controls.
- [x] Keep AI summary and manual verification actions visible from each regulation row.

### Task 4: Verification

**Files:**
- Modify: `README.md`

- [x] Run backend tests.
- [x] Build frontend.
- [x] Run real browser verification for the regulation list/import flow and check console errors.
