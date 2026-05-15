from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from backend.app.models import (
    DocumentSegment,
    Finding,
    ProductMasterData,
    Project,
    RegulationAttachment,
    RegulationRecord,
    RegulationTextSegment,
)


MODULE_KEYWORDS: dict[str, list[str]] = {
    "general_submission": ["注册申报资料", "综述资料", "适用范围", "型号规格", "结构组成"],
    "testing": ["产品技术要求", "检验报告", "检验方法", "性能指标", "代表型号"],
    "standards": ["强制性标准", "适用标准", "标准版本", "GB 9706", "YY 0505"],
    "software": ["软件", "软件版本", "软件研究资料", "发布版本", "回归测试"],
    "network_security": ["网络安全", "联网", "远程维护", "远程升级", "数据传输", "权限控制"],
    "ai_algorithm": ["人工智能", "智能算法", "算法", "自动推荐", "训练验证", "性能评价", "AI"],
    "clinical": ["临床评价", "同品种", "临床试验", "免于临床评价", "单臂", "30例"],
    "reliability": ["使用期限", "可靠性", "稳定性", "有效期"],
    "labeling": ["说明书", "标签", "一次性", "警示", "重复使用", "清洁消毒"],
    "risk_management": ["风险管理", "剩余风险", "禁忌", "警示"],
}

RULE_MODULES = {
    "R-NAME-CONSISTENCY": "general_submission",
    "R-MODEL-CONSISTENCY": "general_submission",
    "R-STRUCTURE-CONSISTENCY": "general_submission",
    "R-INTENDED-USE": "general_submission",
    "R-SOFTWARE-VERSION": "software",
    "R-NETWORK-SECURITY": "network_security",
    "R-TEST-COVERAGE": "testing",
    "R-STANDARD-VERSION": "standards",
    "R-SERVICE-LIFE": "reliability",
    "R-DISPOSABLE-CONFLICT": "labeling",
    "R-CONTRAINDICATION": "risk_management",
    "R-UNSUPPORTED-CLAIM": "clinical",
    "R-REPRESENTATIVE-MODEL": "testing",
    "R-AI-ALGORITHM": "ai_algorithm",
    "R-CLINICAL-OVERCLAIM": "clinical",
}

ALL_KEYWORDS = sorted({keyword for keywords in MODULE_KEYWORDS.values() for keyword in keywords}, key=len, reverse=True)


@dataclass(frozen=True)
class RegulationRagHit:
    regulation_id: int
    regulation_title: str
    attachment_id: int
    attachment_filename: str
    attachment_sha256: str
    locator: str
    quote: str
    module: str
    score: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "regulation_id": self.regulation_id,
            "regulation_title": self.regulation_title,
            "attachment_id": self.attachment_id,
            "attachment_filename": self.attachment_filename,
            "attachment_sha256": self.attachment_sha256,
            "locator": self.locator,
            "quote": self.quote,
            "module": self.module,
            "score": self.score,
        }


def search_verified_regulation_segments(
    session: Session,
    project_id: int,
    *,
    limit: int = 8,
) -> list[RegulationRagHit]:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError("Project not found")
    modules, keywords, project_text = build_project_rag_terms(session, project)
    rows = session.exec(
        select(RegulationTextSegment, RegulationRecord, RegulationAttachment)
        .join(RegulationRecord, RegulationRecord.id == RegulationTextSegment.regulation_id)
        .join(RegulationAttachment, RegulationAttachment.id == RegulationTextSegment.attachment_id)
        .where(RegulationRecord.verification_status == "verified")
        .where(RegulationAttachment.verification_usable == True)  # noqa: E712
        .where(RegulationAttachment.sha256 != "")
        .where(RegulationAttachment.stored_path != "")
        .where(RegulationAttachment.download_status == "extracted")
        .where(RegulationAttachment.segment_count > 0)
    ).all()

    hits: list[RegulationRagHit] = []
    for segment, regulation, attachment in rows:
        if not regulation.id or not attachment.id:
            continue
        score, matched_module = score_regulation_segment(
            segment.text,
            regulation.applicable_modules,
            modules,
            keywords,
            project_text,
        )
        if score <= 0:
            continue
        hits.append(
            RegulationRagHit(
                regulation_id=regulation.id,
                regulation_title=regulation.title,
                attachment_id=attachment.id,
                attachment_filename=attachment.filename,
                attachment_sha256=attachment.sha256,
                locator=segment.locator,
                quote=bounded_quote(segment.text, keywords),
                module=matched_module,
                score=score,
            )
        )

    hits.sort(key=lambda hit: (-hit.score, hit.regulation_title, hit.locator))
    deduped: list[RegulationRagHit] = []
    seen: set[tuple[int, int, str]] = set()
    for hit in hits:
        key = (hit.regulation_id, hit.attachment_id, hit.locator)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
        if len(deduped) >= limit:
            break
    return deduped


