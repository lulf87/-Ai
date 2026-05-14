from __future__ import annotations

import re

from sqlmodel import Session, select

from backend.app.models import DocumentSegment, ProductMasterData, Project, utc_now


LABELS = {
    "product_name": ["产品名称", "注册产品名称"],
    "model_specifications": ["型号规格", "型号"],
    "structure_composition": ["结构组成", "组成"],
    "intended_use": ["适用范围", "预期用途"],
    "use_environment": ["使用环境"],
    "users": ["使用者", "目标用户"],
    "software_name": ["软件名称"],
    "software_version": ["软件版本"],
    "energy_type": ["能量类型"],
    "service_life": ["使用期限", "寿命"],
    "tested_model": ["检验型号", "检测型号"],
    "applicable_standards": ["适用标准", "引用标准"],
}


def extract_master_data(session: Session, project: Project) -> ProductMasterData:
    text = "\n".join(
        segment.text
        for segment in session.exec(
            select(DocumentSegment).where(DocumentSegment.project_id == project.id)
        ).all()
    )
    existing = session.exec(
        select(ProductMasterData).where(ProductMasterData.project_id == project.id)
    ).first()
    master = existing or ProductMasterData(project_id=project.id)

    for field_name, labels in LABELS.items():
        value = first_label_value(text, labels)
        if value:
            setattr(master, field_name, value)

    master.is_networked = project.is_networked or contains_any(
        text, ["联网", "Wi-Fi", "远程升级", "远程维护", "医院网络", "数据上传"]
    )
    master.outputs_energy = project.outputs_energy or contains_any(
        text, ["微波", "射频", "激光", "超声", "电刺激", "X 射线", "输出能量"]
    )
    master.has_disposable_accessory = project.has_disposable_accessory or contains_any(
        text, ["一次性", "一次性附件", "一次性探针"]
    )
    master.updated_at = utc_now()

    session.add(master)
    session.commit()
    session.refresh(master)
    return master


def first_label_value(text: str, labels: list[str]) -> str:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[：:]\s*([^\n。；;]+)"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ""


def contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)

