from __future__ import annotations

import re
from dataclasses import dataclass

from backend.app.consistency import build_consistency_matrix
from sqlmodel import Session, delete, select

from backend.app.master_data import contains_any, extract_master_data, first_label_value
from backend.app.models import (
    DocumentRecord,
    DocumentSegment,
    Finding,
    ProductMasterData,
    Project,
    RegulationRecord,
)
from backend.app.obligations import load_rule_config, matching_obligations


@dataclass(frozen=True)
class RuleMeta:
    rule_id: str
    module: str
    title: str
    risk_level: str
    possible_impact: str
    recommended_action: str
    category: str = ""
    owner: str = ""
    workload: str = ""


OWNER_BY_CATEGORY = {
    "资料完整性": "注册负责人",
    "主数据一致性": "注册负责人+研发",
    "软件": "软件研发/注册",
    "网络安全": "软件研发/网络安全",
    "AI算法": "算法团队/临床评价",
    "检测覆盖": "研发+检测接口人",
    "临床评价": "临床评价负责人",
    "风险管理": "质量/风险管理",
    "说明书标签": "注册负责人/市场医学",
    "标准": "法规/研发",
    "OCR": "注册助理",
}


CATEGORY_BY_MODULE = {
    "general_submission": "主数据一致性",
    "software": "软件",
    "network_security": "网络安全",
    "testing": "检测覆盖",
    "standards": "标准",
    "reliability": "风险管理",
    "labeling": "说明书标签",
    "risk_management": "风险管理",
    "clinical": "临床评价",
    "ai_algorithm": "AI算法",
}


REQUIRED_DOCUMENT_TYPES = {
    "application_form": "注册申请表",
    "overview": "产品综述资料",
    "technical_requirements": "产品技术要求",
    "instructions": "说明书",
    "risk_management": "风险管理资料",
    "clinical_evaluation": "临床评价资料/免临床说明",
    "test_report": "注册检验/检测报告",
}


