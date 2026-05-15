from __future__ import annotations

import json
import re
import time
from typing import Any

from sqlmodel import Session, delete, select

from backend.app.llm import LLMProvider, LLMProviderResult, SanitizedSegment, get_llm_provider
from backend.app.master_data import extract_master_data
from backend.app.models import (
    DocumentRecord,
    DocumentSegment,
    EvidenceSpan,
    Finding,
    LLMRun,
    ProductMasterData,
    Project,
    RegulationImpactDraft,
    RegulationRecord,
    Report,
    utc_now,
)
from backend.app.reporting import reportable_findings, write_docx
from backend.app.regulation_rag import RegulationRagHit, search_verified_regulation_segments
from backend.app.schemas import FindingReview


MASTER_FIELDS = [
    "product_name",
    "model_specifications",
    "structure_composition",
    "intended_use",
    "use_environment",
    "users",
    "software_name",
    "software_version",
    "is_networked",
    "energy_type",
    "outputs_energy",
    "has_disposable_accessory",
    "service_life",
    "tested_model",
    "applicable_standards",
]

BOOLEAN_MASTER_FIELDS = {
    "is_networked",
    "outputs_energy",
    "has_disposable_accessory",
}

SENSITIVE_PATTERNS = [
    r"\b1[3-9]\d{9}\b",
    r"[\w.\-]+@[\w.\-]+\.\w+",
    r"\d{17}[\dXx]",
    r"(患者姓名|身份证|联系方式|手机号|住址|病历号)",
]


def normalize_master_field_value(field_name: str, value: Any) -> Any:
    if value in (None, ""):
        return None
    if field_name in BOOLEAN_MASTER_FIELDS:
        return normalize_bool_value(value)
    return normalize_text_value(value)


def normalize_bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, list):
        normalized_items = [
            normalize_bool_value(item)
            for item in value
            if normalize_text_value(item) not in ("", "{}")
        ]
        return any(normalized_items) if normalized_items else False
    if isinstance(value, dict):
        return any(normalize_bool_value(item) for item in value.values())
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "是", "有", "包含", "联网", "输出"}:
            return True
        if normalized in {
            "false",
            "0",
            "no",
            "n",
            "否",
            "无",
            "不含",
            "不包含",
            "不联网",
            "未联网",
            "不输出",
        }:
            return False
    return bool(value)


def normalize_text_value(value: Any) -> str:
    if isinstance(value, list):
        parts = [normalize_text_value(item) for item in value]
        return "、".join(part for part in parts if part)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def normalize_candidate_evidence(candidate: dict[str, Any]) -> str:
    quote = normalize_text_value(candidate.get("evidence_quote", ""))
    documents = split_slash_list(normalize_text_value(candidate.get("evidence_document", "")))
    quotes = split_slash_list(quote)
    if len(documents) >= 2 and len(documents) == len(quotes):
        locator = normalize_text_value(candidate.get("evidence_locator", "") or "全文")
        locators = split_slash_list(locator)
        if len(locators) != len(documents):
            locators = [locator] * len(documents)
        return "\n".join(
            f"{documents[index]}（{locators[index]}）：{quotes[index]}"
            for index in range(len(documents))
        )
    return quote


def split_slash_list(value: str) -> list[str]:
    return [
        item.strip().strip('"“”')
        for item in re.split(r"\s*/\s*", value)
        if item.strip().strip('"“”')
    ]


def ai_extract_master_data(
    session: Session,
    project_id: int,
    provider: LLMProvider | None = None,
) -> tuple[ProductMasterData, list[EvidenceSpan], LLMRun]:
    project = require_project(session, project_id)
    provider = provider or get_llm_provider()
    fallback = extract_master_data(session, project)
    segments = load_sanitized_segments(session, project_id)
    start = time.perf_counter()
    result = provider.extract_master_data(segments, master_data_dict(fallback))
    duration_ms = int((time.perf_counter() - start) * 1000)
    run = create_llm_run(
        session=session,
        task_type="extract_master_data",
        provider_result=result,
        project_id=project_id,
        input_summary=summarize_input(project_id, segments),
        duration_ms=duration_ms,
        contains_sensitive_content=contains_sensitive_segments(segments),
    )

    fields = result.output_json.get("fields", {})
    for field_name, value in fields.items():
        if field_name in MASTER_FIELDS:
            normalized_value = normalize_master_field_value(field_name, value)
            if normalized_value not in (None, ""):
                setattr(fallback, field_name, normalized_value)
    fallback.updated_at = utc_now()
    session.add(fallback)

    session.exec(
        delete(EvidenceSpan).where(
            EvidenceSpan.project_id == project_id,
            EvidenceSpan.master_data_field != "",
        )
    )
    spans = []
    for item in result.output_json.get("evidence", []):
        span = EvidenceSpan(
            project_id=project_id,
            document_id=item.get("document_id"),
            master_data_field=item.get("field_name", ""),
            filename=item.get("filename", ""),
            locator=item.get("locator", ""),
            quote=item.get("quote", ""),
        )
        session.add(span)
        spans.append(span)
    session.commit()
    session.refresh(fallback)
    session.refresh(run)
    for span in spans:
        session.refresh(span)
    return fallback, spans, run


