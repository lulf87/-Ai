from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from backend.app.models import DocumentRecord, Project


@dataclass(frozen=True)
class DocumentChecklistItem:
    document_type: str
    label: str
    section: str
    required: bool = True
    project_flag: str = ""


DOCUMENT_CHECKLIST: tuple[DocumentChecklistItem, ...] = (
    DocumentChecklistItem("application_form", "注册申请表", "监管信息"),
    DocumentChecklistItem("terms", "术语、缩写和符号说明", "监管信息"),
    DocumentChecklistItem("overview", "综述资料", "综述资料"),
    DocumentChecklistItem("technical_requirements", "产品技术要求", "非临床资料"),
    DocumentChecklistItem("test_report", "检验报告", "非临床资料"),
    DocumentChecklistItem("risk_management", "风险管理资料", "非临床资料"),
    DocumentChecklistItem("essential_principles", "基本原则符合性资料", "非临床资料"),
    DocumentChecklistItem("research", "非临床研究资料", "非临床资料"),
    DocumentChecklistItem("software", "软件研究资料", "专项研究"),
    DocumentChecklistItem("cybersecurity", "网络安全研究资料", "专项研究", required=False, project_flag="is_networked"),
    DocumentChecklistItem("algorithm", "AI/算法研究资料", "专项研究", required=False, project_flag="has_ai"),
    DocumentChecklistItem("energy_safety", "输出能量安全研究资料", "专项研究"),
    DocumentChecklistItem("reliability", "使用期限和可靠性资料", "专项研究"),
    DocumentChecklistItem("usability", "可用性工程资料", "专项研究"),
    DocumentChecklistItem("clinical_evaluation", "临床评价资料", "临床资料"),
    DocumentChecklistItem("instructions", "说明书", "说明书和标签"),
    DocumentChecklistItem("labels", "标签样稿", "说明书和标签"),
    DocumentChecklistItem("quality_system", "质量管理体系资料", "质量体系"),
)


def expected_document_items(project: Project) -> list[DocumentChecklistItem]:
    return [
        item
        for item in DOCUMENT_CHECKLIST
        if item.required or (item.project_flag and bool(getattr(project, item.project_flag)))
    ]


def build_document_readiness(session: Session, project: Project) -> dict[str, Any]:
    uploaded_document_types = {
        document.document_type
        for document in session.exec(
            select(DocumentRecord).where(DocumentRecord.project_id == project.id)
        ).all()
    }
    expected_items = expected_document_items(project)
    missing_items = [
        {
            "document_type": item.document_type,
            "label": item.label,
            "section": item.section,
        }
        for item in expected_items
        if item.document_type not in uploaded_document_types
    ]
    return {
        "required_document_count": len(expected_items),
        "uploaded_required_document_count": len(expected_items) - len(missing_items),
        "missing_required_documents": missing_items,
    }