RULES: dict[str, RuleMeta] = {
    "R-NAME-CONSISTENCY": RuleMeta(
        "R-NAME-CONSISTENCY",
        "general_submission",
        "产品名称前后不一致",
        "red",
        "可能导致注册申请表、说明书、技术要求和检验资料之间无法建立同一产品证据链。",
        "统一所有申报资料中的产品名称，并保留变更痕迹供复核。",
    ),
    "R-MODEL-CONSISTENCY": RuleMeta(
        "R-MODEL-CONSISTENCY",
        "general_submission",
        "型号规格前后不一致",
        "red",
        "可能影响注册单元、代表型号和检验覆盖判断。",
        "统一型号规格清单，说明各型号差异及代表型号选择依据。",
    ),
    "R-STRUCTURE-CONSISTENCY": RuleMeta(
        "R-STRUCTURE-CONSISTENCY",
        "general_submission",
        "结构组成描述不一致",
        "yellow",
        "关键模块缺失可能导致审评人员无法确认产品组成和功能边界。",
        "核对综述、说明书、技术要求中的结构组成，补齐缺失模块。",
    ),
    "R-INTENDED-USE": RuleMeta(
        "R-INTENDED-USE",
        "general_submission",
        "说明书适用范围疑似扩大",
        "red",
        "适用范围扩大可能影响临床评价路径、注册单元和补正风险。",
        "统一适用范围；如确需扩大，应补充对应验证和临床评价资料。",
    ),
    "R-SOFTWARE-VERSION": RuleMeta(
        "R-SOFTWARE-VERSION",
        "software",
        "软件版本证据链不一致",
        "red",
        "软件版本不一致会削弱检验、说明书和软件研究资料之间的对应关系。",
        "统一软件版本号，必要时补充版本差异说明和回归验证记录。",
    ),
    "R-NETWORK-SECURITY": RuleMeta(
        "R-NETWORK-SECURITY",
        "network_security",
        "联网功能触发网络安全资料缺口",
        "red",
        "联网、远程升级或远程维护缺少网络安全资料，可能导致补正。",
        "补充网络安全研究资料，至少覆盖身份鉴别、权限控制、日志审计和数据传输保护。",
    ),
    "R-TEST-COVERAGE": RuleMeta(
        "R-TEST-COVERAGE",
        "testing",
        "产品技术要求与检验报告覆盖不足",
        "red",
        "技术要求中的关键指标未在检验报告中体现，可能导致补检或补充说明。",
        "补充检验项目或提供覆盖性说明，确保关键性能指标可追溯。",
    ),
    "R-STANDARD-VERSION": RuleMeta(
        "R-STANDARD-VERSION",
        "standards",
        "引用标准版本疑似过旧",
        "yellow",
        "引用旧版强制或推荐标准可能导致补充标准适用性说明。",
        "核对现行有效标准版本，必要时更新产品技术要求并说明差异影响。",
    ),
    "R-SERVICE-LIFE": RuleMeta(
        "R-SERVICE-LIFE",
        "reliability",
        "使用期限缺少可靠性证据",
        "yellow",
        "说明书声明使用期限但缺少可靠性或使用期限研究资料。",
        "补充使用期限、可靠性或稳定性支持资料，并与说明书保持一致。",
    ),
    "R-DISPOSABLE-CONFLICT": RuleMeta(
        "R-DISPOSABLE-CONFLICT",
        "labeling",
        "一次性附件出现重复使用表述",
        "red",
        "一次性使用附件与清洁消毒后重复使用表述冲突，可能形成严重标签风险。",
        "删除重复使用表述，统一一次性使用、处置和警示说明。",
    ),
    "R-CONTRAINDICATION": RuleMeta(
        "R-CONTRAINDICATION",
        "risk_management",
        "风险管理禁忌未体现在说明书",
        "yellow",
        "风险管理资料中的禁忌或警示未进入说明书，可能导致标签不完整。",
        "将风险管理中的禁忌、警示和剩余风险控制措施同步到说明书。",
    ),
    "R-UNSUPPORTED-CLAIM": RuleMeta(
        "R-UNSUPPORTED-CLAIM",
        "clinical",
        "功能声称缺少验证证据",
        "yellow",
        "宽泛或绝对化功能声称缺少验证依据，可能导致补正或标签修改。",
        "删除无依据表述，或补充性能、临床或可用性验证证据。",
    ),
    "R-REPRESENTATIVE-MODEL": RuleMeta(
        "R-REPRESENTATIVE-MODEL",
        "testing",
        "代表型号覆盖说明不足",
        "yellow",
        "多个型号只检验一个型号但缺少代表性说明，可能影响检验覆盖判断。",
        "补充型号差异分析和代表型号选择依据。",
    ),
    "R-AI-ALGORITHM": RuleMeta(
        "R-AI-ALGORITHM",
        "ai_algorithm",
        "智能算法功能触发算法资料缺口",
        "yellow",
        "自动识别、推荐或预测功能缺少算法资料，可能导致补正。",
        "补充算法基本信息、训练/验证数据、性能评价和风险控制资料。",
    ),
    "R-CLINICAL-OVERCLAIM": RuleMeta(
        "R-CLINICAL-OVERCLAIM",
        "clinical",
        "临床路径结论过强",
        "red",
        "临床证据不足时直接给出免临床或充分有效结论，可能误导注册路径。",
        "将结论改为待确认，补充同品种对比、目录依据或临床评价证据。",
        "临床评价",
        "临床评价负责人",
        "临床评价专项补充",
    ),
    "COMPLETE-SOFTWARE": RuleMeta(
        "COMPLETE-SOFTWARE",
        "software",
        "产品触发软件研究资料，但资料包缺少软件研究资料",
        "red",
        "软件安全性级别、运行环境、生命周期、验证确认和缺陷管理无法被审查。",
        "补充软件研究资料，至少覆盖软件标识、安全性级别、运行环境、需求、架构、V&V、缺陷管理、可追溯性和更新历史。",
        "软件",
        "软件研发/注册",
        "研发+注册专项补充",
    ),
    "COMPLETE-CYBERSECURITY": RuleMeta(
        "COMPLETE-CYBERSECURITY",
        "network_security",
        "产品触发网络安全研究资料，但资料包缺少网络安全资料",
        "red",
        "可能无法证明数据交换、访问控制、漏洞管理、补丁管理和安全更新策略的充分性。",
        "补充网络安全研究资料，包含资产/接口、数据流、身份认证、访问控制、加密、漏洞评估、补丁和应急响应。",
        "网络安全",
        "软件研发/网络安全",
        "软件研发+网络安全评估",
    ),
    "COMPLETE-AI-ALGORITHM": RuleMeta(
        "COMPLETE-AI-ALGORITHM",
        "ai_algorithm",
        "AI/算法触发，但缺少算法研究资料",
        "red",
        "算法数据集、训练验证、性能评价、泛化性和偏倚控制缺乏证据。",
        "补充算法研究资料，明确算法用途、输入输出、训练/验证/测试集、性能指标、偏倚控制、失败模式和临床证据。",
        "AI算法",
        "算法团队/临床评价",
        "算法团队+临床评价专项补充",
    ),
    "PTQ-TEST-COVERAGE": RuleMeta(
        "PTQ-TEST-COVERAGE",
        "testing",
        "产品技术要求指标未在检测报告中形成覆盖矩阵",
        "red",
        "可能导致补检、检测报告补充说明或 PTQ 指标修订。",
        "建立 PTQ-检测报告覆盖矩阵：每个指标对应样品型号、检测项目、结果、结论和报告页码。",
        "检测覆盖",
        "研发+检测接口人",
        "检测接口确认/可能补检",
    ),
    "MULTI-MODEL-COVERAGE": RuleMeta(
        "MULTI-MODEL-COVERAGE",
        "testing",
        "多型号产品缺少代表型号/覆盖逻辑",
        "yellow",
        "可能要求说明注册单元划分、代表型号选择、检测覆盖和型号差异。",
        "补充型号差异表、代表型号选择依据、检测覆盖矩阵和注册单元划分说明。",
        "检测覆盖",
        "研发+检测接口人",
        "研发+检测接口确认",
    ),
}


@dataclass
class SegmentContext:
    document_type: str
    filename: str
    locator: str
    text: str


@dataclass(frozen=True)
class LabeledEvidence:
    context: SegmentContext
    label: str
    value: str