def ai_analyze_risks(
    session: Session,
    project_id: int,
    provider: LLMProvider | None = None,
) -> tuple[list[Finding], LLMRun]:
    require_project(session, project_id)
    provider = provider or get_llm_provider()
    segments = load_sanitized_segments(session, project_id)
    start = time.perf_counter()
    result = provider.analyze_risks(segments)
    duration_ms = int((time.perf_counter() - start) * 1000)
    run = create_llm_run(
        session=session,
        task_type="analyze_risks",
        provider_result=result,
        project_id=project_id,
        input_summary=summarize_input(project_id, segments),
        duration_ms=duration_ms,
        contains_sensitive_content=contains_sensitive_segments(segments),
    )

    session.exec(
        delete(Finding).where(
            Finding.project_id == project_id,
            Finding.source_type == "llm_candidate",
            Finding.review_status == "pending_review",
        )
    )
    findings: list[Finding] = []
    for candidate in result.output_json.get("candidates", []):
        evidence_quote = normalize_candidate_evidence(candidate)
        finding = Finding(
            project_id=project_id,
            rule_id=candidate.get("rule_id", "AI-CANDIDATE"),
            risk_level=candidate.get("risk_level", "yellow"),
            title=candidate.get("title", "AI候选问题"),
            description=candidate.get("description", ""),
            evidence_document=candidate.get("evidence_document", ""),
            evidence_locator=candidate.get("evidence_locator", ""),
            evidence_quote=evidence_quote,
            possible_impact=candidate.get("possible_impact", ""),
            recommended_action=candidate.get("recommended_action", ""),
            confidence_status="ai_candidate",
            source_type="llm_candidate",
            ai_rationale=candidate.get("ai_rationale", ""),
            review_status="pending_review",
        )
        session.add(finding)
        findings.append(finding)
    session.commit()
    session.refresh(run)
    for finding in findings:
        session.refresh(finding)
    return findings, run


def regulatory_rag_review(
    session: Session,
    project_id: int,
    provider: LLMProvider | None = None,
) -> tuple[list[Finding], LLMRun]:
    require_project(session, project_id)
    provider = provider or get_llm_provider()
    segments = load_sanitized_segments(session, project_id)
    hits = search_verified_regulation_segments(session, project_id)
    start = time.perf_counter()
    if hits:
        result = provider.analyze_regulatory_rag(
            segments,
            [hit.to_payload() for hit in hits],
        )
    else:
        result = LLMProviderResult(
            output_json={
                "candidates": [],
                "retrieved_hits": 0,
                "notes": "无可用已校验法规来源，未生成法规RAG候选。",
            },
            output_text="无可用已校验法规来源，未生成法规RAG候选。",
            provider=provider.provider_name,
            model_name=provider.model_name,
            model_config={"mode": "regulatory_rag_no_verified_source"},
        )
    duration_ms = int((time.perf_counter() - start) * 1000)
    run = create_llm_run(
        session=session,
        task_type="regulatory_rag_review",
        provider_result=result,
        project_id=project_id,
        input_summary=summarize_regulatory_rag_input(project_id, segments, hits),
        duration_ms=duration_ms,
        contains_sensitive_content=contains_sensitive_segments(segments),
    )

    session.exec(
        delete(Finding).where(
            Finding.project_id == project_id,
            Finding.source_type == "regulatory_rag_candidate",
            Finding.review_status == "pending_review",
        )
    )
    findings: list[Finding] = []
    for candidate in result.output_json.get("candidates", []):
        hit = matching_regulation_hit(candidate, hits)
        if hit is None:
            continue
        evidence_quote = normalize_candidate_evidence(candidate)
        finding = Finding(
            project_id=project_id,
            rule_id=candidate.get("rule_id", "RAG-CANDIDATE"),
            regulation_id=hit.regulation_id,
            regulation_attachment_id=hit.attachment_id,
            regulation_title=hit.regulation_title,
            regulation_attachment_filename=hit.attachment_filename,
            regulation_attachment_sha256=hit.attachment_sha256,
            regulation_evidence_locator=hit.locator,
            regulation_evidence_quote=normalize_text_value(
                candidate.get("regulation_evidence_quote", "")
            )
            or hit.quote,
            risk_level=candidate.get("risk_level", "yellow"),
            title=candidate.get("title", "法规RAG候选问题"),
            description=candidate.get("description", ""),
            evidence_document=candidate.get("evidence_document", ""),
            evidence_locator=candidate.get("evidence_locator", ""),
            evidence_quote=evidence_quote,
            possible_impact=candidate.get("possible_impact", ""),
            recommended_action=candidate.get("recommended_action", ""),
            confidence_status="rag_candidate",
            source_type="regulatory_rag_candidate",
            ai_rationale=candidate.get("ai_rationale", ""),
            review_status="pending_review",
        )
        session.add(finding)
        findings.append(finding)
    session.commit()
    session.refresh(run)
    for finding in findings:
        session.refresh(finding)
    return findings, run


