# Regulation Attachment Knowledge Base Design

## Goal

Upgrade the regulation library from a publication-page catalog into a traceable regulation source library. Official publication pages remain metadata; downloaded attachments and extracted attachment text become the actual regulation data source.

## Scope

- Store regulation attachments as first-class records.
- Download or upload attachment files, calculate SHA256, and keep stored file paths.
- Extract attachment text into searchable segments with attachment-level traceability.
- Use attachment evidence, not publication-page metadata alone, to decide whether a regulation can be manually verified.
- Add a lightweight retrieval layer now; keep vector RAG as a later extension.

## Non-Goals

- Do not treat non-official mirror files as final regulation evidence.
- Do not claim AI-generated summaries are regulatory conclusions.
- Do not add external vector database or embedding dependencies in this step.
- Do not auto-verify a regulation only because a page URL exists.

## Data Model

`RegulationRecord` remains the top-level regulation metadata record.

`RegulationAttachment` is added as the source-file layer:

- `regulation_id`
- `filename`
- `source_url`
- `source_page_url`
- `source_type`: `official_attachment`, `uploaded_file`, `reference_attachment`, or `web_page`
- `verification_usable`
- `sha256`
- `stored_path`
- `content_type`
- `byte_size`
- `download_status`
- `download_error`
- `text_preview`
- `segment_count`

`RegulationTextSegment` is extended with `attachment_id`. This keeps every text segment traceable back to the exact attachment file and SHA.

## Retrieval Strategy

Phase 1 uses deterministic local retrieval:

- exact/keyword search over extracted text segments;
- module filters through `RegulationRecord.applicable_modules`;
- result payload includes regulation title, attachment filename, SHA, locator, and text snippet.

This is the right first layer because it is reproducible and auditable. A later RAG layer can use these same segments as the corpus for embeddings, but answer generation must still cite segment IDs and attachment SHA values.

## Verification Rules

A regulation can be marked `verified` only if:

1. it has a publication page URL, and
2. it has at least one `verification_usable` source that has been downloaded or uploaded, has a SHA256, and has extracted text segments. For announcements with attachments, this source should be the attachment. For regulations where the official page itself is the full text and no attachment exists, the saved official webpage snapshot can satisfy this source requirement.

Reference attachments from mirrors or reposts can be displayed and searched if imported, but they do not satisfy the verification gate unless manually re-imported as an accepted source.

## UI Changes

The regulation card should show:

- publication page URL;
- attachment count;
- whether attachments are official, uploaded, or reference-only;
- extracted segment count;
- search box for regulation text;
- disabled verification button until an acceptable attachment exists.

## Testing

Backend tests should cover:

- file import creates an attachment and text segments;
- imported attachment text is searchable;
- reference-only preset source files do not enable verification;
- usable attachment evidence enables verification.

Browser verification should cover:

- preset list displays attachment evidence status;
- importing a docx creates a usable attachment;
- search returns the imported text;
- verification is disabled for reference-only preset items and enabled for usable attachments.
