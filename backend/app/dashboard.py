from __future__ import annotations

from collections import Counter
from typing import Any

from sqlmodel import Session, select

from backend.app.models import Finding, Project


def build_dashboard(session: Session, project_id: int) -> dict[str, Any]:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError("Project not found")

    findings = session.exec(
        select(Finding)
        .where(Finding.project_id == project_id)
        .order_by(Finding.id)
    ).all()
    active_findings = [finding for finding in findings if finding.review_status != "rejected"]
    risk_counts = Counter(finding.risk_level for finding in active_findings)
    category_counts = Counter(finding.category or "未分类" for finding in active_findings)
    owner_counts = Counter(finding.owner or "未分配" for finding in active_findings)
    readiness_score = max(
        0,
        100
        - risk_counts.get("red", 0) * 15
        - risk_counts.get("yellow", 0) * 5
        - risk_counts.get("green", 0),
    )
    major_breakpoints = [
        finding for finding in active_findings if finding.risk_level == "red"
    ][:8]
    next_actions = [
        {
            "title": finding.title,
            "owner": finding.owner or "注册负责人",
            "action": finding.recommended_action,
            "workload": finding.workload or "资料修订/人工确认",
        }
        for finding in major_breakpoints[:5]
    ]
    return {
        "project_id": project_id,
        "readiness_score": readiness_score,
        "risk_counts": {
            "red": risk_counts.get("red", 0),
            "yellow": risk_counts.get("yellow", 0),
            "green": risk_counts.get("green", 0),
        },
        "category_counts": dict(category_counts),
        "owner_counts": dict(owner_counts),
        "major_breakpoints": major_breakpoints,
        "next_actions": next_actions,
        "boss_summary": (
            f"项目“{project.name}”当前申报准备度 {readiness_score}/100；"
            f"红色断点 {risk_counts.get('red', 0)} 项，黄色风险 {risk_counts.get('yellow', 0)} 项。"
            "优先处理资料缺失、主数据不一致、软件/网络安全、PTQ-检测覆盖和说明书声称证据闭环。"
        ),
    }
