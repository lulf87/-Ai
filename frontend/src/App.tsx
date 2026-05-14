import {
  ClipboardCheck,
  Check,
  Download,
  FileText,
  LoaderCircle,
  Play,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

type Project = {
  id: number;
  name: string;
  registration_scenario: string;
  origin_type: string;
  application_type: string;
  device_class: string;
  classification_code: string;
  has_software: boolean;
  is_networked: boolean;
  has_ai: boolean;
  outputs_energy: boolean;
  has_disposable_accessory: boolean;
};

type DocumentRecord = {
  id: number;
  document_type: string;
  filename: string;
  sha256: string;
  parse_status: string;
  parse_error: string;
};

type MasterData = {
  id?: number;
  project_id?: number;
  product_name?: string;
  model_specifications?: string;
  structure_composition?: string;
  intended_use?: string;
  use_environment?: string;
  users?: string;
  software_name?: string;
  software_version?: string;
  is_networked?: boolean;
  energy_type?: string;
  outputs_energy?: boolean;
  has_disposable_accessory?: boolean;
  service_life?: string;
  tested_model?: string;
  applicable_standards?: string;
};

type Finding = {
  id: number;
  rule_id: string;
  regulation_id: number | null;
  risk_level: "red" | "yellow" | "green";
  title: string;
  description: string;
  evidence_document: string;
  evidence_locator: string;
  evidence_quote: string;
  possible_impact: string;
  recommended_action: string;
  confidence_status: string;
  source_type: "rule" | "llm_candidate" | "rule_llm_confirmed" | "manual";
  ai_rationale: string;
  review_status: "pending_review" | "confirmed" | "rejected" | "edited";
};

type EvidenceSpan = {
  id: number;
  field_name: string;
  filename: string;
  locator: string;
  quote: string;
};

type LLMRun = {
  id: number;
  task_type: string;
  provider: string;
  model_name: string;
  input_summary: string;
  contains_sensitive_content: boolean;
};

type Regulation = {
  id: number;
  title: string;
  reference_number: string;
  publication_date: string;
  official_url: string;
  attachment_filename: string;
  attachment_sha256: string;
  applicable_modules: string[];
  verification_status: string;
  verified_by: string;
};

type Report = {
  id: number;
  project_id: number;
  filename: string;
  summary: string;
};

type AIExtractResponse = {
  master_data: MasterData;
  evidence_spans: EvidenceSpan[];
  llm_run: LLMRun;
};

type AIRiskResponse = {
  findings: Finding[];
  llm_run: LLMRun;
};

type RegulationImpactDraft = {
  id: number;
  regulation_id: number;
  summary: string;
  impacted_modules: string[];
  suggested_rule_changes: string[];
  verification_status: string;
};

const emptyProject = {
  name: "微波消融治疗系统预审",
  registration_scenario: "国产三类首次注册",
  origin_type: "domestic",
  application_type: "initial",
  device_class: "III",
  classification_code: "",
  has_software: true,
  is_networked: true,
  has_ai: true,
  outputs_energy: true,
  has_disposable_accessory: true,
};

const masterFields: Array<[keyof MasterData, string]> = [
  ["product_name", "产品名称"],
  ["model_specifications", "型号规格"],
  ["structure_composition", "结构组成"],
  ["intended_use", "适用范围"],
  ["use_environment", "使用环境"],
  ["users", "使用者"],
  ["software_name", "软件名称"],
  ["software_version", "软件版本"],
  ["energy_type", "能量类型"],
  ["service_life", "使用期限"],
  ["tested_model", "检验型号"],
  ["applicable_standards", "适用标准"],
];

const documentTypeOptions = [
  { value: "application_form", label: "申请表", section: "监管信息", required: true },
  { value: "terms", label: "术语、缩写和符号说明", section: "监管信息", required: true },
  { value: "overview", label: "综述资料", section: "综述资料", required: true },
  { value: "technical_requirements", label: "产品技术要求", section: "非临床资料", required: true },
  { value: "test_report", label: "检验报告", section: "非临床资料", required: true },
  { value: "risk_management", label: "风险管理资料", section: "非临床资料", required: true },
  { value: "essential_principles", label: "基本原则符合性资料", section: "非临床资料", required: true },
  { value: "research", label: "非临床研究资料", section: "非临床资料", required: true },
  { value: "software", label: "软件研究资料", section: "专项研究", required: true },
  { value: "cybersecurity", label: "网络安全研究资料", section: "专项研究", required: false },
  { value: "algorithm", label: "算法研究资料", section: "专项研究", required: false },
  { value: "energy_safety", label: "输出能量安全研究资料", section: "专项研究", required: true },
  { value: "reliability", label: "使用期限和可靠性资料", section: "专项研究", required: true },
  { value: "usability", label: "可用性工程资料", section: "专项研究", required: true },
  { value: "clinical_evaluation", label: "临床评价资料", section: "临床资料", required: true },
  { value: "instructions", label: "说明书", section: "说明书和标签", required: true },
  { value: "labels", label: "标签样稿", section: "说明书和标签", required: true },
  { value: "quality_system", label: "质量管理体系资料", section: "质量体系", required: true },
] as const;

const documentTypeLabels = Object.fromEntries(
  documentTypeOptions.map((option) => [option.value, option.label])
) as Record<string, string>;

const masterFieldLabels: Record<string, string> = Object.fromEntries(
  masterFields.map(([key, label]) => [key, label])
);

const reviewStatusLabels: Record<Finding["review_status"], string> = {
  pending_review: "待人工确认",
  confirmed: "已确认",
  rejected: "已驳回",
  edited: "已修改确认",
};

const riskLevelLabels: Record<Finding["risk_level"], string> = {
  red: "高风险",
  yellow: "需关注",
  green: "通过",
};

const taskLabels: Record<string, string> = {
  extract_master_data: "主数据抽取",
  analyze_risks: "风险初筛",
  summarize_regulation_impact: "法规影响摘要",
  polish_report: "报告摘要润色",
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || response.statusText);
  }
  return response.json() as Promise<T>;
}

