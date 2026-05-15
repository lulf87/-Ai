# Regulation Attachment Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make regulation attachments and extracted text the actual regulation data source while keeping publication pages as metadata.

**Architecture:** Add a `RegulationAttachment` table between `RegulationRecord` and `RegulationTextSegment`; import/download files into runtime storage, calculate SHA256, extract segments, and expose a deterministic text search endpoint. Verification checks attachment evidence instead of page metadata alone.

**Tech Stack:** FastAPI, SQLModel/SQLite, existing docx/pdf extractors, React/Vite, local keyword retrieval.

---

### Task 1: Attachment Data Model And Migration

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/database.py`
- Modify: `backend/app/regulations.py`

- [x] Write failing tests for attachment-backed imports and verification gates.
- [x] Add `RegulationAttachment`.
- [x] Add `attachment_id` to `RegulationTextSegment`.
- [x] Add SQLite migrations for the new table/column.
- [x] Seed attachment records from `source_files` without treating reference files as verification evidence.

### Task 2: Attachment Import And Search APIs

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/regulations.py`
- Modify: `backend/app/storage.py`

- [x] Create attachments from file imports.
- [x] Add URL attachment import/download endpoint.
- [x] Add attachment listing endpoint.
- [x] Add text search endpoint over extracted regulation segments.
- [x] Keep web-page import as metadata/text preview, not final attachment evidence.

### Task 3: Frontend Attachment Source UI

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [x] Show attachment source counts and segment counts.
- [x] Distinguish official/uploaded/reference attachments.
- [x] Add regulation text search controls and result list.
- [x] Disable verification unless an acceptable attachment exists.

### Task 4: Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/regulation-source-audit.md`

- [x] Run backend tests.
- [x] Build frontend.
- [x] Run browser verification for attachment import/search/verify.
- [x] Run the default V0.2 browser flow if the changed surface could affect demo behavior.
