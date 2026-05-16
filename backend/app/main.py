from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import AsyncIterator
import shutil

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlmodel import Session, select

from backend.app.config import BASE_DIR, UPLOAD_DIR
from backend.app.database import get_session, init_db
from backend.app.llm import validate_llm_startup_configuration
from backend.app.ai_services import (
    ai_analyze_risks,
    ai_extract_master_data,
    polish_report,
    regulatory_rag_review,
    review_finding,
    summarize_regulation_impact,
)
from backend.app.extractors import extract_text_segments
from backend.app.master_data import extract_master_data
from backend.app.models import (
    DocumentRecord,
    DocumentSegment,
    Finding,
    ProductMasterData,
    Project,
    RegulationAttachment,
    RegulationRecord,
    RegulationTextSegment,
    Report,
    LLMRun,
)
from backend.app import regulations as regulation_services
from backend.app.reporting import create_report
from backend.app.rules import run_rules
from backend.app.schemas import (
    DocumentRead,
    AIExtractMasterDataResponse,
    AIRiskAnalysisResponse,
    FindingRead,
    FindingReview,
    LLMRunRead,
    ProductMasterDataPatch,
    ProductMasterDataRead,
    ProjectCreate,
    ProjectRead,
    RegulationImpactDraftRead,
    RegulationAttachmentImport,
    RegulationAttachmentBulkDownloadResponse,
    RegulationAttachmentDownloadItem,
    RegulationAttachmentRead,
    RegulationCreate,
    RegulationRead,
    RegulationSearchResult,
    RegulationTextSegmentRead,
    RegulationVerify,
    RegulationWebImport,
    ReportPolishResponse,
    ReportRead,
    RunChecksResponse,
)
from backend.app.storage import safe_suffix, save_regulation_bytes, save_regulation_upload, save_upload, sha256_file


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    validate_llm_startup_configuration()
    yield