DOC_TYPE_LABELS = {
    "application_form": "申请表",
    "terms": "术语和缩写",
    "overview": "综述资料",
    "technical_requirements": "产品技术要求",
    "instructions": "使用说明书",
    "risk_management": "风险管理资料",
    "clinical_evaluation": "临床评价资料",
    "test_report": "检验报告",
    "software": "软件研究资料",
    "cybersecurity": "网络安全研究资料",
    "algorithm": "算法研究资料",
    "essential_principles": "基本原则符合性资料",
    "research": "非临床研究资料",
    "reliability": "使用期限和可靠性资料",
    "usability": "可用性工程资料",
    "energy_safety": "输出能量安全研究资料",
    "quality_system": "质量管理体系资料",
    "labels": "标签样稿",
}


def run_rules(session: Session, project_id: int) -> list[Finding]:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError("Project not found")

    master = session.exec(
        select(ProductMasterData).where(ProductMasterData.project_id == project_id)
    ).first()
    if master is None:
        master = extract_master_data(session, project)

    session.exec(
        delete(Finding).where(
            Finding.project_id == project_id,
            Finding.source_type == "rule",
        )
    )
    contexts = load_contexts(session, project_id)
    triggers = triggered_features(project, master, contexts)
    findings: list[Finding] = []

    findings.extend(check_document_completeness(contexts, project_id, session, triggers))
    add_if(findings, check_name_consistency(contexts, project_id, session))
    add_if(findings, check_model_consistency(contexts, project_id, session))
    add_if(findings, check_structure_consistency(contexts, project_id, session))
    add_if(findings, check_intended_use(contexts, project_id, session))
    add_if(findings, check_software_version(contexts, project_id, session))
    add_if(findings, check_network_security(contexts, project_id, session, project, master))
    add_if(findings, check_test_coverage(contexts, project_id, session))
    add_if(findings, check_standard_version(contexts, project_id, session))
    add_if(findings, check_service_life(contexts, project_id, session, master))
    add_if(findings, check_disposable_conflict(contexts, project_id, session, project, master))
    add_if(findings, check_contraindication(contexts, project_id, session))
    add_if(findings, check_unsupported_claim(contexts, project_id, session))
    add_if(findings, check_representative_model(contexts, project_id, session, master))
    add_if(findings, check_ai_algorithm(contexts, project_id, session, project))
    add_if(findings, check_clinical_overclaim(contexts, project_id, session))
    add_if(findings, check_ptq_test_coverage(contexts, project_id, session))
    add_if(findings, check_multi_model_coverage(contexts, project_id, session, master))
    findings.extend(check_configured_obligations(contexts, project_id, session, triggers))

    for finding in findings:
        session.add(finding)
    session.commit()
    for finding in findings:
        session.refresh(finding)
    return findings


def add_if(findings: list[Finding], finding: Finding | None) -> None:
    if finding is not None:
        findings.append(finding)


def load_contexts(session: Session, project_id: int) -> list[SegmentContext]:
    rows = session.exec(
        select(DocumentSegment, DocumentRecord)
        .join(DocumentRecord, DocumentRecord.id == DocumentSegment.document_id)
        .where(DocumentSegment.project_id == project_id)
    ).all()
    return [
        SegmentContext(
            document_type=record.document_type,
            filename=record.filename,
            locator=segment.locator,
            text=segment.text,
        )
        for segment, record in rows
    ]


def make_finding(
    session: Session,
    contexts: list[SegmentContext],
    project_id: int,
    rule_id: str,
    description: str,
    terms: list[str],
    evidence_text: str | None = None,
) -> Finding:
    meta = RULES[rule_id]
    evidence = find_evidence(contexts, terms)
    regulation = verified_regulation(session, meta.module)
    category = meta.category or CATEGORY_BY_MODULE.get(meta.module, meta.module)
    return Finding(
        project_id=project_id,
        rule_id=rule_id,
        regulation_id=regulation.id if regulation else None,
        risk_level=meta.risk_level,
        title=meta.title,
        description=description,
        evidence_document=evidence.filename if evidence and not evidence_text else "",
        evidence_locator=evidence.locator if evidence and not evidence_text else "",
        evidence_quote=evidence_text or (quote(evidence.text, terms) if evidence else ""),
        possible_impact=meta.possible_impact,
        recommended_action=meta.recommended_action,
        owner=meta.owner or OWNER_BY_CATEGORY.get(category, "注册负责人"),
        workload=meta.workload or "资料修订/人工确认",
        category=category,
        confidence_status="evidence_based" if evidence or evidence_text else "pending_evidence",
        source_type="rule",
        review_status="confirmed",
    )


def verified_regulation(session: Session, module: str) -> RegulationRecord | None:
    regulations = session.exec(
        select(RegulationRecord).where(RegulationRecord.verification_status == "verified")
    ).all()
    for regulation in regulations:
        if module in regulation.applicable_modules or "general_submission" in regulation.applicable_modules:
            return regulation
    return None


def find_evidence(contexts: list[SegmentContext], terms: list[str]) -> SegmentContext | None:
    for context in contexts:
        if any(term in context.text for term in terms):
            return context
    return contexts[0] if contexts else None