export function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [projectDraft, setProjectDraft] = useState(emptyProject);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [documentType, setDocumentType] = useState("overview");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [masterData, setMasterData] = useState<MasterData>({});
  const [findings, setFindings] = useState<Finding[]>([]);
  const [aiEvidenceSpans, setAiEvidenceSpans] = useState<EvidenceSpan[]>([]);
  const [latestAiRun, setLatestAiRun] = useState<LLMRun | null>(null);
  const [regulations, setRegulations] = useState<Regulation[]>([]);
  const [regulationImpacts, setRegulationImpacts] = useState<Record<number, RegulationImpactDraft>>({});
  const [regulationDraft, setRegulationDraft] = useState({
    title: "医疗器械注册申报资料要求和批准证明文件格式",
    reference_number: "国家药监局 2021年第121号",
    publication_date: "2021-09-30",
    official_url: "https://www.nmpa.gov.cn/ylqx/ylqxggtg/20210930155134148.html",
    attachment_filename: "人工校验附件.pdf",
    attachment_sha256: "manual-placeholder-sha256",
    applicable_modules: "general_submission,testing,network_security",
  });
  const [latestReport, setLatestReport] = useState<Report | null>(null);
  const [status, setStatus] = useState("就绪");
  const [busyTask, setBusyTask] = useState<string | null>(null);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) ?? null,
    [projects, selectedProjectId]
  );
  const uploadedDocumentTypes = useMemo(
    () => new Set(documents.map((document) => document.document_type)),
    [documents]
  );
  const checklistRows = useMemo(() => {
    const activeProject = selectedProject ?? projectDraft;
    return documentTypeOptions.map((option) => {
      const featureRequired =
        (option.value === "software" && activeProject.has_software) ||
        (option.value === "cybersecurity" && activeProject.is_networked) ||
        (option.value === "algorithm" && activeProject.has_ai) ||
        (option.value === "energy_safety" && activeProject.outputs_energy);
      const expected = option.required || featureRequired;
      const uploaded = uploadedDocumentTypes.has(option.value);
      return {
        ...option,
        expected,
        uploaded,
        status: uploaded ? "已上传" : expected ? "待补充" : "按产品情况准备",
      };
    });
  }, [documents, projectDraft, selectedProject, uploadedDocumentTypes]);

  useEffect(() => {
    refreshAll();
  }, []);

  useEffect(() => {
    if (selectedProjectId) {
      refreshProject(selectedProjectId);
    }
  }, [selectedProjectId]);

  async function refreshAll() {
    const [projectList, regulationList] = await Promise.all([
      request<Project[]>("/projects"),
      request<Regulation[]>("/regulations"),
    ]);
    setProjects(projectList);
    setRegulations(regulationList);
    if (!selectedProjectId && projectList.length) {
      setSelectedProjectId(projectList[0].id);
    }
  }

  async function refreshProject(projectId: number) {
    const [documentList, findingList] = await Promise.all([
      request<DocumentRecord[]>(`/projects/${projectId}/documents`),
      request<Finding[]>(`/projects/${projectId}/findings`),
    ]);
    setDocuments(documentList);
    setFindings(findingList);
    try {
      setMasterData(await request<MasterData>(`/projects/${projectId}/master-data`));
    } catch {
      setMasterData({});
    }
  }

  async function createProject(event: FormEvent) {
    event.preventDefault();
    setStatus("创建项目中");
    const project = await request<Project>("/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(projectDraft),
    });
    setProjects([project, ...projects]);
    setSelectedProjectId(project.id);
    setStatus("项目已创建");
  }

  async function uploadDocument(event: FormEvent) {
    event.preventDefault();
    if (!selectedProjectId || !uploadFile) return;
    setStatus("上传解析中");
    const body = new FormData();
    body.append("document_type", documentType);
    body.append("file", uploadFile);
    await request<DocumentRecord>(`/projects/${selectedProjectId}/documents`, {
      method: "POST",
      body,
    });
    setUploadFile(null);
    await refreshProject(selectedProjectId);
    setStatus("资料已解析");
  }

  async function loadGoldenSample() {
    if (!selectedProjectId) return;
    setStatus("加载黄金样例中");
    await request<DocumentRecord[]>(`/projects/${selectedProjectId}/sample-documents/golden-microwave`, {
      method: "POST",
    });
    await refreshProject(selectedProjectId);
    setStatus("黄金样例已加载");
  }

  async function extractMasterData() {
    if (!selectedProjectId) return;
    setStatus("抽取主数据中");
    const data = await request<MasterData>(`/projects/${selectedProjectId}/extract-master-data`, {
      method: "POST",
    });
    setMasterData(data);
    setStatus("主数据已抽取");
  }

  async function aiExtractMasterData() {
    if (!selectedProjectId) return;
    setBusyTask("ai-extract");
    setStatus("智能抽取主数据中，正在等待模型返回");
    try {
      const result = await request<AIExtractResponse>(
        `/projects/${selectedProjectId}/ai/extract-master-data`,
        { method: "POST" }
      );
      setMasterData(result.master_data);
      setAiEvidenceSpans(result.evidence_spans);
      setLatestAiRun(result.llm_run);
      setStatus(
        result.llm_run.provider === "fake"
          ? "智能抽取已完成：已使用本地安全兜底结果"
          : "智能抽取已完成，主数据候选已生成"
      );
    } catch (error) {
      setStatus(`智能抽取失败：${friendlyError(error)}`);
    } finally {
      setBusyTask(null);
    }
  }

  async function saveMasterData() {
    if (!selectedProjectId) return;
    setStatus("保存主数据中");
    const data = await request<MasterData>(`/projects/${selectedProjectId}/master-data`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(masterData),
    });
    setMasterData(data);
    setStatus("主数据已保存");
  }

  async function runChecks() {
    if (!selectedProjectId) return;
    setStatus("规则运行中");
    const result = await request<{ findings: Finding[] }>(`/projects/${selectedProjectId}/run-checks`, {
      method: "POST",
    });
    setFindings(result.findings);
    setStatus("规则已完成");
  }

  async function analyzeRisksWithAI() {
    if (!selectedProjectId) return;
    setBusyTask("ai-risk");
    setStatus("智能风险分析中，正在等待模型返回候选问题");
    try {
      const result = await request<AIRiskResponse>(`/projects/${selectedProjectId}/ai/analyze-risks`, {
        method: "POST",
      });
      setLatestAiRun(result.llm_run);
      await refreshProject(selectedProjectId);
      setStatus(
        result.llm_run.provider === "fake"
          ? `智能分析已生成 ${result.findings.length} 条候选问题：已使用本地安全兜底结果`
          : `智能分析已生成 ${result.findings.length} 条候选问题`
      );
    } catch (error) {
      setStatus(`智能风险分析失败：${friendlyError(error)}`);
    } finally {
      setBusyTask(null);
    }
  }

  async function reviewFinding(findingId: number, reviewStatus: "confirmed" | "rejected") {
    if (!selectedProjectId) return;
    setStatus(reviewStatus === "confirmed" ? "确认候选问题中" : "驳回候选问题中");
    await request<Finding>(`/findings/${findingId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ review_status: reviewStatus }),
    });
    await refreshProject(selectedProjectId);
    setStatus(reviewStatus === "confirmed" ? "候选问题已确认" : "候选问题已驳回");
  }

  async function createRegulation(event: FormEvent) {
    event.preventDefault();
    setStatus("录入法规中");
    await request<Regulation>("/regulations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...regulationDraft,
        applicable_modules: regulationDraft.applicable_modules
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      }),
    });
    setRegulations(await request<Regulation[]>("/regulations"));
    setStatus("法规已录入");
  }

  async function verifyRegulation(regulationId: number) {
    setStatus("校验法规中");
    await request<Regulation>(`/regulations/${regulationId}/verify`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ verification_status: "verified", verified_by: "内部校验" }),
    });
    setRegulations(await request<Regulation[]>("/regulations"));
    setStatus("法规已校验");
  }

  async function summarizeRegulationImpact(regulationId: number) {
    setStatus("智能摘要法规影响中");
    const draft = await request<RegulationImpactDraft>(
      `/regulations/${regulationId}/ai/summarize-impact`,
      { method: "POST" }
    );
    setRegulationImpacts((current) => ({ ...current, [regulationId]: draft }));
    setStatus("法规影响草稿已生成");
  }

  async function generateReport() {
    if (!selectedProjectId) return;
    setStatus("生成报告中");
    const report = await request<Report>(`/projects/${selectedProjectId}/reports`, {
      method: "POST",
    });
    setLatestReport(report);
    setStatus("报告已生成");
  }

  async function polishReportWithAI() {
    if (!latestReport) return;
    setStatus("智能润色报告摘要中");
    const result = await request<{ report: Report; llm_run: LLMRun }>(
      `/reports/${latestReport.id}/ai/polish`,
      { method: "POST" }
    );
    setLatestReport(result.report);
    setLatestAiRun(result.llm_run);
    setStatus("报告摘要已润色");
  }

  function updateMasterField(key: keyof MasterData, value: string | boolean) {
    setMasterData((current) => ({ ...current, [key]: value }));
  }

  function friendlyError(error: unknown) {
    if (!(error instanceof Error)) return "未知错误";
    try {
      const parsed = JSON.parse(error.message);
      if (typeof parsed.detail === "string") return parsed.detail;
    } catch {
      // Keep the original message below when it is not JSON.
    }
    return error.message.replace(/^Internal Server Error$/, "服务器处理失败，请稍后重试或联系维护人员");
  }

  function documentLabel(type: string) {
    return documentTypeLabels[type] ?? type;
  }

  function parseStatusLabel(status: string) {
    if (status === "parsed") return "已解析";
    if (status === "failed") return "解析失败";
    return "待解析";
  }

  function regulationStatusLabel(status: string) {
    if (status === "verified") return "已校验";
    if (status === "rejected") return "已退回";
    return "待校验";
  }

  function displayText(value: string) {
    return value.replace(/AI\s*功能/g, "智能算法功能").replace(/\bAI\b/g, "智能算法");
  }

  function sourceLabel(finding: Finding) {
    if (finding.source_type === "llm_candidate") {
      return finding.review_status === "pending_review" ? "智能候选" : "智能辅助";
    }
    if (finding.source_type === "rule_llm_confirmed") return "规则与智能辅助确认";
    if (finding.source_type === "manual") return "人工录入";
    return "规则发现";
  }

  function evidenceLines(finding: Finding) {
    const lines = finding.evidence_quote
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    if (lines.length) return lines;
    const line = [finding.evidence_document, finding.evidence_locator, finding.evidence_quote]
      .filter(Boolean)
      .join(" ");
    return line ? [line] : ["暂无可展示证据，请人工补充资料后复核。"];
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <ClipboardCheck size={22} />
          <span>注册资料预审</span>
        </div>
        <form className="project-form" onSubmit={createProject}>
          <label>
            项目名称
            <input
              value={projectDraft.name}
              onChange={(event) => setProjectDraft({ ...projectDraft, name: event.target.value })}
            />
          </label>
          <label>
            注册场景
            <input
              value={projectDraft.registration_scenario}
              onChange={(event) =>
                setProjectDraft({ ...projectDraft, registration_scenario: event.target.value })
              }
            />
          </label>
          <div className="project-form-grid">
            <label>
              产地
              <select
                value={projectDraft.origin_type}
                onChange={(event) => setProjectDraft({ ...projectDraft, origin_type: event.target.value })}
              >
                <option value="domestic">国产</option>
                <option value="imported">进口</option>
              </select>
            </label>
            <label>
              申报类型
              <select
                value={projectDraft.application_type}
                onChange={(event) =>
                  setProjectDraft({ ...projectDraft, application_type: event.target.value })
                }
              >
                <option value="initial">首次注册</option>
                <option value="change">变更注册</option>
                <option value="renewal">延续注册</option>
              </select>
            </label>
          </div>
          <div className="project-form-grid">
            <label>
              管理类别
              <select
                value={projectDraft.device_class}
                onChange={(event) =>
                  setProjectDraft({ ...projectDraft, device_class: event.target.value })
                }
              >
                <option value="III">第三类</option>
                <option value="II">第二类</option>
              </select>
            </label>
            <label>
              分类编码
              <input
                placeholder="如 01-03-04"
                value={projectDraft.classification_code}
                onChange={(event) =>
                  setProjectDraft({ ...projectDraft, classification_code: event.target.value })
                }
              />
            </label>
          </div>
          <div className="toggle-grid">
            {[
              ["has_software", "软件"],
              ["is_networked", "联网"],
              ["has_ai", "智能算法"],
              ["outputs_energy", "输出能量"],
              ["has_disposable_accessory", "一次性附件"],
            ].map(([key, label]) => (
              <label key={key} className="toggle-line">
                <input
                  type="checkbox"
                  checked={Boolean(projectDraft[key as keyof typeof projectDraft])}
                  onChange={(event) =>
                    setProjectDraft({ ...projectDraft, [key]: event.target.checked })
                  }
                />
                {label}
              </label>
            ))}
          </div>
          <button type="submit">
            <Plus size={16} />
            新建项目
          </button>
        </form>
        <div className="project-list">
          {projects.map((project) => (
            <button
              key={project.id}
              className={project.id === selectedProjectId ? "selected" : ""}
              onClick={() => setSelectedProjectId(project.id)}
            >
              {project.name}
            </button>
          ))}
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>{selectedProject?.name ?? "未选择项目"}</h1>
            <p>{selectedProject?.registration_scenario ?? status}</p>
            <div className={`status-pill ${busyTask ? "busy" : ""}`}>
              {busyTask && <LoaderCircle size={14} />}
              {status}
            </div>
          </div>
          <button onClick={refreshAll}>
            <RefreshCw size={16} />
            刷新
          </button>
        </header>

        <section className="band two-columns">
          <form className="panel" onSubmit={uploadDocument}>
            <div className="panel-title">
              <FileText size={18} />
              <h2>资料包</h2>
            </div>
            <div className="inline-fields">
              <select value={documentType} onChange={(event) => setDocumentType(event.target.value)}>
                {documentTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <input type="file" onChange={(event: ChangeEvent<HTMLInputElement>) => setUploadFile(event.target.files?.[0] ?? null)} />
              <button type="submit" disabled={!selectedProjectId || !uploadFile}>
                <Upload size={16} />
                上传
              </button>
              <button type="button" onClick={loadGoldenSample} disabled={!selectedProjectId}>
                <FileText size={16} />
                加载样例
              </button>
            </div>
            <div className="table-list">
              {documents.map((doc) => (
                <div key={doc.id} className="table-row">
                  <span>{documentLabel(doc.document_type)}</span>
                  <span>{doc.filename}</span>
                  <span className={doc.parse_status === "parsed" ? "ok" : "warn"}>
                    {parseStatusLabel(doc.parse_status)}
                  </span>
                </div>
              ))}
            </div>
          </form>

          <form className="panel" onSubmit={createRegulation}>
            <div className="panel-title">
              <ShieldCheck size={18} />
              <h2>法规库</h2>
            </div>
            <input
              value={regulationDraft.title}
              onChange={(event) => setRegulationDraft({ ...regulationDraft, title: event.target.value })}
            />
            <input
              value={regulationDraft.official_url}
              onChange={(event) =>
                setRegulationDraft({ ...regulationDraft, official_url: event.target.value })
              }
            />
            <input
              value={regulationDraft.attachment_sha256}
              onChange={(event) =>
                setRegulationDraft({ ...regulationDraft, attachment_sha256: event.target.value })
              }
            />
            <button type="submit">
              <Plus size={16} />
              录入法规
            </button>
            <div className="table-list">
              {regulations.map((regulation) => (
                <div key={regulation.id} className="table-row regulation-row">
                  <span>{regulation.title}</span>
                  <span className={regulation.verification_status === "verified" ? "ok" : "warn"}>
                    {regulationStatusLabel(regulation.verification_status)}
                  </span>
                  <button type="button" onClick={() => verifyRegulation(regulation.id)}>
                    校验
                  </button>
                  <button type="button" onClick={() => summarizeRegulationImpact(regulation.id)}>
                    <Sparkles size={16} />
                    智能摘要
                  </button>
                  {regulationImpacts[regulation.id] && (
                    <p className="impact-draft">{regulationImpacts[regulation.id].summary}</p>
                  )}
                </div>
              ))}
            </div>
          </form>
        </section>

        <section className="band">
          <div className="panel">
            <div className="panel-title actions-title">
              <div>
                <h2>三类有源器械资料准备清单</h2>
                <p className="section-note">
                  按首次注册资料框架整理，并突出软件、联网、算法、输出能量和可靠性等高风险有源器械专项资料。
                </p>
              </div>
            </div>
            <div className="checklist-grid">
              {checklistRows.map((row) => (
                <div key={row.value} className={`checklist-row ${row.uploaded ? "ready" : row.expected ? "needed" : ""}`}>
                  <span>{row.section}</span>
                  <strong>{row.label}</strong>
                  <span>{row.status}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="band">
          <div className="panel">
            <div className="panel-title actions-title">
              <h2>产品主数据</h2>
              <div className="button-row">
                <button onClick={extractMasterData} disabled={!selectedProjectId}>
                  <Play size={16} />
                  抽取
                </button>
                <button onClick={aiExtractMasterData} disabled={!selectedProjectId || Boolean(busyTask)}>
                  {busyTask === "ai-extract" ? <LoaderCircle size={16} /> : <Sparkles size={16} />}
                  {busyTask === "ai-extract" ? "智能抽取中" : "智能抽取"}
                </button>
                <button onClick={saveMasterData} disabled={!selectedProjectId}>
                  保存
                </button>
              </div>
            </div>
            <div className="master-grid">
              {masterFields.map(([key, label]) => (
                <label key={key}>
                  {label}
                  <input
                    value={String(masterData[key] ?? "")}
                    onChange={(event) => updateMasterField(key, event.target.value)}
                  />
                </label>
              ))}
              {[
                ["is_networked", "联网"],
                ["outputs_energy", "输出能量"],
                ["has_disposable_accessory", "一次性附件"],
              ].map(([key, label]) => (
                <label key={key} className="toggle-line compact">
                  <input
                    type="checkbox"
                    checked={Boolean(masterData[key as keyof MasterData])}
                    onChange={(event) => updateMasterField(key as keyof MasterData, event.target.checked)}
                  />
                  {label}
                </label>
              ))}
            </div>
            {aiEvidenceSpans.length > 0 && (
              <div className="evidence-list">
                {aiEvidenceSpans.slice(0, 6).map((span) => (
                  <div key={span.id} className="evidence-card">
                    <strong>{masterFieldLabels[span.field_name] ?? span.field_name}</strong>
                    <span>{span.filename} {span.locator}</span>
                    <p>{displayText(span.quote)}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="band">
          <div className="panel">
            <div className="panel-title actions-title">
              <h2>风险清单</h2>
              <div className="button-row">
                <button onClick={runChecks} disabled={!selectedProjectId}>
                  <Play size={16} />
                  运行规则
                </button>
                <button onClick={analyzeRisksWithAI} disabled={!selectedProjectId || Boolean(busyTask)}>
                  {busyTask === "ai-risk" ? <LoaderCircle size={16} /> : <Sparkles size={16} />}
                  {busyTask === "ai-risk" ? "智能分析中" : "智能分析"}
                </button>
                <button onClick={generateReport} disabled={!selectedProjectId}>
                  <Download size={16} />
                  生成报告
                </button>
                <button onClick={polishReportWithAI} disabled={!latestReport}>
                  <Sparkles size={16} />
                  智能润色
                </button>
              </div>
            </div>
            {latestAiRun && (
              <p className="ai-run-note">
                最近智能处理：{taskLabels[latestAiRun.task_type] ?? "资料处理"} ·
                {latestAiRun.contains_sensitive_content ? " 已做脱敏标记" : " 仅使用脱敏摘录"}
              </p>
            )}
            <div className="findings">
              {findings.map((finding) => (
                <article key={finding.id} className={`finding ${finding.risk_level}`}>
                  <div className="finding-head">
                    <span className={`risk-badge ${finding.risk_level}`}>{riskLevelLabels[finding.risk_level]}</span>
                    <span className={`source-badge ${finding.source_type}`}>{sourceLabel(finding)}</span>
                    <span className={`review-badge ${finding.review_status}`}>
                      {reviewStatusLabels[finding.review_status]}
                    </span>
                  </div>
                  <div>
                    <h3>{displayText(finding.title)}</h3>
                  </div>
                  <p>{displayText(finding.description)}</p>
                  <div className="evidence-block">
                    <strong>资料依据</strong>
                    {evidenceLines(finding).map((line, index) => (
                      <p key={`${finding.id}-${index}`}>{displayText(line)}</p>
                    ))}
                  </div>
                  {finding.ai_rationale && (
                    <p className="ai-rationale">{displayText(finding.ai_rationale)}</p>
                  )}
                  <p className="action-text">建议处理：{displayText(finding.recommended_action)}</p>
                  {finding.source_type === "llm_candidate" && finding.review_status === "pending_review" && (
                    <div className="button-row review-actions">
                      <button type="button" onClick={() => reviewFinding(finding.id, "confirmed")}>
                        <Check size={16} />
                        确认
                      </button>
                      <button type="button" className="secondary-button" onClick={() => reviewFinding(finding.id, "rejected")}>
                        <X size={16} />
                        驳回
                      </button>
                    </div>
                  )}
                </article>
              ))}
            </div>
            {latestReport && selectedProjectId && (
              <a
                className="download-link"
                href={`${API_BASE}/projects/${selectedProjectId}/reports/${latestReport.id}/download`}
              >
                {latestReport.filename}
              </a>
            )}
          </div>
        </section>
      </section>
    </main>
  );
}
