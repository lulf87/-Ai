from pathlib import Path

from docx import Document
from fastapi.testclient import TestClient

from backend.app.database import reset_database
from backend.app.llm import LLMProviderResult
from backend.app.main import app


def make_client():
    reset_database()
    return TestClient(app)


def create_golden_project(client: TestClient) -> dict:
    project = client.post(
        "/projects",
        json={
            "name": "微波消融黄金测试",
            "registration_scenario": "国产三类首次注册",
            "origin_type": "domestic",
            "application_type": "initial",
            "device_class": "III",
            "classification_code": "",
            "has_software": True,
            "is_networked": True,
            "has_ai": True,
            "outputs_energy": True,
            "has_disposable_accessory": True,
        },
    ).json()

    for sample in sorted(Path("samples/golden/microwave_ablation").glob("*.md")):
        response = client.post(
            f"/projects/{project['id']}/documents",
            files={"file": (sample.name, sample.read_bytes(), "text/markdown")},
            data={"document_type": sample.stem.split("_", 1)[1]},
        )
        assert response.status_code == 200
    return project


def report_text(filename: str) -> str:
    path = Path("reports/generated") / filename
    document = Document(path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def test_backend_root_is_a_helpful_entrypoint():
    client = make_client()

    response = client.get("/")

    assert response.status_code == 200
    assert "注册资料预审" in response.text


def test_unverified_regulation_cannot_be_referenced_by_findings(tmp_path):
    client = make_client()

    project = client.post(
        "/projects",
        json={
            "name": "微波消融黄金测试",
            "registration_scenario": "国产三类首次注册",
            "origin_type": "domestic",
            "application_type": "initial",
            "device_class": "III",
            "classification_code": "",
            "has_software": True,
            "is_networked": True,
            "has_ai": True,
            "outputs_energy": True,
            "has_disposable_accessory": True,
        },
    ).json()

    regulation = client.post(
        "/regulations",
        json={
            "title": "医疗器械网络安全注册审查指导原则",
            "reference_number": "CMDE 网络安全指导原则",
            "publication_date": "2022-03-01",
            "official_url": "https://www.cmde.org.cn/",
            "attachment_filename": "network-security.pdf",
            "attachment_sha256": "abc123",
            "applicable_modules": ["network_security"],
        },
    ).json()

    sample = Path("samples/golden/microwave_ablation/03_instructions.md")
    response = client.post(
        f"/projects/{project['id']}/documents",
        files={"file": (sample.name, sample.read_bytes(), "text/markdown")},
        data={"document_type": "instructions"},
    )
    assert response.status_code == 200

    run = client.post(f"/projects/{project['id']}/run-checks")
    assert run.status_code == 200
    findings = run.json()["findings"]
    assert findings
    assert all(f["regulation_id"] is None for f in findings)

    verified = client.patch(
        f"/regulations/{regulation['id']}/verify",
        json={"verification_status": "verified", "verified_by": "tester"},
    )
    assert verified.status_code == 200

    rerun = client.post(f"/projects/{project['id']}/run-checks")
    assert rerun.status_code == 200
    verified_findings = rerun.json()["findings"]
    assert any(f["regulation_id"] == regulation["id"] for f in verified_findings)


def test_master_data_endpoint_returns_empty_record_before_extraction():
    client = make_client()
    project = client.post(
        "/projects",
        json={
            "name": "空主数据项目",
            "registration_scenario": "国产三类首次注册",
        },
    ).json()

    response = client.get(f"/projects/{project['id']}/master-data")

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project["id"]
    assert body["product_name"] == ""


def test_project_can_load_golden_sample_documents_from_ui_flow():
    client = make_client()
    project = client.post(
        "/projects",
        json={
            "name": "样例加载项目",
            "registration_scenario": "国产三类首次注册",
        },
    ).json()

    response = client.post(f"/projects/{project['id']}/sample-documents/golden-microwave")

    assert response.status_code == 200
    documents = response.json()
    assert len(documents) >= 7
    assert {doc["parse_status"] for doc in documents} == {"parsed"}


def test_golden_dataset_identifies_at_least_fourteen_seeded_issues(tmp_path):
    client = make_client()
    project = client.post(
        "/projects",
        json={
            "name": "微波消融黄金测试",
            "registration_scenario": "国产三类首次注册",
            "origin_type": "domestic",
            "application_type": "initial",
            "device_class": "III",
            "classification_code": "",
            "has_software": True,
            "is_networked": True,
            "has_ai": True,
            "outputs_energy": True,
            "has_disposable_accessory": True,
        },
    ).json()

    for sample in sorted(Path("samples/golden/microwave_ablation").glob("*.md")):
        client.post(
            f"/projects/{project['id']}/documents",
            files={"file": (sample.name, sample.read_bytes(), "text/markdown")},
            data={"document_type": sample.stem.split("_", 1)[1]},
        )

    extraction = client.post(f"/projects/{project['id']}/extract-master-data")
    assert extraction.status_code == 200
    master = extraction.json()
    assert master["product_name"] == "微波消融治疗系统"
    assert master["software_version"] == "V1.0.3"

    run = client.post(f"/projects/{project['id']}/run-checks")
    assert run.status_code == 200
    findings = run.json()["findings"]
    must_find = {
        "R-NAME-CONSISTENCY",
        "R-MODEL-CONSISTENCY",
        "R-INTENDED-USE",
        "R-SOFTWARE-VERSION",
        "R-NETWORK-SECURITY",
        "R-TEST-COVERAGE",
        "R-STANDARD-VERSION",
        "R-SERVICE-LIFE",
        "R-DISPOSABLE-CONFLICT",
        "R-CONTRAINDICATION",
        "R-STRUCTURE-CONSISTENCY",
        "R-UNSUPPORTED-CLAIM",
        "R-REPRESENTATIVE-MODEL",
        "R-AI-ALGORITHM",
    }
    found_rule_ids = {finding["rule_id"] for finding in findings}
    assert must_find.issubset(found_rule_ids)
    assert len(findings) >= 14
    name_finding = next(
        finding for finding in findings if finding["rule_id"] == "R-NAME-CONSISTENCY"
    )
    assert "综述资料（01_overview.md" in name_finding["evidence_quote"]
    assert "产品名称：微波消融治疗系统" in name_finding["evidence_quote"]
    assert "使用说明书（03_instructions.md" in name_finding["evidence_quote"]
    assert "产品名称：肝脏微波消融系统" in name_finding["evidence_quote"]

    report = client.post(f"/projects/{project['id']}/reports")
    assert report.status_code == 200
    body = report.json()
    assert body["filename"].endswith(".docx")
    assert "能否获批" not in body["summary"]


def test_ai_extract_records_desensitized_llm_run_and_field_evidence():
    client = make_client()
    project = create_golden_project(client)

    response = client.post(f"/projects/{project['id']}/ai/extract-master-data")

    assert response.status_code == 200
    body = response.json()
    assert body["master_data"]["product_name"] == "微波消融治疗系统"
    assert body["master_data"]["software_version"] == "V1.0.3"
    assert any(span["field_name"] == "product_name" for span in body["evidence_spans"])
    assert body["llm_run"]["task_type"] == "extract_master_data"
    assert body["llm_run"]["contains_sensitive_content"] is False
    assert "植入式心脏起搏器患者禁用" not in body["llm_run"]["input_summary"]


def test_ai_extract_normalizes_structured_field_values(monkeypatch):
    class StructuredFieldProvider:
        provider_name = "structured-test"
        model_name = "structured-test-model"

        def extract_master_data(self, segments, fallback_master_data):
            return LLMProviderResult(
                output_json={
                    "fields": {
                        "model_specifications": ["A100", "A200"],
                        "structure_composition": [
                            "主机",
                            "微波消融探针",
                            "脚踏开关",
                        ],
                        "applicable_standards": ["GB 9706.1-2007", "YY 0505-2012"],
                        "is_networked": "是",
                        "outputs_energy": "输出",
                        "has_disposable_accessory": ["否"],
                    },
                    "evidence": [],
                },
                output_text="返回数组字段用于回归测试。",
                provider=self.provider_name,
                model_name=self.model_name,
                model_config={},
            )

    client = make_client()
    project = create_golden_project(client)
    monkeypatch.setattr(
        "backend.app.ai_services.get_llm_provider",
        lambda: StructuredFieldProvider(),
    )

    response = client.post(f"/projects/{project['id']}/ai/extract-master-data")

    assert response.status_code == 200, response.text
    master = response.json()["master_data"]
    assert master["model_specifications"] == "A100、A200"
    assert master["structure_composition"] == "主机、微波消融探针、脚踏开关"
    assert master["applicable_standards"] == "GB 9706.1-2007、YY 0505-2012"
    assert master["is_networked"] is True
    assert master["outputs_energy"] is True
    assert master["has_disposable_accessory"] is False


def test_ai_candidates_require_review_and_report_filters_pending_and_rejected_items():
    client = make_client()
    project = create_golden_project(client)
    client.post(f"/projects/{project['id']}/extract-master-data")
    client.post(f"/projects/{project['id']}/run-checks")

    ai_response = client.post(f"/projects/{project['id']}/ai/analyze-risks")

    assert ai_response.status_code == 200
    candidates = ai_response.json()["findings"]
    assert len(candidates) >= 2
    assert {finding["source_type"] for finding in candidates} == {"llm_candidate"}
    assert {finding["review_status"] for finding in candidates} == {"pending_review"}

    first_report = client.post(f"/projects/{project['id']}/reports").json()
    first_text = report_text(first_report["filename"])
    assert "智能辅助分析，非最终注册结论，需人工复核" in first_text
    assert candidates[0]["title"] not in first_text

    confirmed = client.post(
        f"/findings/{candidates[0]['id']}/review",
        json={"review_status": "confirmed"},
    )
    rejected = client.post(
        f"/findings/{candidates[1]['id']}/review",
        json={"review_status": "rejected"},
    )
    assert confirmed.status_code == 200
    assert rejected.status_code == 200

    final_report = client.post(f"/projects/{project['id']}/reports").json()
    final_text = report_text(final_report["filename"])
    assert candidates[0]["title"] in final_text
    assert candidates[1]["title"] not in final_text


def test_regulation_ai_impact_stays_draft_until_manual_verification():
    client = make_client()
    regulation = client.post(
        "/regulations",
        json={
            "title": "有源医疗器械软件注册审查指导原则",
            "reference_number": "CMDE 软件指导原则",
            "publication_date": "2025-01-01",
            "official_url": "https://www.cmde.org.cn/",
            "attachment_filename": "software-guideline.pdf",
            "attachment_sha256": "def456",
            "applicable_modules": ["software"],
        },
    ).json()

    response = client.post(f"/regulations/{regulation['id']}/ai/summarize-impact")

    assert response.status_code == 200
    draft = response.json()
    assert draft["verification_status"] == "pending_review"
    assert "software" in draft["impacted_modules"]
    regulations = client.get("/regulations").json()
    assert regulations[0]["verification_status"] == "pending"
