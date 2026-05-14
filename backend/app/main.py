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
from backend.app.ai_services import (
    ai_analyze_risks,
    ai_extract_master_data,
    polish_report,
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
    RegulationRecord,
    Report,
    LLMRun,
)
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
    RegulationCreate,
    RegulationRead,
    RegulationVerify,
    ReportPolishResponse,
    ReportRead,
    RunChecksResponse,
)
from backend.app.storage import safe_suffix, save_upload, sha256_file


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
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


@app.post("/projects/{project_id}/sample-documents/golden-microwave", response_model=list[DocumentRead])
def load_golden_sample_documents(
    project_id: int,
    session: Session = Depends(get_session),
) -> list[DocumentRecord]:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    sample_dir = BASE_DIR / "samples" / "golden" / "microwave_ablation"
    if not sample_dir.is_dir():
        raise HTTPException(status_code=404, detail="Golden sample not found")

    records = []
    for sample in sorted(sample_dir.glob("*.md")):
        document_type = sample.stem.split("_", 1)[1]
        record = create_document_record_from_path(project_id, document_type, sample, session)
        records.append(record)
    return records


def create_document_record_from_path(
    project_id: int,
    document_type: str,
    source_path: Path,
    session: Session,
) -> DocumentRecord:
    project_dir = UPLOAD_DIR / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256_file(source_path)
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
        if not regulation.official_url or not regulation.attachment_sha256:
            raise HTTPException(
                status_code=400,
                detail="Verified regulations require official_url and attachment_sha256",
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