app = FastAPI(title="注册资料 AI 辅助检查 V0.1", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
SUPPORTED_REGULATION_SUFFIXES = {".doc", ".docx", ".pdf", ".txt", ".md"}
SUPPORTED_SAMPLE_SUFFIXES = {".doc", ".docx", ".pdf", ".txt", ".md"}
SAMPLE_DOCUMENT_SETS = {
    "golden-microwave": BASE_DIR / "samples" / "golden" / "microwave_ablation",
    "local-pfe-catheter": BASE_DIR / "samples" / "local_reports" / "pfe_catheter",
}


def frontend_help_page() -> Response:
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="zh-CN">
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>注册资料预审 Demo</title>
            <style>
              body {
                margin: 0;
                min-height: 100vh;
                display: grid;
                place-items: center;
                font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
                background: #f5f6f1;
                color: #223136;
              }
              main {
                width: min(720px, calc(100vw - 32px));
                background: #fff;
                border: 1px solid #d8ddd8;
                border-radius: 8px;
                padding: 28px;
              }
              h1 { margin-top: 0; font-size: 24px; }
              code {
                background: #eef3f0;
                border-radius: 5px;
                padding: 2px 6px;
              }
              a { color: #246c7a; font-weight: 700; }
            </style>
          </head>
          <body>
            <main>
              <h1>注册资料预审 Demo 后端已启动</h1>
              <p>如果你正在开发前端，请另开终端运行：</p>
              <p><code>cd frontend && npm run dev -- --host 127.0.0.1 --port 5173</code></p>
              <p>然后打开 <a href="http://127.0.0.1:5173/">http://127.0.0.1:5173/</a>。</p>
              <p>如果希望只通过 <code>8000</code> 打开完整页面，请先运行：</p>
              <p><code>cd frontend && npm run build</code></p>
              <p>API 健康检查：<a href="/health">/health</a></p>
            </main>
          </body>
        </html>
        """
    )


@app.get("/", include_in_schema=False)
def frontend_entrypoint() -> Response:
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return frontend_help_page()


@app.get("/assets/{asset_path:path}", include_in_schema=False)
def frontend_asset(asset_path: str) -> Response:
    asset_file = FRONTEND_DIST / "assets" / asset_path
    if not asset_file.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(asset_file)


@app.get("/favicon.svg", include_in_schema=False)
def frontend_favicon() -> Response:
    favicon_path = FRONTEND_DIST / "favicon.svg"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    source_favicon = BASE_DIR / "frontend" / "public" / "favicon.svg"
    if source_favicon.exists():
        return FileResponse(source_favicon)
    raise HTTPException(status_code=404, detail="Favicon not found")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/projects", response_model=ProjectRead)
def create_project(payload: ProjectCreate, session: Session = Depends(get_session)) -> Project:
    project = Project(**payload.model_dump())
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@app.get("/projects", response_model=list[ProjectRead])
def list_projects(session: Session = Depends(get_session)) -> list[Project]:
    return session.exec(select(Project).order_by(Project.id.desc())).all()


@app.post("/projects/{project_id}/documents", response_model=DocumentRead)
def upload_document(
    project_id: int,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> DocumentRecord:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    stored_path, digest = save_upload(project_id, file)
    record = DocumentRecord(
        project_id=project_id,
        document_type=document_type,
        filename=file.filename or stored_path.name,
        stored_path=str(stored_path),
        sha256=digest,
        parse_status="pending",
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    try:
        segments = extract_text_segments(stored_path)
        for locator, text in segments:
            session.add(
                DocumentSegment(
                    project_id=project_id,
                    document_id=record.id,
                    locator=locator,
                    text=text,
                )
            )
        record.parse_status = "parsed"
        record.parse_error = ""
    except Exception as exc:
        record.parse_status = "failed"
        record.parse_error = str(exc)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@app.post("/projects/{project_id}/sample-documents/{sample_key}", response_model=list[DocumentRead])
def load_sample_documents(
    project_id: int,
    sample_key: str,
    session: Session = Depends(get_session),
) -> list[DocumentRecord]:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    sample_dir = SAMPLE_DOCUMENT_SETS.get(sample_key)
    if sample_dir is None:
        raise HTTPException(status_code=404, detail="Sample document set not found")
    if not sample_dir.is_dir():
        raise HTTPException(status_code=404, detail="Sample document set not found")

    records = []
    for sample, document_type in sample_documents(sample_dir):
        record = create_document_record_from_path(project_id, document_type, sample, session)
        records.append(record)
    if not records:
        raise HTTPException(status_code=404, detail="Sample document set has no supported documents")
    return records


def sample_documents(sample_dir: Path) -> list[tuple[Path, str]]:
    documents: list[tuple[Path, str]] = []
    for sample in sorted(sample_dir.iterdir()):
        prefix, separator, document_type = sample.stem.partition("_")
        if (
            not sample.is_file()
            or sample.suffix.lower() not in SUPPORTED_SAMPLE_SUFFIXES
            or separator != "_"
            or not prefix.isdigit()
            or not document_type
        ):
            continue
        documents.append((sample, document_type))
    return documents


def create_document_record_from_path(
    project_id: int,
    document_type: str,
    source_path: Path,
    session: Session,
) -> DocumentRecord:
    project_dir = UPLOAD_DIR / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256_file(source_path)
    existing = session.exec(
        select(DocumentRecord)
        .where(DocumentRecord.project_id == project_id)
        .where(DocumentRecord.document_type == document_type)
        .where(DocumentRecord.filename == source_path.name)
        .where(DocumentRecord.sha256 == digest)
        .order_by(DocumentRecord.id)
    ).first()
    if existing is not None:
        return existing

    stored_path = project_dir / f"{digest}{safe_suffix(source_path.name)}"
    if not stored_path.exists():
        shutil.copy2(source_path, stored_path)
    record = DocumentRecord(
        project_id=project_id,
        document_type=document_type,
        filename=source_path.name,
        stored_path=str(stored_path),
        sha256=digest,
        parse_status="pending",
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    try:
        segments = extract_text_segments(stored_path)
        for locator, text in segments:
            session.add(
                DocumentSegment(
                    project_id=project_id,
                    document_id=record.id,
                    locator=locator,
                    text=text,
                )
            )
        record.parse_status = "parsed"
        record.parse_error = ""
    except Exception as exc:
        record.parse_status = "failed"
        record.parse_error = str(exc)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@app.get("/projects/{project_id}/documents", response_model=list[DocumentRead])
def list_documents(project_id: int, session: Session = Depends(get_session)) -> list[DocumentRecord]:
    return session.exec(select(DocumentRecord).where(DocumentRecord.project_id == project_id)).all()


@app.post("/projects/{project_id}/extract-master-data", response_model=ProductMasterDataRead)
def extract_master(project_id: int, session: Session = Depends(get_session)) -> ProductMasterData:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return extract_master_data(session, project)


@app.post("/projects/{project_id}/ai/extract-master-data", response_model=AIExtractMasterDataResponse)
def ai_extract_master(
    project_id: int,
    session: Session = Depends(get_session),
) -> AIExtractMasterDataResponse:
    try:
        master, spans, run = ai_extract_master_data(session, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AIExtractMasterDataResponse(
        master_data=ProductMasterDataRead.model_validate(master),
        evidence_spans=[span for span in spans],
        llm_run=LLMRunRead.model_validate(run),
    )


@app.get("/projects/{project_id}/master-data", response_model=ProductMasterDataRead)
def get_master_data(project_id: int, session: Session = Depends(get_session)) -> ProductMasterData:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    master = session.exec(
        select(ProductMasterData).where(ProductMasterData.project_id == project_id)
    ).first()
    if master is None:
        master = ProductMasterData(project_id=project_id)
        session.add(master)
        session.commit()
        session.refresh(master)
    return master


@app.patch("/projects/{project_id}/master-data", response_model=ProductMasterDataRead)
def patch_master_data(
    project_id: int,
    payload: ProductMasterDataPatch,
    session: Session = Depends(get_session),
) -> ProductMasterData:
    master = session.exec(
        select(ProductMasterData).where(ProductMasterData.project_id == project_id)
    ).first()
    if master is None:
        master = ProductMasterData(project_id=project_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(master, field, value)
    master.updated_at = datetime.now(timezone.utc)
    session.add(master)
    session.commit()
    session.refresh(master)
    return master


@app.post("/projects/{project_id}/run-checks", response_model=RunChecksResponse)
def run_checks(project_id: int, session: Session = Depends(get_session)) -> RunChecksResponse:
    try:
        findings = run_rules(session, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RunChecksResponse(findings=[FindingRead.model_validate(finding) for finding in findings])


@app.post("/projects/{project_id}/ai/analyze-risks", response_model=AIRiskAnalysisResponse)
def ai_risk_analysis(
    project_id: int,
    session: Session = Depends(get_session),
) -> AIRiskAnalysisResponse:
    try:
        findings, run = ai_analyze_risks(session, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AIRiskAnalysisResponse(
        findings=[FindingRead.model_validate(finding) for finding in findings],
        llm_run=LLMRunRead.model_validate(run),
    )


@app.post("/projects/{project_id}/regulatory-rag-review", response_model=AIRiskAnalysisResponse)
def run_regulatory_rag_review(
    project_id: int,
    session: Session = Depends(get_session),
) -> AIRiskAnalysisResponse:
    try:
        findings, run = regulatory_rag_review(session, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AIRiskAnalysisResponse(
        findings=[FindingRead.model_validate(finding) for finding in findings],
        llm_run=LLMRunRead.model_validate(run),
    )


@app.get("/projects/{project_id}/findings", response_model=list[FindingRead])
def list_findings(project_id: int, session: Session = Depends(get_session)) -> list[Finding]:
    return session.exec(select(Finding).where(Finding.project_id == project_id)).all()


@app.get("/projects/{project_id}/llm-runs", response_model=list[LLMRunRead])
def list_project_llm_runs(project_id: int, session: Session = Depends(get_session)) -> list[LLMRun]:
    return session.exec(
        select(LLMRun).where(LLMRun.project_id == project_id).order_by(LLMRun.id.desc())
    ).all()


@app.post("/findings/{finding_id}/review", response_model=FindingRead)
def review_ai_finding(
    finding_id: int,
    payload: FindingReview,
    session: Session = Depends(get_session),
) -> Finding:
    try:
        return review_finding(session, finding_id, payload)
    except ValueError as exc:
        message = str(exc)
        status = 400 if "Invalid" in message else 404
        raise HTTPException(status_code=status, detail=message) from exc


@app.post("/projects/{project_id}/reports", response_model=ReportRead)
def generate_report(project_id: int, session: Session = Depends(get_session)) -> Report:
    try:
        return create_report(session, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/reports/{report_id}/download")
def download_report(project_id: int, report_id: int, session: Session = Depends(get_session)) -> FileResponse:
    report = session.get(Report, report_id)
    if report is None or report.project_id != project_id:
        raise HTTPException(status_code=404, detail="Report not found")
    path = Path(report.stored_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report file missing")
    return FileResponse(path, filename=report.filename)


@app.post("/reports/{report_id}/ai/polish", response_model=ReportPolishResponse)
def ai_polish_report(
    report_id: int,
    session: Session = Depends(get_session),
) -> ReportPolishResponse:
    try:
        report, run = polish_report(session, report_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReportPolishResponse(
        report=ReportRead.model_validate(report),
        llm_run=LLMRunRead.model_validate(run),
    )


@app.post("/regulations", response_model=RegulationRead)
def create_regulation(
    payload: RegulationCreate,
    session: Session = Depends(get_session),
) -> RegulationRecord:
    regulation = RegulationRecord(**payload.model_dump())
    session.add(regulation)
    session.commit()
    session.refresh(regulation)
    return regulation


@app.get("/regulations", response_model=list[RegulationRead])
def list_regulations(session: Session = Depends(get_session)) -> list[RegulationRecord]:
    return session.exec(select(RegulationRecord).order_by(RegulationRecord.id.desc())).all()


@app.get("/regulations/search", response_model=list[RegulationSearchResult])
def search_regulations(
    query: str,
    module: str = "",
    session: Session = Depends(get_session),
) -> list[RegulationSearchResult]:
    needle = query.strip()
    if not needle:
        return []
    records = {
        record.id: record
        for record in session.exec(select(RegulationRecord)).all()
        if not module or module in record.applicable_modules
    }
    attachments = {
        attachment.id: attachment
        for attachment in session.exec(select(RegulationAttachment)).all()
    }
    results: list[RegulationSearchResult] = []
    for segment in session.exec(select(RegulationTextSegment).order_by(RegulationTextSegment.id)).all():
        regulation = records.get(segment.regulation_id)
        if regulation is None or needle not in segment.text:
            continue
        attachment = attachments.get(segment.attachment_id or 0)
        results.append(
            RegulationSearchResult(
                regulation_id=regulation.id or 0,
                regulation_title=regulation.title,
                attachment_id=attachment.id if attachment else None,
                attachment_filename=attachment.filename if attachment else "",
                attachment_sha256=attachment.sha256 if attachment else "",
                locator=segment.locator,
                snippet=_snippet(segment.text, needle),
            )
        )
        if len(results) >= 20:
            break
    return results


@app.get("/regulations/{regulation_id}/attachments", response_model=list[RegulationAttachmentRead])
def list_regulation_attachments(
    regulation_id: int,
    session: Session = Depends(get_session),
) -> list[RegulationAttachment]:
    regulation = session.get(RegulationRecord, regulation_id)
    if regulation is None:
        raise HTTPException(status_code=404, detail="Regulation not found")
    return session.exec(
        select(RegulationAttachment)
        .where(RegulationAttachment.regulation_id == regulation_id)
        .order_by(RegulationAttachment.id)
    ).all()


@app.get("/regulations/{regulation_id}/segments", response_model=list[RegulationTextSegmentRead])
def list_regulation_segments(
    regulation_id: int,
    session: Session = Depends(get_session),
) -> list[RegulationTextSegment]:
    regulation = session.get(RegulationRecord, regulation_id)
    if regulation is None:
        raise HTTPException(status_code=404, detail="Regulation not found")
    return session.exec(
        select(RegulationTextSegment)
        .where(RegulationTextSegment.regulation_id == regulation_id)
        .order_by(RegulationTextSegment.id)
    ).all()


def _download_and_extract_attachment(
    session: Session,
    regulation: RegulationRecord,
    attachment: RegulationAttachment,
) -> RegulationAttachment:
    if not attachment.source_url:
        raise ValueError("Attachment has no source URL to download")
    downloaded = regulation_services.download_attachment(
        attachment.source_url,
        attachment.filename,
        referer=attachment.source_page_url or regulation.official_url,
    )
    if safe_suffix(downloaded.filename) not in SUPPORTED_REGULATION_SUFFIXES:
        raise ValueError("Only doc, docx, pdf, txt, and md regulation attachments can be extracted")
    path, digest = save_regulation_bytes(downloaded.filename, downloaded.content)
    if attachment.sha256 and attachment.sha256 != digest:
        raise ValueError("Downloaded attachment SHA does not match the seeded official SHA")
    segments = extract_text_segments(path)
    for segment in session.exec(
        select(RegulationTextSegment).where(
            RegulationTextSegment.attachment_id == attachment.id
        )
    ).all():
        session.delete(segment)
    attachment.filename = downloaded.filename
    attachment.sha256 = digest
    attachment.stored_path = str(path)
    attachment.content_type = downloaded.content_type
    attachment.byte_size = len(downloaded.content)
    attachment.download_status = "downloaded"
    attachment.download_error = ""
    session.add(attachment)
    regulation_services.write_regulation_segments(session, regulation, segments, attachment)
    return attachment


def _download_and_extract_web_page_source(
    session: Session,
    regulation: RegulationRecord,
) -> RegulationAttachment:
    if not regulation.official_url:
        raise ValueError("Regulation has no official URL to download")
    source = regulation_services.fetch_web_regulation(regulation.official_url)
    content = source.content or source.text.encode("utf-8")
    filename = f"regulation-{regulation.id or 'source'}-official-page.html"
    path, digest = save_regulation_bytes(filename, content)
    attachment = session.exec(
        select(RegulationAttachment).where(
            RegulationAttachment.regulation_id == regulation.id,
            RegulationAttachment.source_type == "web_page",
            RegulationAttachment.source_url == regulation.official_url,
        )
    ).first()
    if attachment is None:
        attachment = regulation_services.create_attachment(
            session,
            regulation,
            filename=filename,
            source_url=regulation.official_url,
            source_page_url=regulation.official_url,
            source_type="web_page",
            verification_usable=True,
            sha256=source.content_sha256 or digest,
            stored_path=str(path),
            content_type=source.content_type,
            byte_size=len(content),
            download_status="downloaded",
        )
    else:
        for segment in session.exec(
            select(RegulationTextSegment).where(
                RegulationTextSegment.attachment_id == attachment.id
            )
        ).all():
            session.delete(segment)
        attachment.filename = filename
        attachment.sha256 = source.content_sha256 or digest
        attachment.stored_path = str(path)
        attachment.content_type = source.content_type
        attachment.byte_size = len(content)
        attachment.download_status = "downloaded"
        attachment.download_error = ""
        attachment.verification_usable = True
        session.add(attachment)
    regulation.source_content_sha256 = source.content_sha256 or digest
    regulation_services.write_regulation_segments(session, regulation, [("网页正文", source.text)], attachment)
    return attachment


@app.post("/regulations/{regulation_id}/attachments/import-url", response_model=RegulationAttachmentRead)
def import_regulation_attachment_from_url(
    regulation_id: int,
    payload: RegulationAttachmentImport,
    session: Session = Depends(get_session),
) -> RegulationAttachment:
    regulation = session.get(RegulationRecord, regulation_id)
    if regulation is None:
        raise HTTPException(status_code=404, detail="Regulation not found")
    try:
        downloaded = regulation_services.download_attachment(
            payload.url,
            payload.filename,
            referer=regulation.official_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if safe_suffix(downloaded.filename) not in SUPPORTED_REGULATION_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only doc, docx, pdf, txt, and md regulation attachments can be extracted")
    path, digest = save_regulation_bytes(downloaded.filename, downloaded.content)
    try:
        segments = extract_text_segments(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    attachment = regulation_services.create_attachment(
        session,
        regulation,
        filename=downloaded.filename,
        source_url=payload.url,
        source_page_url=regulation.official_url,
        source_type=payload.source_type,
        verification_usable=payload.verification_usable,
        sha256=digest,
        stored_path=str(path),
        content_type=downloaded.content_type,
        byte_size=len(downloaded.content),
        download_status="downloaded",
    )
    regulation_services.write_regulation_segments(session, regulation, segments, attachment)
    session.commit()
    session.refresh(attachment)
    return attachment


@app.post("/regulations/preset-attachments/download", response_model=RegulationAttachmentBulkDownloadResponse)
def download_preset_regulation_attachments(
    session: Session = Depends(get_session),
) -> RegulationAttachmentBulkDownloadResponse:
    preset_records = {
        regulation.id: regulation
        for regulation in session.exec(
            select(RegulationRecord).where(RegulationRecord.source_type == "preset")
        ).all()
    }
    attachments = session.exec(
        select(RegulationAttachment)
        .where(RegulationAttachment.regulation_id.in_(list(preset_records)))
        .order_by(RegulationAttachment.id)
    ).all()
    attachment_record_ids = {attachment.regulation_id for attachment in attachments}
    results: list[RegulationAttachmentDownloadItem] = []
    downloaded_count = 0
    skipped_count = 0
    failed_count = 0
    for attachment in attachments:
        regulation = preset_records.get(attachment.regulation_id)
        if regulation is None or attachment.id is None:
            continue
        if attachment.download_status == "extracted" and attachment.segment_count > 0:
            skipped_count += 1
            results.append(
                RegulationAttachmentDownloadItem(
                    regulation_id=regulation.id or 0,
                    regulation_title=regulation.title,
                    attachment_id=attachment.id,
                    filename=attachment.filename,
                    source_type=attachment.source_type,
                    status="skipped",
                    detail="already extracted",
                    segment_count=attachment.segment_count,
                )
            )
            continue
        try:
            if attachment.source_type == "web_page":
                attachment = _download_and_extract_web_page_source(session, regulation)
            else:
                _download_and_extract_attachment(session, regulation, attachment)
            session.commit()
            session.refresh(attachment)
            downloaded_count += 1
            results.append(
                RegulationAttachmentDownloadItem(
                    regulation_id=regulation.id or 0,
                    regulation_title=regulation.title,
                    attachment_id=attachment.id,
                    filename=attachment.filename,
                    source_type=attachment.source_type,
                    status="downloaded",
                    segment_count=attachment.segment_count,
                )
            )
        except Exception as exc:
            session.rollback()
            attachment = session.get(RegulationAttachment, attachment.id)
            if attachment is not None:
                attachment.download_status = "failed"
                attachment.download_error = str(exc)
                session.add(attachment)
                session.commit()
            failed_count += 1
            results.append(
                RegulationAttachmentDownloadItem(
                    regulation_id=regulation.id or 0,
                    regulation_title=regulation.title,
                    attachment_id=attachment.id if attachment else 0,
                    filename=attachment.filename if attachment else "",
                    source_type=attachment.source_type if attachment else "",
                    status="failed",
                    detail=str(exc),
                    segment_count=attachment.segment_count if attachment else 0,
                )
            )
    for regulation in preset_records.values():
        if regulation.id in attachment_record_ids or not regulation.official_url:
            continue
        existing_web_page = session.exec(
            select(RegulationAttachment).where(
                RegulationAttachment.regulation_id == regulation.id,
                RegulationAttachment.source_type == "web_page",
                RegulationAttachment.source_url == regulation.official_url,
            )
        ).first()
        if existing_web_page is not None and existing_web_page.download_status == "extracted" and existing_web_page.segment_count > 0:
            skipped_count += 1
            results.append(
                RegulationAttachmentDownloadItem(
                    regulation_id=regulation.id or 0,
                    regulation_title=regulation.title,
                    attachment_id=existing_web_page.id or 0,
                    filename=existing_web_page.filename,
                    source_type=existing_web_page.source_type,
                    status="skipped",
                    detail="already extracted",
                    segment_count=existing_web_page.segment_count,
                )
            )
            continue
        try:
            attachment = _download_and_extract_web_page_source(session, regulation)
            session.commit()
            session.refresh(attachment)
            downloaded_count += 1
            results.append(
                RegulationAttachmentDownloadItem(
                    regulation_id=regulation.id or 0,
                    regulation_title=regulation.title,
                    attachment_id=attachment.id or 0,
                    filename=attachment.filename,
                    source_type=attachment.source_type,
                    status="downloaded",
                    segment_count=attachment.segment_count,
                )
            )
        except Exception as exc:
            session.rollback()
            failed_count += 1
            if existing_web_page is None:
                try:
                    existing_web_page = regulation_services.create_attachment(
                        session,
                        regulation,
                        filename=f"regulation-{regulation.id or 'source'}-official-page.html",
                        source_url=regulation.official_url,
                        source_page_url=regulation.official_url,
                        source_type="web_page",
                        verification_usable=True,
                        download_status="failed",
                        download_error=str(exc),
                    )
                    session.commit()
                except Exception:
                    session.rollback()
            else:
                existing_web_page.download_status = "failed"
                existing_web_page.download_error = str(exc)
                session.add(existing_web_page)
                session.commit()
            results.append(
                RegulationAttachmentDownloadItem(
                    regulation_id=regulation.id or 0,
                    regulation_title=regulation.title,
                    attachment_id=existing_web_page.id if existing_web_page and existing_web_page.id else 0,
                    filename=existing_web_page.filename if existing_web_page else "",
                    source_type="web_page",
                    status="failed",
                    detail=str(exc),
                    segment_count=existing_web_page.segment_count if existing_web_page else 0,
                )
            )
    return RegulationAttachmentBulkDownloadResponse(
        total=len(attachments) + len(
            [
                regulation
                for regulation in preset_records.values()
                if regulation.id not in attachment_record_ids and regulation.official_url
            ]
        ),
        downloaded=downloaded_count,
        skipped=skipped_count,
        failed=failed_count,
        results=results,
    )


@app.post("/regulations/{regulation_id}/attachments/{attachment_id}/download", response_model=RegulationAttachmentRead)
def download_existing_regulation_attachment(
    regulation_id: int,
    attachment_id: int,
    session: Session = Depends(get_session),
) -> RegulationAttachment:
    regulation = session.get(RegulationRecord, regulation_id)
    if regulation is None:
        raise HTTPException(status_code=404, detail="Regulation not found")
    attachment = session.get(RegulationAttachment, attachment_id)
    if attachment is None or attachment.regulation_id != regulation_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    try:
        _download_and_extract_attachment(session, regulation, attachment)
    except Exception as exc:
        attachment.download_status = "failed"
        attachment.download_error = str(exc)
        session.add(attachment)
        session.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    session.refresh(attachment)
    return attachment


@app.post("/regulations/import/web", response_model=RegulationRead)
def import_regulation_from_web(
    payload: RegulationWebImport,
    session: Session = Depends(get_session),
) -> RegulationRecord:
    try:
        source = regulation_services.fetch_web_regulation(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    regulation = RegulationRecord(
        title=payload.title or source.title or payload.url,
        reference_number=payload.reference_number,
        publication_date=payload.publication_date,
        official_url=payload.url,
        source_type="web_import",
        source_content_sha256=source.content_sha256,
        source_note="网页正文已导入并计算来源内容 SHA；若要标记为已校验，仍需补充官方附件文件 SHA。",
        applicable_modules=payload.applicable_modules,
        coverage_classes=payload.coverage_classes,
        device_scope=payload.device_scope,
    )
    session.add(regulation)
    session.commit()
    session.refresh(regulation)
    regulation_services.write_regulation_segments(session, regulation, [("网页正文", source.text)])
    session.commit()
    session.refresh(regulation)
    return regulation


@app.post("/regulations/import/file", response_model=RegulationRead)
def import_regulation_from_file(
    title: str = Form(""),
    official_url: str = Form(""),
    reference_number: str = Form(""),
    publication_date: str = Form(""),
    applicable_modules: str = Form(""),
    coverage_classes: str = Form("II,III"),
    device_scope: str = Form("II类和III类有源医疗器械注册"),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> RegulationRecord:
    if safe_suffix(file.filename or "") not in SUPPORTED_REGULATION_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only doc, docx, pdf, txt, and md regulation files are supported")
    path, digest = save_regulation_upload(file)
    try:
        segments = extract_text_segments(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    filename = file.filename or path.name
    regulation = RegulationRecord(
        title=title or filename,
        reference_number=reference_number,
        publication_date=publication_date,
        official_url=official_url,
        attachment_filename=filename,
        attachment_sha256=digest,
        source_type="file_import",
        source_files=[
            {
                "filename": filename,
                "url": official_url,
                "sha256": digest,
                "source": "uploaded_file",
                "verification_usable": True,
            }
        ],
        source_note="上传文件已保存并计算 SHA；法规适用性和官方来源仍需人工确认。",
        applicable_modules=_split_csv(applicable_modules),
        coverage_classes=_split_csv(coverage_classes) or ["II", "III"],
        device_scope=device_scope,
        stored_path=str(path),
    )
    session.add(regulation)
    session.commit()
    session.refresh(regulation)
    attachment = regulation_services.create_attachment(
        session,
        regulation,
        filename=filename,
        source_url=official_url,
        source_page_url=official_url,
        source_type="uploaded_file",
        verification_usable=True,
        sha256=digest,
        stored_path=str(path),
        content_type=file.content_type or "",
        byte_size=path.stat().st_size,
        download_status="uploaded",
    )
    regulation_services.write_regulation_segments(session, regulation, segments, attachment)
    session.commit()
    session.refresh(regulation)
    return regulation


@app.patch("/regulations/{regulation_id}/verify", response_model=RegulationRead)
def verify_regulation(
    regulation_id: int,
    payload: RegulationVerify,
    session: Session = Depends(get_session),
) -> RegulationRecord:
    regulation = session.get(RegulationRecord, regulation_id)
    if regulation is None:
        raise HTTPException(status_code=404, detail="Regulation not found")
    if payload.verification_status == "verified":
        has_file_evidence = regulation_services.has_usable_attachment(session, regulation_id)
        if not regulation.official_url or not has_file_evidence:
            raise HTTPException(
                status_code=400,
                detail="Verified regulations require official_url and at least one extracted source SHA",
            )
        regulation.verified_at = datetime.now(timezone.utc)
    regulation.verification_status = payload.verification_status
    regulation.verified_by = payload.verified_by
    session.add(regulation)
    session.commit()
    session.refresh(regulation)
    return regulation


@app.post("/regulations/{regulation_id}/ai/summarize-impact", response_model=RegulationImpactDraftRead)
def ai_summarize_regulation_impact(
    regulation_id: int,
    session: Session = Depends(get_session),
) -> RegulationImpactDraftRead:
    try:
        draft = summarize_regulation_impact(session, regulation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RegulationImpactDraftRead.model_validate(draft)


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _snippet(text: str, needle: str) -> str:
    index = text.find(needle)
    if index < 0:
        return text[:240]
    start = max(index - 90, 0)
    end = min(index + len(needle) + 150, len(text))
    return text[start:end]