def review_finding(session: Session, finding_id: int, payload: FindingReview) -> Finding:
    finding = session.get(Finding, finding_id)
    if finding is None:
        raise ValueError("Finding not found")
    allowed = {"pending_review", "confirmed", "rejected", "edited"}
    if payload.review_status not in allowed:
        raise ValueError("Invalid review_status")
    for field in ["title", "description", "risk_level", "recommended_action"]:
        value = getattr(payload, field)
        if value is not None:
            setattr(finding, field, value)
    finding.review_status = payload.review_status
    session.add(finding)
    session.commit()
    session.refresh(finding)
    return finding


def summarize_regulation_impact(
    session: Session,
    regulation_id: int,
    provider: LLMProvider | None = None,
) -> RegulationImpactDraft:
    regulation = session.get(RegulationRecord, regulation_id)
    if regulation is None:
        raise ValueError("Regulation not found")
    provider = provider or get_llm_provider()
    payload = {
        "title": regulation.title,
        "reference_number": regulation.reference_number,
        "publication_date": regulation.publication_date,
        "official_url": regulation.official_url,
        "attachment_filename": regulation.attachment_filename,
        "attachment_sha256": regulation.attachment_sha256,
        "source_type": regulation.source_type,
        "source_files": regulation.source_files,
        "source_content_sha256": regulation.source_content_sha256,
        "coverage_classes": regulation.coverage_classes,
        "device_scope": regulation.device_scope,
        "applicable_modules": regulation.applicable_modules,
        "verification_status": regulation.verification_status,
        "text_preview": regulation.text_preview,
    }
    start = time.perf_counter()
    result = provider.summarize_regulation_impact(payload)
    duration_ms = int((time.perf_counter() - start) * 1000)
    run = create_llm_run(
        session=session,
        task_type="summarize_regulation_impact",
        provider_result=result,
        regulation_id=regulation_id,
        input_summary=(
            f"regulation_id={regulation_id}; title={regulation.title}; "
            f"modules={','.join(regulation.applicable_modules)}; source=official_record_metadata"
        ),
        duration_ms=duration_ms,
        contains_sensitive_content=False,
    )
    output = result.output_json
    draft = RegulationImpactDraft(
        regulation_id=regulation_id,
        llm_run_id=run.id,
        summary=output.get("summary", ""),
        change_points=output.get("change_points", []),
        impacted_modules=output.get("impacted_modules", []),
        suggested_rule_changes=output.get("suggested_rule_changes", []),
        verification_status=output.get("verification_status", "pending_review"),
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return draft


def polish_report(
    session: Session,
    report_id: int,
    provider: LLMProvider | None = None,
) -> tuple[Report, LLMRun]:
    report = session.get(Report, report_id)
    if report is None:
        raise ValueError("Report not found")
    project = require_project(session, report.project_id)
    master = session.exec(
        select(ProductMasterData).where(ProductMasterData.project_id == project.id)
    ).first()
    findings = reportable_findings(
        session.exec(select(Finding).where(Finding.project_id == project.id)).all()
    )
    provider = provider or get_llm_provider()
    start = time.perf_counter()
    result = provider.polish_report(
        {
            "project_id": project.id,
            "report_id": report_id,
            "finding_count": len(findings),
            "risk_levels": [finding.risk_level for finding in findings],
        }
    )
    duration_ms = int((time.perf_counter() - start) * 1000)
    run = create_llm_run(
        session=session,
        task_type="polish_report",
        provider_result=result,
        project_id=project.id,
        input_summary=f"project_id={project.id}; report_id={report_id}; confirmed_findings={len(findings)}",
        duration_ms=duration_ms,
        contains_sensitive_content=False,
    )
    report.summary = result.output_json.get("summary", report.summary)
    write_docx(
        path=report.stored_path,
        project=project,
        master=master,
        findings=findings,
        summary=report.summary,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    session.refresh(run)
    return report, run


def require_project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError("Project not found")
    return project


def master_data_dict(master: ProductMasterData) -> dict[str, Any]:
    return {field: getattr(master, field) for field in MASTER_FIELDS}


def load_sanitized_segments(session: Session, project_id: int) -> list[SanitizedSegment]:
    rows = session.exec(
        select(DocumentSegment, DocumentRecord)
        .join(DocumentRecord, DocumentRecord.id == DocumentSegment.document_id)
        .where(DocumentSegment.project_id == project_id)
    ).all()
    segments: list[SanitizedSegment] = []
    for segment, record in rows:
        segments.append(
            SanitizedSegment(
                document_id=record.id or 0,
                document_type=record.document_type,
                filename=record.filename,
                locator=segment.locator,
                excerpt=redact_sensitive_text(segment.text)[:500],
            )
        )
    return segments


def summarize_input(project_id: int, segments: list[SanitizedSegment]) -> str:
    docs = sorted({f"{segment.filename}({segment.document_type})" for segment in segments})
    locators = [f"{segment.filename}:{segment.locator}" for segment in segments[:20]]
    return (
        f"project_id={project_id}; input=desensitized_excerpts_only; "
        f"documents={docs}; excerpt_refs={locators}; excerpt_count={len(segments)}"
    )


def summarize_regulatory_rag_input(
    project_id: int,
    segments: list[SanitizedSegment],
    hits: list[RegulationRagHit],
) -> str:
    base = summarize_input(project_id, segments)
    hit_refs = [
        f"{hit.regulation_title}:{hit.attachment_filename}:{hit.locator}:sha={hit.attachment_sha256[:12]}"
        for hit in hits[:10]
    ]
    return f"{base}; regulation_rag_hits={len(hits)}; regulation_refs={hit_refs}"


def matching_regulation_hit(
    candidate: dict[str, Any],
    hits: list[RegulationRagHit],
) -> RegulationRagHit | None:
    regulation_id = int_or_none(candidate.get("regulation_id"))
    attachment_id = int_or_none(
        candidate.get("regulation_attachment_id") or candidate.get("attachment_id")
    )
    locator = normalize_text_value(
        candidate.get("regulation_evidence_locator") or candidate.get("locator") or ""
    )
    for hit in hits:
        if regulation_id == hit.regulation_id and attachment_id == hit.attachment_id:
            if not locator or locator == hit.locator:
                return hit
    if regulation_id is None or attachment_id is None:
        return None
    for hit in hits:
        if regulation_id == hit.regulation_id and attachment_id == hit.attachment_id:
            return hit
    return None


def int_or_none(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def redact_sensitive_text(text: str) -> str:
    redacted = text
    for pattern in SENSITIVE_PATTERNS:
        redacted = re.sub(pattern, "[已脱敏]", redacted)
    return redacted


def contains_sensitive_segments(segments: list[SanitizedSegment]) -> bool:
    return any("[已脱敏]" in segment.excerpt for segment in segments)


def create_llm_run(
    *,
    session: Session,
    task_type: str,
    provider_result,
    input_summary: str,
    duration_ms: int,
    contains_sensitive_content: bool,
    project_id: int | None = None,
    regulation_id: int | None = None,
) -> LLMRun:
    run = LLMRun(
        project_id=project_id,
        regulation_id=regulation_id,
        task_type=task_type,
        provider=provider_result.provider,
        model_name=provider_result.model_name,
        model_config_json=provider_result.model_config,
        input_summary=input_summary,
        output_json=provider_result.output_json,
        output_text=provider_result.output_text,
        status="completed",
        duration_ms=duration_ms,
        contains_sensitive_content=contains_sensitive_content,
    )
    session.add(run)
    session.flush()
    return run