def build_project_rag_terms(
    session: Session,
    project: Project,
) -> tuple[set[str], set[str], str]:
    master = session.exec(
        select(ProductMasterData).where(ProductMasterData.project_id == project.id)
    ).first()
    segments = session.exec(
        select(DocumentSegment).where(DocumentSegment.project_id == project.id)
    ).all()
    findings = session.exec(select(Finding).where(Finding.project_id == project.id)).all()
    project_text = "\n".join(segment.text for segment in segments)
    master_text = " ".join(
        str(getattr(master, field, "") or "")
        for field in [
            "product_name",
            "structure_composition",
            "intended_use",
            "software_name",
            "software_version",
            "energy_type",
            "service_life",
            "applicable_standards",
        ]
    ) if master else ""
    combined = f"{project_text}\n{master_text}"

    modules = {"general_submission"}
    if project.has_software or contains_any(combined, ["软件", "软件版本"]):
        modules.add("software")
    if project.is_networked or (master and master.is_networked) or contains_any(combined, ["联网", "远程升级", "远程维护", "Wi-Fi"]):
        modules.add("network_security")
    if project.has_ai or contains_any(combined, ["人工智能", "智能算法", "自动推荐", "AI", "算法"]):
        modules.add("ai_algorithm")
    if project.outputs_energy or (master and master.outputs_energy) or contains_any(combined, ["微波", "输出能量", "消融"]):
        modules.add("testing")
    if project.has_disposable_accessory or (master and master.has_disposable_accessory) or contains_any(combined, ["一次性", "重复使用", "清洁消毒"]):
        modules.add("labeling")
    if contains_any(combined, ["临床评价", "同品种", "临床试验", "免于临床评价", "30例", "单臂"]):
        modules.add("clinical")
    if contains_any(combined, ["使用期限", "可靠性", "稳定性"]):
        modules.add("reliability")
    if contains_any(combined, ["禁忌", "警示", "风险管理"]):
        modules.add("risk_management")
    if contains_any(combined, ["GB 9706", "YY 0505", "标准版本", "适用标准"]):
        modules.add("standards")
    for finding in findings:
        module = RULE_MODULES.get(finding.rule_id)
        if module:
            modules.add(module)

    keywords = set()
    for module in modules:
        keywords.update(MODULE_KEYWORDS.get(module, []))
    keywords.update(keyword for keyword in ALL_KEYWORDS if keyword in combined)
    return modules, {keyword for keyword in keywords if keyword}, combined


def score_regulation_segment(
    text: str,
    regulation_modules: list[str],
    project_modules: set[str],
    keywords: set[str],
    project_text: str,
) -> tuple[int, str]:
    score = 0
    matched_module = ""
    regulation_module_set = set(regulation_modules)
    module_overlap = project_modules.intersection(regulation_module_set)
    if module_overlap:
        matched_module = sorted(module_overlap)[0]
        score += 8
    elif "general_submission" in regulation_module_set:
        matched_module = "general_submission"
        score += 2

    for keyword in keywords:
        if keyword in text:
            score += 3 if keyword in project_text else 1
            if not matched_module:
                matched_module = module_for_keyword(keyword)

    for module in project_modules:
        module_hits = sum(1 for keyword in MODULE_KEYWORDS.get(module, []) if keyword in text)
        if module_hits:
            score += module_hits
            if not matched_module:
                matched_module = module
    return score, matched_module or "general_submission"


def bounded_quote(text: str, keywords: set[str], *, max_length: int = 360) -> str:
    cleaned = clean_text(text)
    for keyword in sorted(keywords, key=len, reverse=True):
        index = cleaned.find(keyword)
        if index >= 0:
            start = max(0, index - 90)
            end = min(len(cleaned), index + len(keyword) + 240)
            return cleaned[start:end]
    return cleaned[:max_length]


def module_for_keyword(keyword: str) -> str:
    for module, keywords in MODULE_KEYWORDS.items():
        if keyword in keywords:
            return module
    return "general_submission"


def contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