def quote(text: str, terms: list[str]) -> str:
    for term in terms:
        index = text.find(term)
        if index >= 0:
            start = max(0, index - 45)
            end = min(len(text), index + len(term) + 80)
            return text[start:end].replace("\n", " ")
    return text[:160].replace("\n", " ")


def document_label(document_type: str) -> str:
    return DOC_TYPE_LABELS.get(document_type, document_type)


def evidence_line(context: SegmentContext, statement: str) -> str:
    return f"{document_label(context.document_type)}（{context.filename}，{context.locator}）：{statement}"


def missing_evidence_line(document_name: str, statement: str) -> str:
    return f"{document_name}：{statement}"


def first_context(contexts: list[SegmentContext], document_type: str) -> SegmentContext | None:
    for context in contexts:
        if context.document_type == document_type:
            return context
    return None


def context_quote(context: SegmentContext, terms: list[str]) -> str:
    return quote(context.text, terms)


def text_for(contexts: list[SegmentContext], document_type: str) -> str:
    return "\n".join(context.text for context in contexts if context.document_type == document_type)


def all_text(contexts: list[SegmentContext]) -> str:
    return "\n".join(context.text for context in contexts)


def labeled_values(contexts: list[SegmentContext], labels: list[str]) -> dict[str, str]:
    return {
        document_type: evidence.value
        for document_type, evidence in labeled_evidence(contexts, labels).items()
    }


def labeled_evidence(
    contexts: list[SegmentContext], labels: list[str]
) -> dict[str, LabeledEvidence]:
    values: dict[str, LabeledEvidence] = {}
    for context in contexts:
        for label in labels:
            value = first_label_value(context.text, [label])
            if value:
                values[context.document_type] = LabeledEvidence(context, label, value)
                break
    return values


def format_labeled_evidence(values: dict[str, LabeledEvidence]) -> str:
    return "\n".join(
        evidence_line(evidence.context, f"{evidence.label}：{evidence.value}")
        for evidence in values.values()
    )


def format_term_evidence(
    contexts: list[SegmentContext], terms: list[str], limit: int = 5
) -> str:
    lines = []
    seen: set[tuple[str, str]] = set()
    for context in contexts:
        if any(term in context.text for term in terms):
            key = (context.document_type, context.filename)
            if key in seen:
                continue
            seen.add(key)
            lines.append(evidence_line(context, context_quote(context, terms)))
        if len(lines) >= limit:
            break
    return "\n".join(lines)


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", value).strip("。；;")


def unique_normalized(values: dict[str, str] | dict[str, LabeledEvidence]) -> set[str]:
    normalized_values = []
    for value in values.values():
        if isinstance(value, LabeledEvidence):
            normalized_values.append(value.value)
        elif value:
            normalized_values.append(value)
    return {normalize(value) for value in normalized_values if value}


def document_types(contexts: list[SegmentContext]) -> set[str]:
    return {context.document_type for context in contexts}


def has_document(contexts: list[SegmentContext], *types: str) -> bool:
    available = document_types(contexts)
    return any(document_type in available for document_type in types)


def triggered_features(
    project: Project,
    master: ProductMasterData,
    contexts: list[SegmentContext],
) -> dict[str, bool]:
    text = all_text(contexts)
    model_text = master.model_specifications or first_label_value(text, ["型号规格", "型号"])
    return {
        "has_software": project.has_software
        or bool(master.software_name or master.software_version)
        or contains_any(text, ["软件", "版本", "嵌入式程序"]),
        "is_networked": project.is_networked
        or master.is_networked
        or contains_any(
            text,
            ["联网", "网络连接", "远程", "云端", "数据传输", "电子数据交换", "用户登录", "USB", "存储介质"],
        ),
        "has_ai": project.has_ai
        or contains_any(
            text,
            ["人工智能", "AI", "深度学习", "机器学习", "算法", "辅助诊断", "自动识别", "分割", "预测", "自动推荐"],
        ),
        "outputs_energy": project.outputs_energy
        or master.outputs_energy
        or contains_any(
            text,
            ["输出能量", "射频", "微波", "脉冲电场", "激光", "超声", "辐射", "消融", "电刺激"],
        ),
        "multi_model": bool(re.search(r"(、|,|，|/|;|；)", model_text)),
        "clinical_claim": contains_any(
            text, ["治疗", "诊断", "辅助诊断", "准确率", "灵敏度", "特异性", "疗效", "适应症"]
        ),
        "electrical_device": contains_any(text, ["有源", "电气", "供电", "电源", "EMC", "电磁兼容", "GB 9706", "IEC 60601"]),
    }


