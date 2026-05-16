from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlmodel import Session, select

from backend.app.master_data import first_label_value
from backend.app.models import DocumentRecord, DocumentSegment


KEY_FIELDS: list[tuple[str, str, list[str]]] = [
    ("product_name", "产品名称", ["产品名称", "注册产品名称"]),
    ("model_specifications", "型号规格", ["型号规格", "型号"]),
    ("structure_composition", "结构组成", ["结构组成", "组成"]),
    ("intended_use", "预期用途/适用范围", ["适用范围", "预期用途"]),
    ("software_version", "软件版本", ["软件版本"]),
    ("service_life", "使用寿命/有效期", ["使用期限", "使用寿命", "寿命"]),
    ("tested_model", "检测/代表型号", ["检验型号", "检测型号", "代表型号"]),
]


def normalize_for_compare(value: str) -> str:
    return (
        value.replace(" ", "")
        .replace("，", ",")
        .replace("；", ";")
        .lower()
        .strip()
    )


def build_consistency_matrix(session: Session, project_id: int) -> list[dict[str, Any]]:
    documents = document_texts(session, project_id)
    rows: list[dict[str, Any]] = []
    for field, label, labels in KEY_FIELDS:
        values_by_document = []
        normalized_seen: dict[str, list[str]] = defaultdict(list)
        for document in documents:
            value = first_label_value(document["text"], labels)
            quote = build_quote(document["text"], value)
            if value:
                normalized_seen[normalize_for_compare(value)].append(document["filename"])
            values_by_document.append(
                {
                    "document_id": document["document_id"],
                    "document_type": document["document_type"],
                    "filename": document["filename"],
                    "value": value,
                    "quote": quote,
                }
            )
        present_count = sum(1 for item in values_by_document if item["value"])
        if present_count == 0:
            status = "missing"
        elif len(normalized_seen) > 1:
            status = "conflict"
        elif present_count < min(2, len(values_by_document)):
            status = "weak"
        else:
            status = "consistent"
        rows.append(
            {
                "field": field,
                "label": label,
                "status": status,
                "values_by_document": values_by_document,
            }
        )
    return rows


def document_texts(session: Session, project_id: int) -> list[dict[str, Any]]:
    documents = session.exec(
        select(DocumentRecord)
        .where(DocumentRecord.project_id == project_id)
        .order_by(DocumentRecord.id)
    ).all()
    rows: list[dict[str, Any]] = []
    for document in documents:
        segments = session.exec(
            select(DocumentSegment)
            .where(DocumentSegment.document_id == document.id)
            .order_by(DocumentSegment.id)
        ).all()
        rows.append(
            {
                "document_id": document.id or 0,
                "document_type": document.document_type,
                "filename": document.filename,
                "text": "\n".join(segment.text for segment in segments),
            }
        )
    return rows


def build_quote(text: str, value: str) -> str:
    if not value:
        return ""
    index = text.find(value)
    if index < 0:
        return value
    start = max(0, index - 40)
    end = min(len(text), index + len(value) + 80)
    return text[start:end].replace("\n", " ")
