from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
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


class ProjectRead(ProjectCreate):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DocumentRead(BaseModel):
    id: int
    project_id: int
    document_type: str
    filename: str
    sha256: str
    parse_status: str
    parse_error: str
    model_config = ConfigDict(from_attributes=True)


class ProductMasterDataPatch(BaseModel):
    product_name: Optional[str] = None
    model_specifications: Optional[str] = None
    structure_composition: Optional[str] = None
    intended_use: Optional[str] = None
    use_environment: Optional[str] = None
    users: Optional[str] = None
    software_name: Optional[str] = None
    software_version: Optional[str] = None
    is_networked: Optional[bool] = None
    energy_type: Optional[str] = None
    outputs_energy: Optional[bool] = None
    has_disposable_accessory: Optional[bool] = None
    service_life: Optional[str] = None
    tested_model: Optional[str] = None
    applicable_standards: Optional[str] = None


class ProductMasterDataRead(ProductMasterDataPatch):
    id: int
    project_id: int
    model_config = ConfigDict(from_attributes=True)


class RegulationCreate(BaseModel):
    title: str
    reference_number: str = ""
    publication_date: str = ""
    official_url: str
    attachment_filename: str = ""
    attachment_sha256: str = ""
    attachment_url: str = ""
    source_type: str = "manual"
    source_files: list[dict] = Field(default_factory=list)
    source_content_sha256: str = ""
    source_note: str = ""
    coverage_classes: list[str] = Field(default_factory=list)
    device_scope: str = ""
    applicable_modules: list[str] = Field(default_factory=list)


class RegulationWebImport(BaseModel):
    url: str
    title: str = ""
    reference_number: str = ""
    publication_date: str = ""
    applicable_modules: list[str] = Field(default_factory=list)
    coverage_classes: list[str] = Field(default_factory=lambda: ["II", "III"])
    device_scope: str = "II类和III类有源医疗器械注册"


class RegulationAttachmentImport(BaseModel):
    url: str
    filename: str = ""
    source_type: str = "official_attachment"
    verification_usable: bool = True


class RegulationVerify(BaseModel):
    verification_status: str
    verified_by: str


class RegulationRead(RegulationCreate):
    id: int
    stored_path: str = ""
    text_preview: str = ""
    segment_count: int = 0
    verification_status: str
    verified_by: str
    verified_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class RegulationTextSegmentRead(BaseModel):
    id: int
    regulation_id: int
    attachment_id: Optional[int] = None
    locator: str
    text: str
    model_config = ConfigDict(from_attributes=True)


class RegulationAttachmentRead(BaseModel):
    id: int
    regulation_id: int
    filename: str
    source_url: str
    source_page_url: str
    source_type: str
    verification_usable: bool
    sha256: str
    content_type: str
    byte_size: int
    download_status: str
    download_error: str
    text_preview: str
    segment_count: int
    model_config = ConfigDict(from_attributes=True)


class RegulationSearchResult(BaseModel):
    regulation_id: int
    regulation_title: str
    attachment_id: Optional[int] = None
    attachment_filename: str = ""
    attachment_sha256: str = ""
    locator: str
    snippet: str


class RegulationAttachmentDownloadItem(BaseModel):
    regulation_id: int
    regulation_title: str
    attachment_id: int
    filename: str
    source_type: str
    status: str
    detail: str = ""
    segment_count: int = 0


class RegulationAttachmentBulkDownloadResponse(BaseModel):
    total: int
    downloaded: int
    skipped: int
    failed: int
    results: list[RegulationAttachmentDownloadItem]


class FindingRead(BaseModel):
    id: int
    project_id: int
    rule_id: str
    regulation_id: Optional[int]
    regulation_attachment_id: Optional[int]
    regulation_title: str
    regulation_attachment_filename: str
    regulation_attachment_sha256: str
    regulation_evidence_locator: str
    regulation_evidence_quote: str
    risk_level: str
    title: str
    description: str
    evidence_document: str
    evidence_locator: str
    evidence_quote: str
    possible_impact: str
    recommended_action: str
    owner: str
    workload: str
    category: str
    confidence_status: str
    source_type: str
    ai_rationale: str
    review_status: str
    model_config = ConfigDict(from_attributes=True)


class FindingReview(BaseModel):
    review_status: str
    title: Optional[str] = None
    description: Optional[str] = None
    risk_level: Optional[str] = None
    recommended_action: Optional[str] = None


class RunChecksResponse(BaseModel):
    findings: list[FindingRead]


class ConsistencyMatrixCell(BaseModel):
    document_id: int
    document_type: str
    filename: str
    value: str
    quote: str


class ConsistencyMatrixRow(BaseModel):
    field: str
    label: str
    status: str
    values_by_document: list[ConsistencyMatrixCell]


class DashboardAction(BaseModel):
    title: str
    owner: str
    action: str
    workload: str


class DashboardRead(BaseModel):
    project_id: int
    readiness_score: int
    risk_counts: dict[str, int]
    category_counts: dict[str, int]
    owner_counts: dict[str, int]
    major_breakpoints: list[FindingRead]
    next_actions: list[DashboardAction]
    boss_summary: str


class ReportRead(BaseModel):
    id: int
    project_id: int
    filename: str
    summary: str
    model_config = ConfigDict(from_attributes=True)


class LLMRunRead(BaseModel):
    id: int
    project_id: Optional[int] = None
    regulation_id: Optional[int] = None
    task_type: str
    provider: str
    model_name: str
    input_summary: str
    output_json: dict
    output_text: str
    status: str
    error: str
    duration_ms: int
    contains_sensitive_content: bool
    model_config = ConfigDict(from_attributes=True)


class EvidenceSpanRead(BaseModel):
    id: int
    project_id: int
    document_id: Optional[int] = None
    finding_id: Optional[int] = None
    field_name: str = Field(alias="master_data_field", serialization_alias="field_name")
    filename: str
    locator: str
    quote: str
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AIExtractMasterDataResponse(BaseModel):
    master_data: ProductMasterDataRead
    evidence_spans: list[EvidenceSpanRead]
    llm_run: LLMRunRead


class AIRiskAnalysisResponse(BaseModel):
    findings: list[FindingRead]
    llm_run: LLMRunRead


class RegulationImpactDraftRead(BaseModel):
    id: int
    regulation_id: int
    llm_run_id: Optional[int]
    summary: str
    change_points: list[str]
    impacted_modules: list[str]
    suggested_rule_changes: list[str]
    verification_status: str
    model_config = ConfigDict(from_attributes=True)


class ReportPolishResponse(BaseModel):
    report: ReportRead
    llm_run: LLMRunRead