def check_document_completeness(
    contexts: list[SegmentContext],
    project_id: int,
    session: Session,
    triggers: dict[str, bool],
) -> list[Finding]:
    findings: list[Finding] = []
    available = document_types(contexts)
    for document_type, label in REQUIRED_DOCUMENT_TYPES.items():
        if document_type not in available:
            level = "red" if document_type in {"technical_requirements", "test_report", "risk_management"} else "yellow"
            findings.append(
                make_completeness_finding(
                    session=session,
                    contexts=contexts,
                    project_id=project_id,
                    rule_id=f"COMPLETE-{document_type.upper()}",
                    risk_level=level,
                    title=f"缺少{label}",
                    description=f"当前资料包未识别到“{label}”。这是注册资料预审的基础断点。",
                    recommended_action=f"补充或上传{label}；如确实不适用，应提交不适用理由和证据。",
                    category="资料完整性",
                    owner="注册负责人",
                    workload="内部补资料/注册整理",
                )
            )
    if triggers.get("has_software") and not has_document(contexts, "software"):
        findings.append(
            make_finding(
                session,
                contexts,
                project_id,
                "COMPLETE-SOFTWARE",
                "资料中出现软件、版本、嵌入式程序或算法相关特征，但未上传软件研究资料。",
                ["软件", "版本", "嵌入式程序"],
                evidence_text=missing_special_evidence(
                    contexts,
                    ["软件", "版本", "嵌入式程序"],
                    "软件研究资料",
                    "未上传或未识别到软件研究资料。",
                ),
            )
        )
    if triggers.get("is_networked") and not has_document(contexts, "cybersecurity"):
        findings.append(
            make_finding(
                session,
                contexts,
                project_id,
                "COMPLETE-CYBERSECURITY",
                "资料中出现联网、远程、云端、数据传输、用户登录、USB/存储介质交换等触发词。",
                ["联网", "远程", "云端", "数据传输", "用户登录", "USB"],
                evidence_text=missing_special_evidence(
                    contexts,
                    ["联网", "远程", "云端", "数据传输", "用户登录", "USB"],
                    "网络安全研究资料",
                    "未上传或未识别到网络安全研究资料。",
                ),
            )
        )
    if triggers.get("has_ai") and not has_document(contexts, "algorithm", "ai_algorithm"):
        findings.append(
            make_finding(
                session,
                contexts,
                project_id,
                "COMPLETE-AI-ALGORITHM",
                "资料中存在人工智能、深度学习、辅助诊断、自动识别、分割或预测等声称。",
                ["人工智能", "AI", "深度学习", "算法", "辅助诊断", "自动识别", "预测", "自动推荐"],
                evidence_text=missing_special_evidence(
                    contexts,
                    ["人工智能", "AI", "深度学习", "算法", "辅助诊断", "自动识别", "预测", "自动推荐"],
                    "AI/算法研究资料",
                    "未上传或未识别到算法基本信息、训练/验证数据和性能评价资料。",
                ),
            )
        )
    return findings


def make_completeness_finding(
    *,
    session: Session,
    contexts: list[SegmentContext],
    project_id: int,
    rule_id: str,
    risk_level: str,
    title: str,
    description: str,
    recommended_action: str,
    category: str,
    owner: str,
    workload: str,
) -> Finding:
    regulation = verified_regulation(session, "general_submission")
    return Finding(
        project_id=project_id,
        rule_id=rule_id,
        regulation_id=regulation.id if regulation else None,
        risk_level=risk_level,
        title=title,
        description=description,
        evidence_quote=missing_evidence_line(title, "未上传或未识别到对应资料。"),
        possible_impact="可能导致申报资料不完整、内部预审无法闭环，正式申报时形成发补或退回风险。",
        recommended_action=recommended_action,
        owner=owner,
        workload=workload,
        category=category,
        confidence_status="pending_evidence" if not contexts else "evidence_based",
        source_type="rule",
        review_status="confirmed",
    )


def missing_special_evidence(
    contexts: list[SegmentContext],
    terms: list[str],
    document_name: str,
    statement: str,
) -> str:
    return "\n".join(
        part
        for part in [
            format_term_evidence(contexts, terms),
            missing_evidence_line(document_name, statement),
        ]
        if part
    )


def check_name_consistency(contexts: list[SegmentContext], project_id: int, session: Session) -> Finding | None:
    values = labeled_evidence(contexts, ["产品名称", "注册产品名称"])
    if len(unique_normalized(values)) > 1:
        return make_finding(
            session,
            contexts,
            project_id,
            "R-NAME-CONSISTENCY",
            "不同资料中的产品名称写法不一致，需确认是否为同一注册产品并统一法定名称。",
            ["产品名称"],
            evidence_text=format_labeled_evidence(values),
        )
    return None


def check_model_consistency(contexts: list[SegmentContext], project_id: int, session: Session) -> Finding | None:
    values = labeled_evidence(contexts, ["型号规格", "型号"])
    if len(unique_normalized(values)) > 1:
        return make_finding(
            session,
            contexts,
            project_id,
            "R-MODEL-CONSISTENCY",
            "不同资料中的型号规格写法不一致，需确认注册单元、型号清单和代表型号覆盖关系。",
            ["型号规格", "型号"],
            evidence_text=format_labeled_evidence(values),
        )
    return None


