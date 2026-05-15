from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    registration_scenario: str
    origin_type: str = "domestic"
    application_type: str = "initial"
    device_class: str = "III"
    classification_code: str = ""
    has_software: bool = False
    is_networked: bool = False
    has_ai: bool = False
    outputs_energy: bool = False
    has_disposable_accessory: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class DocumentRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    document_type: str = Field(index=True)
    filename: str
    stored_path: str
    sha256: str = Field(index=True)
    parse_status: str = "pending"
    parse_error: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class DocumentSegment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    document_id: int = Field(index=True)
    locator: str
    text: str


class ProductMasterData(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True, unique=True)
    product_name: str = ""
    model_specifications: str = ""
    structure_composition: str = ""
    intended_use: str = ""
    use_environment: str = ""
    users: str = ""
    software_name: str = ""
    software_version: str = ""
    is_networked: bool = False
    energy_type: str = ""
    outputs_energy: bool = False
    has_disposable_accessory: bool = False
    service_life: str = ""
    tested_model: str = ""
    applicable_standards: str = ""
    updated_at: datetime = Field(default_factory=utc_now)


class RegulationRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    reference_number: str = ""
    publication_date: str = ""
    official_url: str
    attachment_filename: str = ""
    attachment_sha256: str = ""
    attachment_url: str = ""
    source_type: str = "manual"
    source_files: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    source_content_sha256: str = ""
    source_note: str = ""
    coverage_classes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    device_scope: str = ""
    applicable_modules: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    stored_path: str = ""
    text_preview: str = ""
    segment_count: int = 0
    verification_status: str = "pending"
    verified_by: str = ""
    verified_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)


class RegulationAttachment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    regulation_id: int = Field(index=True)
    filename: str
    source_url: str = ""
    source_page_url: str = ""
    source_type: str = "uploaded_file"
    verification_usable: bool = False
    sha256: str = Field(default="", index=True)
    stored_path: str = ""
    content_type: str = ""
    byte_size: int = 0
    download_status: str = "metadata_only"
    download_error: str = ""
    text_preview: str = ""
    segment_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)


class RegulationTextSegment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    regulation_id: int = Field(index=True)
    attachment_id: Optional[int] = Field(default=None, index=True)
    locator: str
    text: str
    created_at: datetime = Field(default_factory=utc_now)


class Finding(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    rule_id: str = Field(index=True)
    regulation_id: Optional[int] = Field(default=None, index=True)
    regulation_attachment_id: Optional[int] = Field(default=None, index=True)
    regulation_title: str = ""
    regulation_attachment_filename: str = ""
    regulation_attachment_sha256: str = ""
    regulation_evidence_locator: str = ""
    regulation_evidence_quote: str = ""
    risk_level: str
    title: str
    description: str
    evidence_document: str = ""
    evidence_locator: str = ""
    evidence_quote: str = ""
    possible_impact: str = ""
    recommended_action: str = ""
    confidence_status: str = "evidence_based"
    source_type: str = "rule"
    ai_rationale: str = ""
    review_status: str = "confirmed"
    created_at: datetime = Field(default_factory=utc_now)


class Report(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    filename: str
    stored_path: str
    summary: str
    created_at: datetime = Field(default_factory=utc_now)


class LLMRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: Optional[int] = Field(default=None, index=True)
    regulation_id: Optional[int] = Field(default=None, index=True)
    task_type: str = Field(index=True)
    provider: str = "fake"
    model_name: str = "demo-fake-llm"
    model_config_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    input_summary: str
    output_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    output_text: str = ""
    status: str = "completed"
    error: str = ""
    duration_ms: int = 0
    contains_sensitive_content: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class EvidenceSpan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    document_id: Optional[int] = Field(default=None, index=True)
    finding_id: Optional[int] = Field(default=None, index=True)
    master_data_field: str = Field(default="", index=True)
    filename: str = ""
    locator: str = ""
    quote: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class RegulationImpactDraft(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    regulation_id: int = Field(index=True)
    llm_run_id: Optional[int] = Field(default=None, index=True)
    summary: str = ""
    change_points: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    impacted_modules: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    suggested_rule_changes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    verification_status: str = "pending_review"
    created_at: datetime = Field(default_factory=utc_now)
