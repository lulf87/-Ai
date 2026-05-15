# Regulatory RAG Review MVP Design

## Goal

Build a hybrid keyword RAG MVP for automatic regulatory review. The feature helps find candidate registration-material risks by comparing uploaded project evidence with verified regulation source text, but it must not produce final regulatory conclusions without human review.

## Scope

- Add a project action named `法规RAG审查`.
- Use only regulations with `verification_status = verified`.
- Use only regulation attachments that have SHA, stored extracted text, `download_status = extracted`, `verification_usable = true`, and at least one text segment.
- Retrieve regulation text with deterministic keyword and module scoring. No vector database is required for this MVP.
- Create candidate findings with `source_type = regulatory_rag_candidate` and `review_status = pending_review`.
- Store both project-document evidence and regulation evidence on each finding.
- Keep existing confirm, reject, report, and finding-list workflows.

## Data Flow

1. The backend builds project queries from project flags, master data, uploaded document segments, and existing rule findings.
2. The retrieval service scores verified regulation text segments by module and keyword overlap.
3. The LLM provider receives desensitized project excerpts plus bounded regulation excerpts.
4. The provider returns candidate findings. The service validates that every regulation citation refers to a retrieved, verified source.
5. Candidate findings are persisted and shown in the frontend with a dedicated regulation evidence block.

## Evidence Rules

Each RAG candidate must carry:

- project evidence: source filename, locator, and quote;
- regulation evidence: regulation id, title, attachment id, attachment filename, attachment SHA, locator, and quote.

If no verified regulation evidence is available, the endpoint returns an empty candidate list and an LLM run record explaining that no usable verified regulation source was found.

## UI Behavior

The risk toolbar adds a `法规RAG审查` button. Candidate findings display as `法规RAG候选`; after confirmation they remain distinguishable as `法规RAG辅助`. Pending RAG candidates can be confirmed or rejected through the same controls as current AI candidates.

## Safety Boundaries

- Unverified or metadata-only regulations cannot be used as RAG evidence.
- The system must not invent missing regulation links, SHA values, or regulatory conclusions.
- RAG candidates are excluded from reports until confirmed or edited, consistent with existing AI candidate behavior.