def check_structure_consistency(contexts: list[SegmentContext], project_id: int, session: Session) -> Finding | None:
    overview = text_for(contexts, "overview")
    instructions = text_for(contexts, "instructions")
    if "温度监测模块" in overview and "温度监测模块" not in instructions:
        overview_context = first_context(contexts, "overview")
        instructions_context = first_context(contexts, "instructions")
        evidence_lines = []
        if overview_context:
            overview_value = first_label_value(overview_context.text, ["结构组成"]) or "包含温度监测模块"
            evidence_lines.append(evidence_line(overview_context, f"结构组成：{overview_value}"))
        if instructions_context:
            instruction_value = first_label_value(instructions_context.text, ["结构组成"]) or "未见结构组成"
            evidence_lines.append(evidence_line(instructions_context, f"结构组成：{instruction_value}"))
        return make_finding(
            session,
            contexts,
            project_id,
            "R-STRUCTURE-CONSISTENCY",
            "综述资料包含温度监测模块，但说明书结构组成未体现该模块。",
            ["温度监测模块", "结构组成"],
            evidence_text="\n".join(evidence_lines),
        )
    return None


def check_intended_use(contexts: list[SegmentContext], project_id: int, session: Session) -> Finding | None:
    overview = text_for(contexts, "overview")
    instructions = text_for(contexts, "instructions")
    if "肝脏肿瘤" in overview and "实体肿瘤" in instructions:
        values = labeled_evidence(contexts, ["适用范围"])
        return make_finding(
            session,
            contexts,
            project_id,
            "R-INTENDED-USE",
            "说明书写为实体肿瘤，范围大于综述资料中的肝脏肿瘤。",
            ["实体肿瘤", "肝脏肿瘤", "适用范围"],
            evidence_text=format_labeled_evidence(values),
        )
    return None


def check_software_version(contexts: list[SegmentContext], project_id: int, session: Session) -> Finding | None:
    values = labeled_evidence(contexts, ["软件版本"])
    if len(unique_normalized(values)) > 1:
        return make_finding(
            session,
            contexts,
            project_id,
            "R-SOFTWARE-VERSION",
            "软件版本在不同资料之间不一致，需确认检验报告、说明书和软件研究资料对应同一发布版本。",
            ["软件版本", "V1.0."],
            evidence_text=format_labeled_evidence(values),
        )
    return None


def check_network_security(
    contexts: list[SegmentContext],
    project_id: int,
    session: Session,
    project: Project,
    master: ProductMasterData,
) -> Finding | None:
    text = all_text(contexts)
    network_doc = text_for(contexts, "cybersecurity")
    network_triggered = project.is_networked or master.is_networked or contains_any(
        text, ["联网", "Wi-Fi", "远程升级", "远程维护", "医院网络", "数据上传"]
    )
    has_control = contains_any(network_doc, ["身份鉴别", "权限控制", "访问控制", "日志审计", "加密"])
    if network_triggered and (not network_doc or not has_control):
        evidence_text = format_term_evidence(
            contexts, ["联网", "Wi-Fi", "远程升级", "远程维护", "数据上传"]
        )
        if not network_doc:
            evidence_text = "\n".join(
                part
                for part in [
                    evidence_text,
                    missing_evidence_line("网络安全研究资料", "未上传或未识别到网络安全研究资料。"),
                ]
                if part
            )
        elif not has_control:
            network_context = first_context(contexts, "cybersecurity")
            if network_context:
                evidence_text = "\n".join(
                    [
                        evidence_text,
                        evidence_line(
                            network_context,
                            "未见身份鉴别、权限控制、日志审计、传输加密等关键控制项。",
                        ),
                    ]
                )
        return make_finding(
            session,
            contexts,
            project_id,
            "R-NETWORK-SECURITY",
            "资料出现联网、远程升级或远程维护信息，但网络安全资料缺失或未覆盖关键控制项。",
            ["联网", "Wi-Fi", "远程升级", "远程维护", "网络安全"],
            evidence_text=evidence_text,
        )
    return None


def check_test_coverage(contexts: list[SegmentContext], project_id: int, session: Session) -> Finding | None:
    technical = text_for(contexts, "technical_requirements")
    test_report = text_for(contexts, "test_report")
    if "温度精度" in technical and "温度精度" not in test_report:
        technical_context = first_context(contexts, "technical_requirements")
        report_context = first_context(contexts, "test_report")
        evidence_lines = []
        if technical_context:
            evidence_lines.append(evidence_line(technical_context, context_quote(technical_context, ["温度精度"])))
        if report_context:
            evidence_lines.append(evidence_line(report_context, "检验项目中未见“温度精度”项目。"))
        return make_finding(
            session,
            contexts,
            project_id,
            "R-TEST-COVERAGE",
            "产品技术要求包含温度精度指标，但检验报告未见对应检验项目。",
            ["温度精度", "检验项目"],
            evidence_text="\n".join(evidence_lines),
        )
    return None


def check_standard_version(contexts: list[SegmentContext], project_id: int, session: Session) -> Finding | None:
    text = all_text(contexts)
    if "GB 9706.1-2007" in text or "YY 0505-2012" in text:
        evidence_text = format_term_evidence(contexts, ["GB 9706.1-2007", "YY 0505-2012"])
        return make_finding(
            session,
            contexts,
            project_id,
            "R-STANDARD-VERSION",
            "资料引用 GB 9706.1-2007 或 YY 0505-2012，需核对是否仍为现行适用版本。",
            ["GB 9706.1-2007", "YY 0505-2012"],
            evidence_text=evidence_text,
        )
    return None


def check_service_life(
    contexts: list[SegmentContext],
    project_id: int,
    session: Session,
    master: ProductMasterData,
) -> Finding | None:
    text = all_text(contexts)
    has_service_life = bool(master.service_life) or "使用期限" in text
    has_reliability = "可靠性研究" in text or "使用期限研究" in text
    if has_service_life and not has_reliability:
        evidence_text = "\n".join(
            part
            for part in [
                format_term_evidence(contexts, ["使用期限", "8年"]),
                missing_evidence_line("使用期限和可靠性资料", "未上传或未识别到支持“使用期限”的研究资料。"),
            ]
            if part
        )
        return make_finding(
            session,
            contexts,
            project_id,
            "R-SERVICE-LIFE",
            "说明书或综述声明使用期限，但资料包未见可靠性研究或使用期限研究资料。",
            ["使用期限", "8年"],
            evidence_text=evidence_text,
        )
    return None


def check_disposable_conflict(
    contexts: list[SegmentContext],
    project_id: int,
    session: Session,
    project: Project,
    master: ProductMasterData,
) -> Finding | None:
    text = all_text(contexts)
    disposable = project.has_disposable_accessory or master.has_disposable_accessory or "一次性" in text
    if disposable and contains_any(text, ["重复使用", "清洁消毒后再用", "清洁消毒后重复使用"]):
        evidence_text = format_term_evidence(contexts, ["一次性", "重复使用", "清洁消毒后再用"])
        return make_finding(
            session,
            contexts,
            project_id,
            "R-DISPOSABLE-CONFLICT",
            "资料声明一次性附件，但说明书出现清洁消毒后重复使用的表述。",
            ["一次性", "重复使用", "清洁消毒后再用"],
            evidence_text=evidence_text,
        )
    return None


def check_contraindication(contexts: list[SegmentContext], project_id: int, session: Session) -> Finding | None:
    risk = text_for(contexts, "risk_management")
    instructions = text_for(contexts, "instructions")
    if "禁忌" in risk and "起搏器" in risk and "起搏器" not in instructions:
        risk_context = first_context(contexts, "risk_management")
        instructions_context = first_context(contexts, "instructions")
        evidence_lines = []
        if risk_context:
            evidence_lines.append(evidence_line(risk_context, context_quote(risk_context, ["起搏器", "禁忌"])))
        if instructions_context:
            evidence_lines.append(evidence_line(instructions_context, "禁忌证中未见“植入式心脏起搏器患者禁用”。"))
        return make_finding(
            session,
            contexts,
            project_id,
            "R-CONTRAINDICATION",
            "风险管理资料列明植入式心脏起搏器患者禁用，但说明书未体现该禁忌。",
            ["禁忌", "起搏器"],
            evidence_text="\n".join(evidence_lines),
        )
    return None


def check_unsupported_claim(contexts: list[SegmentContext], project_id: int, session: Session) -> Finding | None:
    instructions = text_for(contexts, "instructions")
    if "精准消融" in instructions and "精准消融验证" not in all_text(contexts):
        evidence_text = "\n".join(
            part
            for part in [
                format_term_evidence(contexts, ["精准消融"]),
                missing_evidence_line("验证资料", "未识别到支持“精准消融”声称的验证证据。"),
            ]
            if part
        )
        return make_finding(
            session,
            contexts,
            project_id,
            "R-UNSUPPORTED-CLAIM",
            "说明书包含精准消融声称，但资料包未见对应验证证据。",
            ["精准消融"],
            evidence_text=evidence_text,
        )
    return None


def check_representative_model(
    contexts: list[SegmentContext],
    project_id: int,
    session: Session,
    master: ProductMasterData,
) -> Finding | None:
    text = all_text(contexts)
    models = master.model_specifications or first_label_value(text, ["型号规格", "型号"])
    tested = master.tested_model or first_label_value(text, ["检验型号", "检测型号"])
    has_multiple_models = bool(re.search(r"A100[、,，/ ]+A200|A100.*A200", models))
    if has_multiple_models and tested == "A100" and "代表型号" not in text:
        evidence_text = "\n".join(
            part
            for part in [
                format_term_evidence(contexts, ["A100", "A200", "检验型号"], limit=4),
                missing_evidence_line("代表型号覆盖说明", "未上传或未识别到 A100 覆盖 A200 的代表性说明。"),
            ]
            if part
        )
        return make_finding(
            session,
            contexts,
            project_id,
            "R-REPRESENTATIVE-MODEL",
            "资料包含 A100/A200 多个型号，但仅检验 A100 且未见代表型号覆盖说明。",
            ["A100", "A200", "检验型号"],
            evidence_text=evidence_text,
        )
    return None


def check_ai_algorithm(
    contexts: list[SegmentContext],
    project_id: int,
    session: Session,
    project: Project,
) -> Finding | None:
    text = all_text(contexts)
    ai_triggered = project.has_ai or contains_any(text, ["自动识别", "辅助诊断", "图像分割", "预测", "自动推荐"])
    algorithm_doc = text_for(contexts, "algorithm")
    if ai_triggered and not algorithm_doc:
        evidence_text = "\n".join(
            part
            for part in [
                format_term_evidence(contexts, ["自动识别", "辅助诊断", "图像分割", "预测", "自动推荐", "AI"]),
                missing_evidence_line("算法研究资料", "未上传或未识别到算法基本信息、训练/验证数据和性能评价资料。"),
            ]
            if part
        )
        return make_finding(
            session,
            contexts,
            project_id,
            "R-AI-ALGORITHM",
            "资料出现自动推荐或智能算法相关功能，但未上传算法资料。",
            ["自动推荐", "AI", "算法"],
            evidence_text=evidence_text,
        )
    return None


def check_clinical_overclaim(contexts: list[SegmentContext], project_id: int, session: Session) -> Finding | None:
    clinical = text_for(contexts, "clinical_evaluation")
    if contains_any(clinical, ["免于临床评价", "无需临床评价"]) and contains_any(clinical, ["30例", "单臂"]):
        evidence_text = format_term_evidence(contexts, ["30例", "单臂", "免于临床评价"])
        return make_finding(
            session,
            contexts,
            project_id,
            "R-CLINICAL-OVERCLAIM",
            "临床评价资料仅描述 30 例单臂研究，却直接得出免于临床评价或临床证据充分的结论。",
            ["30例", "单臂", "免于临床评价"],
            evidence_text=evidence_text,
        )
    return None


def check_ptq_test_coverage(contexts: list[SegmentContext], project_id: int, session: Session) -> Finding | None:
    technical = text_for(contexts, "technical_requirements")
    test_report = text_for(contexts, "test_report")
    if not technical or not test_report:
        return None
    candidate_terms = sorted(
        set(
            re.findall(
                r"(?:输出功率|准确度|精度|能量|温度|剂量|灵敏度|特异性|电气安全|EMC|电磁兼容|报警|软件版本|网络安全)[^。；;\n]{0,16}",
                technical,
                re.I,
            )
        )
    )
    missing = [
        term.strip()
        for term in candidate_terms
        if term.strip() and term.strip() not in test_report and term.strip()[:6] not in test_report
    ]
    if missing:
        return make_finding(
            session,
            contexts,
            project_id,
            "PTQ-TEST-COVERAGE",
            "产品技术要求中部分性能/安全指标未在检测报告文本中找到对应项目。",
            ["产品技术要求", "检验报告", "检测报告"],
            evidence_text="未覆盖示例：" + "；".join(missing[:10]),
        )
    return None


def check_multi_model_coverage(
    contexts: list[SegmentContext],
    project_id: int,
    session: Session,
    master: ProductMasterData,
) -> Finding | None:
    text = all_text(contexts)
    models = master.model_specifications or first_label_value(text, ["型号规格", "型号"])
    has_multiple_models = bool(re.search(r"(、|,|，|/|;|；)", models))
    has_coverage_logic = contains_any(text, ["代表型号", "最不利型号", "覆盖", "差异比较", "型号差异"])
    if has_multiple_models and not has_coverage_logic:
        evidence_text = "\n".join(
            part
            for part in [
                format_term_evidence(contexts, ["型号规格", "型号", "检验型号"], limit=4),
                missing_evidence_line("代表型号/型号差异说明", "未识别到代表型号选择依据或型号差异比较。"),
            ]
            if part
        )
        return make_finding(
            session,
            contexts,
            project_id,
            "MULTI-MODEL-COVERAGE",
            "资料中出现多个型号规格，但未识别到代表型号选择依据或型号差异比较。",
            ["型号规格", "型号", "检验型号"],
            evidence_text=evidence_text,
        )
    return None


def check_configured_obligations(
    contexts: list[SegmentContext],
    project_id: int,
    session: Session,
    triggers: dict[str, bool],
) -> list[Finding]:
    combined = all_text(contexts)
    rule_config = load_rule_config()
    findings: list[Finding] = []
    for obligation in matching_obligations(triggers):
        missing = [evidence for evidence in obligation.evidence_required if evidence not in combined]
        if not missing:
            continue
        category = obligation.module
        trigger_line = "；".join(
            f"{key}={triggers.get(key, False)}" for key in obligation.applies_when
        )
        findings.append(
            Finding(
                project_id=project_id,
                rule_id=f"OBLIGATION-{obligation.id}",
                risk_level=obligation.risk_if_missing,
                title=f"法规义务证据缺口：{obligation.title}",
                description=(
                    f"触发条件：{'、'.join(obligation.applies_when)}；"
                    f"缺少证据：{'、'.join(missing[:8])}。"
                ),
                evidence_quote=f"项目触发器：{trigger_line}；缺少证据：{'、'.join(missing[:8])}。",
                possible_impact="条款级义务缺少材料证据，可能转化为发补问题。",
                recommended_action=f"按义务库补齐证据：{'、'.join(obligation.evidence_required)}。",
                owner=obligation.suggested_owner or OWNER_BY_CATEGORY.get(category, "注册负责人"),
                workload="专项资料补充/模板更新",
                category=category,
                confidence_status="pending_evidence",
                source_type="rule",
                review_status="confirmed",
                regulation_title=obligation.source_title,
                regulation_evidence_quote=(
                    f"权威等级：{obligation.authority_level}；"
                    f"规则配置版本：{rule_config.get('version', 'unknown')}。"
                    "该义务库条目需法规负责人逐条 verified 后才能作为最终法规结论。"
                ),
            )
        )
    return findings
