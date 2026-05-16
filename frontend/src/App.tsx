import {
  AlertTriangle,
  BadgeCheck,
  BarChart3,
  ClipboardCheck,
  Check,
  CheckCircle2,
  Circle,
  Download,
  ExternalLink,
  FileCheck2,
  FileText,
  FileUp,
  FolderKanban,
  Globe2,
  LibraryBig,
  LoaderCircle,
  Play,
  Plus,
  RefreshCw,
  Route,
  Search,
  ShieldAlert,
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
  regulation_attachment_id: number | null;
  regulation_title: string;
  regulation_attachment_filename: string;
  regulation_attachment_sha256: string;
  regulation_evidence_locator: string;
  regulation_evidence_quote: string;
  risk_level: "red" | "yellow" | "green";
  title: string;
  description: string;
  evidence_document: string;
  evidence_locator: string;
  evidence_quote: string;
  possible_impact: string;
  recommended_action: string;
  owner: string;
  workload: string;
  category: string;
  confidence_status: string;
  source_type: "rule" | "llm_candidate" | "regulatory_rag_candidate" | "rule_llm_confirmed" | "manual";
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
  attachment_url: string;
  source_type: "preset" | "manual" | "web_import" | "file_import";
  source_files: Array<Record<string, string | boolean>>;
  source_content_sha256: string;
  source_note: string;
  coverage_classes: string[];
  device_scope: string;
  applicable_modules: string[];
  stored_path: string;
  text_preview: string;
  segment_count: number;
  verification_status: string;
  verified_by: string;
};

type RegulationAttachment = {
  id: number;
  regulation_id: number;
  filename: string;
  source_url: string;
  source_page_url: string;
  source_type: "official_attachment" | "uploaded_file" | "reference_attachment" | "web_page";
  verification_usable: boolean;
  sha256: string;
  content_type: string;
  byte_size: number;
  download_status: string;
  download_error: string;
  text_preview: string;
  segment_count: number;
};

type RegulationSearchResult = {
  regulation_id: number;
  regulation_title: string;
  attachment_id: number | null;
  attachment_filename: string;
  attachment_sha256: string;
  locator: string;
  snippet: string;
};

type RegulationAttachmentBulkDownloadResponse = {
  total: number;
  downloaded: number;
  skipped: number;
  failed: number;
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

type ConsistencyMatrixCell = {
  document_id: number;
  document_type: string;
  filename: string;
  value: string;
  quote: string;
};

type ConsistencyMatrixRow = {
  field: string;
  label: string;
  status: "missing" | "weak" | "conflict" | "consistent";
  values_by_document: ConsistencyMatrixCell[];
};

type DashboardAction = {
  title: string;
  owner: string;
  action: string;
  workload: string;
};

type Dashboard = {
  project_id: number;
  readiness_score: number;
  risk_counts: Record<"red" | "yellow" | "green", number>;
  category_counts: Record<string, number>;
  owner_counts: Record<string, number>;
  major_breakpoints: Finding[];
  next_actions: DashboardAction[];
  boss_summary: string;
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
  regulatory_rag_review: "法规RAG审查",
  summarize_regulation_impact: "法规影响摘要",
  polish_report: "报告摘要润色",
};

const findingAreaOrder = [
  "core",
  "testing",
  "software",
  "clinical",
  "labeling",
  "risk",
  "regulatory",
  "other",
] as const;

type FindingArea = (typeof findingAreaOrder)[number];

const findingAreaLabels: Record<FindingArea, string> = {
  core: "核心信息",
  testing: "检验与标准",
  software: "软件与算法",
  clinical: "临床评价",
  labeling: "说明书标签",
  risk: "风险控制",
  regulatory: "法规依据",
  other: "其他问题",
};

const findingFilterLabels = {
  all: "全部",
  red: "高风险",
  pending: "待确认",
  rule: "规则发现",
  ai: "智能候选",
  rag: "法规依据",
} as const;

type FindingFilter = keyof typeof findingFilterLabels;

const regulationModuleLabels: Record<string, string> = {
  general_submission: "申报资料",
  testing: "技术要求/检验",
  standards: "标准",
  software: "软件",
  network_security: "网络安全",
  clinical: "临床评价",
  ai_algorithm: "人工智能",
  reliability: "使用期限",
  risk_management: "风险管理",
  labeling: "说明书标签",
};

const regulationSourceLabels: Record<Regulation["source_type"], string> = {
  preset: "预置",
  manual: "手工录入",
  web_import: "网页导入",
  file_import: "文件导入",
};

const attachmentSourceLabels: Record<RegulationAttachment["source_type"], string> = {
  official_attachment: "官方附件",
  uploaded_file: "上传附件",
  reference_attachment: "参考附件",
  web_page: "网页正文",
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || response.statusText);
  }
  return response.json() as Promise<T>;
}

function compactText(value: string, maxLength: number) {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, Math.max(maxLength - 1, 0))}…`;
}

function findingArea(finding: Finding): FindingArea {
  const ruleId = finding.rule_id.toUpperCase();
  const text = [
    finding.rule_id,
    finding.title,
    finding.description,
    finding.possible_impact,
    finding.recommended_action,
    finding.evidence_document,
    finding.regulation_title,
  ].join(" ");

  if (
    ruleId.includes("NAME") ||
    ruleId.includes("MODEL") ||
    ruleId.includes("STRUCTURE") ||
    ruleId.includes("INTENDED-USE")
  ) {
    return "core";
  }
  if (
    ruleId.includes("TEST") ||
    ruleId.includes("STANDARD") ||
    ruleId.includes("REPRESENTATIVE")
  ) {
    return "testing";
  }
  if (
    ruleId.includes("CLINICAL") ||
    ruleId.includes("UNSUPPORTED-CLAIM") ||
    /临床|同品种|免于临床|单臂|30例/.test(text)
  ) {
    return "clinical";
  }
  if (
    ruleId.includes("DISPOSABLE") ||
    ruleId.includes("LABEL") ||
    /说明书|标签|一次性|重复使用|清洁消毒|包装/.test(text)
  ) {
    return "labeling";
  }
  if (
    ruleId.includes("RISK") ||
    ruleId.includes("CONTRAINDICATION") ||
    ruleId.includes("SERVICE-LIFE") ||
    ruleId.includes("RELIABILITY") ||
    ruleId.includes("ENERGY")
  ) {
    return "risk";
  }
  if (
    ruleId.includes("SOFTWARE") ||
    ruleId.includes("NETWORK") ||
    ruleId.includes("AI") ||
    ruleId.includes("ALGORITHM") ||
    /软件|网络安全|联网|算法|人工智能|智能算法|自动推荐|训练验证/.test(text)
  ) {
    return "software";
  }
  if (
    /检验|标准|代表型号|产品技术要求|性能指标|GB|YY/.test(text)
  ) {
    return "testing";
  }
  if (
    /风险|禁忌|警示|剩余风险|使用期限|可靠性|输出能量/.test(text)
  ) {
    return "risk";
  }
  if (
    ruleId.includes("NAME") ||
    ruleId.includes("MODEL") ||
    ruleId.includes("STRUCTURE") ||
    ruleId.includes("INTENDED-USE") ||
    /产品名称|型号规格|结构组成|适用范围|主数据|综述资料/.test(text)
  ) {
    return "core";
  }
  if (finding.source_type === "regulatory_rag_candidate" || finding.regulation_evidence_quote) {
    return "regulatory";
  }
  return "other";
}

function compareFindings(a: Finding, b: Finding) {
  const riskRank = { red: 0, yellow: 1, green: 2 };
  const reviewRank = { pending_review: 0, confirmed: 1, edited: 2, rejected: 3 };
  const sourceRank = {
    rule: 0,
    rule_llm_confirmed: 1,
    regulatory_rag_candidate: 2,
    llm_candidate: 3,
    manual: 4,
  };
  return (
    riskRank[a.risk_level] - riskRank[b.risk_level] ||
    reviewRank[a.review_status] - reviewRank[b.review_status] ||
    sourceRank[a.source_type] - sourceRank[b.source_type] ||
    a.id - b.id
  );
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
  const [regulationAttachments, setRegulationAttachments] = useState<Record<number, RegulationAttachment[]>>({});
  const [regulationImpacts, setRegulationImpacts] = useState<Record<number, RegulationImpactDraft>>({});
  const [regulationDraft, setRegulationDraft] = useState({
    title: "医疗器械注册申报资料要求和批准证明文件格式",
    reference_number: "国家药监局 2021年第121号",
    publication_date: "2021-09-30",
    official_url: "https://www.nmpa.gov.cn/xxgk/ggtg/ylqxggtg/ylqxqtggtg/20210930155134148.html",
    attachment_filename: "",
    attachment_sha256: "",
    applicable_modules: "general_submission,testing,network_security",
  });
  const [regulationWebDraft, setRegulationWebDraft] = useState({
    url: "",
    title: "",
    applicable_modules: "testing,standards",
    coverage_classes: "II,III",
  });
  const [regulationFileDraft, setRegulationFileDraft] = useState({
    title: "",
    official_url: "",
    reference_number: "",
    publication_date: "",
    applicable_modules: "general_submission",
    coverage_classes: "II,III",
  });
  const [regulationImportFile, setRegulationImportFile] = useState<File | null>(null);
  const [attachmentUrlDraft, setAttachmentUrlDraft] = useState({
    regulation_id: "",
    url: "",
    filename: "",
  });
  const [regulationSearchQuery, setRegulationSearchQuery] = useState("");
  const [regulationSearchResults, setRegulationSearchResults] = useState<RegulationSearchResult[]>([]);
  const [regulationListQuery, setRegulationListQuery] = useState("");
  const [regulationStatusFilter, setRegulationStatusFilter] = useState("all");
  const [visibleRegulationCount, setVisibleRegulationCount] = useState(20);
  const [findingFilter, setFindingFilter] = useState<FindingFilter>("all");
  const [latestReport, setLatestReport] = useState<Report | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [consistencyMatrix, setConsistencyMatrix] = useState<ConsistencyMatrixRow[]>([]);
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
  const requiredDocumentCount = useMemo(
    () => checklistRows.filter((row) => row.expected).length,
    [checklistRows]
  );
  const uploadedRequiredCount = useMemo(
    () => checklistRows.filter((row) => row.expected && row.uploaded).length,
    [checklistRows]
  );
  const missingRequiredCount = Math.max(requiredDocumentCount - uploadedRequiredCount, 0);
  const hasMasterData = useMemo(
    () => masterFields.some(([key]) => Boolean(masterData[key])),
    [masterData]
  );
  const ruleFindingCount = useMemo(
    () => findings.filter((finding) => ["rule", "rule_llm_confirmed"].includes(finding.source_type)).length,
    [findings]
  );
  const aiCandidateCount = useMemo(
    () =>
      findings.filter((finding) =>
        ["llm_candidate", "regulatory_rag_candidate"].includes(finding.source_type)
      ).length,
    [findings]
  );
  const pendingAiCandidateCount = useMemo(
    () =>
      findings.filter(
        (finding) =>
          ["llm_candidate", "regulatory_rag_candidate"].includes(finding.source_type) &&
          finding.review_status === "pending_review"
      ).length,
    [findings]
  );
  const highRiskCount = useMemo(
    () => findings.filter((finding) => finding.risk_level === "red").length,
    [findings]
  );
  const matrixAttentionRows = useMemo(
    () => consistencyMatrix.filter((row) => ["conflict", "weak"].includes(row.status)),
    [consistencyMatrix]
  );
  const readinessScore = dashboard?.readiness_score ?? Math.max(0, 100 - highRiskCount * 15);
  const ownerEntries = useMemo(
    () => Object.entries(dashboard?.owner_counts ?? {}).sort((a, b) => b[1] - a[1]),
    [dashboard]
  );
  const findingFilterCounts = useMemo(
    () => ({
      all: findings.length,
      red: findings.filter((finding) => finding.risk_level === "red").length,
      pending: findings.filter((finding) => finding.review_status === "pending_review").length,
      rule: findings.filter((finding) => ["rule", "rule_llm_confirmed"].includes(finding.source_type)).length,
      ai: findings.filter((finding) => finding.source_type === "llm_candidate").length,
      rag: findings.filter((finding) => finding.source_type === "regulatory_rag_candidate").length,
    }),
    [findings]
  );
  const visibleFindings = useMemo(() => {
    const filtered = findings.filter((finding) => {
      if (findingFilter === "red") return finding.risk_level === "red";
      if (findingFilter === "pending") return finding.review_status === "pending_review";
      if (findingFilter === "rule") return ["rule", "rule_llm_confirmed"].includes(finding.source_type);
      if (findingFilter === "ai") return finding.source_type === "llm_candidate";
      if (findingFilter === "rag") return finding.source_type === "regulatory_rag_candidate";
      return true;
    });
    return [...filtered].sort(compareFindings);
  }, [findingFilter, findings]);
  const findingGroups = useMemo(
    () =>
      findingAreaOrder
        .map((area) => ({
          area,
          findings: visibleFindings.filter((finding) => findingArea(finding) === area),
        }))
        .filter((group) => group.findings.length > 0),
    [visibleFindings]
  );
  const verifiedRegulationCount = useMemo(
    () => regulations.filter((regulation) => regulation.verification_status === "verified").length,
    [regulations]
  );
  const filteredRegulations = useMemo(() => {
    const query = regulationListQuery.trim().toLowerCase();
    return regulations.filter((regulation) => {
      const statusMatched =
        regulationStatusFilter === "all" ||
        regulation.verification_status === regulationStatusFilter ||
        (regulationStatusFilter === "pending" && regulation.verification_status !== "verified");
      if (!statusMatched) return false;
      if (!query) return true;
      return [
        regulation.title,
        regulation.reference_number,
        regulation.device_scope,
        regulation.source_note,
        ...regulation.applicable_modules.map(moduleLabel),
        ...regulation.coverage_classes,
      ]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
  }, [regulationListQuery, regulationStatusFilter, regulations]);
  const visibleRegulations = useMemo(
    () => filteredRegulations.slice(0, visibleRegulationCount),
    [filteredRegulations, visibleRegulationCount]
  );
  const workflowSteps = useMemo(
    () => [
      {
        label: "建项",
        detail: selectedProject ? "项目已就绪" : "创建或选择项目",
        state: selectedProject ? "done" : "active",
      },
      {
        label: "资料",
        detail:
          documents.length > 0
            ? `${uploadedRequiredCount}/${requiredDocumentCount} 项关键资料`
            : "加载样例或上传资料",
        state:
          documents.length === 0
            ? "waiting"
            : missingRequiredCount === 0
              ? "done"
              : "active",
      },
      {
        label: "主数据",
        detail: hasMasterData ? "字段已形成候选" : "待抽取产品主数据",
        state: hasMasterData ? "done" : documents.length ? "active" : "waiting",
      },
      {
        label: "风险",
        detail: findings.length ? `${findings.length} 条发现` : "待运行规则和智能审查",
        state: findings.length ? "done" : hasMasterData ? "active" : "waiting",
      },
      {
        label: "复核",
        detail: pendingAiCandidateCount ? `${pendingAiCandidateCount} 条候选待确认` : "候选已清理或暂无候选",
        state:
          aiCandidateCount === 0
            ? "waiting"
            : pendingAiCandidateCount === 0
              ? "done"
              : "active",
      },
      {
        label: "报告",
        detail: latestReport ? "Word 报告已生成" : "待生成预审报告",
        state: latestReport ? "done" : findings.length ? "active" : "waiting",
      },
    ],
    [
      aiCandidateCount,
      documents.length,
      findings.length,
      hasMasterData,
      latestReport,
      missingRequiredCount,
      pendingAiCandidateCount,
      requiredDocumentCount,
      selectedProject,
      uploadedRequiredCount,
    ]
  );

  useEffect(() => {
    refreshAll();
  }, []);

  useEffect(() => {
    if (selectedProjectId) {
      refreshProject(selectedProjectId);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    setVisibleRegulationCount(20);
  }, [regulationListQuery, regulationStatusFilter]);

  async function refreshAll() {
    const [projectList] = await Promise.all([
      request<Project[]>("/projects"),
    ]);
    setProjects(projectList);
    await refreshRegulations();
    if (!selectedProjectId && projectList.length) {
      setSelectedProjectId(projectList[0].id);
    }
  }

  async function refreshRegulations() {
    const regulationList = await request<Regulation[]>("/regulations");
    setRegulations(regulationList);
    const entries = await Promise.all(
      regulationList.map(async (regulation) => {
        try {
          const attachments = await request<RegulationAttachment[]>(
            `/regulations/${regulation.id}/attachments`
          );
          return [regulation.id, attachments] as const;
        } catch {
          return [regulation.id, []] as const;
        }
      })
    );
    setRegulationAttachments(Object.fromEntries(entries));
  }

  async function refreshProject(projectId: number) {
    const [documentList, findingList, dashboardData, matrixRows] = await Promise.all([
      request<DocumentRecord[]>(`/projects/${projectId}/documents`),
      request<Finding[]>(`/projects/${projectId}/findings`),
      request<Dashboard>(`/projects/${projectId}/dashboard`),
      request<ConsistencyMatrixRow[]>(`/projects/${projectId}/consistency-matrix`),
    ]);
    setDocuments(documentList);
    setFindings(findingList);
    setDashboard(dashboardData);
    setConsistencyMatrix(matrixRows);
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
    await refreshProject(selectedProjectId);
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

  async function runRegulatoryRagReview() {
    if (!selectedProjectId) return;
    setBusyTask("regulatory-rag");
    setStatus("法规RAG审查中，正在检索已校验法规正文");
    try {
      const result = await request<AIRiskResponse>(
        `/projects/${selectedProjectId}/regulatory-rag-review`,
        { method: "POST" }
      );
      setLatestAiRun(result.llm_run);
      await refreshProject(selectedProjectId);
      setStatus(
        result.findings.length > 0
          ? `法规RAG审查已生成 ${result.findings.length} 条候选问题`
          : "法规RAG审查未生成候选问题：暂无匹配的已校验法规正文"
      );
    } catch (error) {
      setStatus(`法规RAG审查失败：${friendlyError(error)}`);
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
        coverage_classes: ["II", "III"],
        device_scope: "II类和III类有源医疗器械注册",
      }),
    });
    await refreshRegulations();
    setStatus("法规已录入");
  }

  async function importRegulationFromWeb(event: FormEvent) {
    event.preventDefault();
    setStatus("导入法规网页中");
    try {
      await request<Regulation>("/regulations/import/web", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...regulationWebDraft,
          applicable_modules: splitInputList(regulationWebDraft.applicable_modules),
          coverage_classes: splitInputList(regulationWebDraft.coverage_classes),
        }),
      });
      await refreshRegulations();
      setStatus("法规网页已导入，等待附件 SHA 或人工确认");
    } catch (error) {
      setStatus(`网页导入失败：${friendlyError(error)}`);
    }
  }

  async function importRegulationFromFile(event: FormEvent) {
    event.preventDefault();
    if (!regulationImportFile) return;
    setStatus("导入法规文件中");
    try {
      const body = new FormData();
      Object.entries(regulationFileDraft).forEach(([key, value]) => body.append(key, value));
      body.append("file", regulationImportFile);
      await request<Regulation>("/regulations/import/file", { method: "POST", body });
      setRegulationImportFile(null);
      await refreshRegulations();
      setStatus("法规文件已导入并计算 SHA");
    } catch (error) {
      setStatus(`文件导入失败：${friendlyError(error)}`);
    }
  }

  async function importAttachmentFromUrl(event: FormEvent) {
    event.preventDefault();
    const regulationId = Number(attachmentUrlDraft.regulation_id);
    if (!regulationId || !attachmentUrlDraft.url) return;
    setStatus("下载法规附件中");
    try {
      await request<RegulationAttachment>(`/regulations/${regulationId}/attachments/import-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: attachmentUrlDraft.url,
          filename: attachmentUrlDraft.filename,
          source_type: "official_attachment",
          verification_usable: true,
        }),
      });
      setAttachmentUrlDraft({ ...attachmentUrlDraft, url: "", filename: "" });
      await refreshRegulations();
      setStatus("法规附件已下载、计算 SHA 并抽取正文");
    } catch (error) {
      setStatus(`附件导入失败：${friendlyError(error)}`);
    }
  }

  async function downloadKnownAttachment(regulationId: number, attachmentId: number) {
    setStatus("下载并抽取官方附件中");
    try {
      await request<RegulationAttachment>(
        `/regulations/${regulationId}/attachments/${attachmentId}/download`,
        { method: "POST" }
      );
      await refreshRegulations();
      setStatus("官方附件已下载、计算 SHA 并抽取正文");
    } catch (error) {
      setStatus(`附件下载失败：${friendlyError(error)}`);
    }
  }

  async function downloadPresetAttachments() {
    setStatus("批量下载预置法规来源中");
    try {
      const result = await request<RegulationAttachmentBulkDownloadResponse>(
        "/regulations/preset-attachments/download",
        { method: "POST" }
      );
      await refreshRegulations();
      setStatus(
        `预置来源下载完成：下载 ${result.downloaded} 个，跳过 ${result.skipped} 个，失败 ${result.failed} 个`
      );
    } catch (error) {
      setStatus(`预置来源批量下载失败：${friendlyError(error)}`);
    }
  }

  async function searchRegulationText(event: FormEvent) {
    event.preventDefault();
    if (!regulationSearchQuery.trim()) return;
    setStatus("检索法规正文中");
    try {
      const params = new URLSearchParams({ query: regulationSearchQuery.trim() });
      const results = await request<RegulationSearchResult[]>(`/regulations/search?${params}`);
      setRegulationSearchResults(results);
      setStatus(`法规正文检索完成：${results.length} 条结果`);
    } catch (error) {
      setStatus(`法规正文检索失败：${friendlyError(error)}`);
    }
  }

  async function verifyRegulation(regulationId: number) {
    setStatus("校验法规中");
    try {
      await request<Regulation>(`/regulations/${regulationId}/verify`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ verification_status: "verified", verified_by: "内部校验" }),
      });
      await refreshRegulations();
      setStatus("法规已校验");
    } catch (error) {
      setStatus(`法规校验失败：${friendlyError(error)}`);
    }
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

  function splitInputList(value: string) {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function moduleLabel(module: string) {
    return regulationModuleLabels[module] ?? module;
  }

  function sourceEvidence(regulation: Regulation) {
    const attachments = attachmentsFor(regulation);
    if (attachments.length) {
      const readySources = attachments.filter(isAttachmentEvidenceReady);
      const readyWebPages = readySources.filter((item) => item.source_type === "web_page");
      const readyFileAttachments = readySources.filter((item) => item.source_type !== "web_page");
      const pendingOfficial = attachments.filter(
        (item) =>
          item.source_type === "official_attachment" &&
          item.verification_usable &&
          !isAttachmentEvidenceReady(item)
      );
      const failedWebPages = attachments.filter(
        (item) => item.source_type === "web_page" && item.download_status === "failed"
      );
      const segmentCount = attachments.reduce((sum, item) => sum + item.segment_count, 0);
      if (readyFileAttachments.length && readyWebPages.length) {
        return `${readyFileAttachments.length} 个已抽取可校验附件 + ${readyWebPages.length} 个官方网页正文 · ${segmentCount} 段正文`;
      }
      if (readyFileAttachments.length) {
        return `${readyFileAttachments.length} 个已抽取可校验附件 · ${segmentCount} 段正文`;
      }
      if (readyWebPages.length) {
        return `${readyWebPages.length} 个官方网页正文已抽取 · ${segmentCount} 段正文`;
      }
      if (pendingOfficial.length) {
        return `${pendingOfficial.length} 个官方附件待下载/抽取 · ${segmentCount} 段正文`;
      }
      if (failedWebPages.length) {
        return `${failedWebPages.length} 个官方网页正文抓取失败`;
      }
      return `${attachments.length} 个参考附件 · ${segmentCount} 段正文`;
    }
    if (regulation.source_files.length) {
      const usableFiles = regulation.source_files.filter((item) => item.verification_usable !== false);
      if (usableFiles.length) return `${usableFiles.length} 个官方文件待下载/抽取`;
      return `${regulation.source_files.length} 个参考文件 SHA`;
    }
    if (regulation.attachment_sha256) return shortSha(regulation.attachment_sha256);
    if (regulation.source_content_sha256) return `网页 SHA ${shortSha(regulation.source_content_sha256)}`;
    return "待补附件 SHA";
  }

  function canVerifyRegulation(regulation: Regulation) {
    const usableAttachment = attachmentsFor(regulation).some(isAttachmentEvidenceReady);
    return Boolean(regulation.official_url && usableAttachment);
  }

  function attachmentsFor(regulation: Regulation) {
    return regulationAttachments[regulation.id] ?? [];
  }

  function isAttachmentEvidenceReady(attachment: RegulationAttachment) {
    return Boolean(
      attachment.verification_usable &&
        attachment.sha256 &&
        attachment.download_status === "extracted" &&
        attachment.segment_count > 0
    );
  }

  function attachmentStatusLabel(attachment: RegulationAttachment) {
    if (!attachment.verification_usable) return "参考";
    if (isAttachmentEvidenceReady(attachment)) return "可校验";
    if (attachment.download_status === "failed") return "抽取失败";
    if (attachment.download_status === "metadata_only") return "待下载";
    return "待抽取";
  }

  function shortSha(value: string) {
    return value ? `${value.slice(0, 10)}...` : "";
  }

  function sourceLabel(finding: Finding) {
    if (finding.source_type === "llm_candidate") {
      return finding.review_status === "pending_review" ? "智能候选" : "智能辅助";
    }
    if (finding.source_type === "regulatory_rag_candidate") {
      return finding.review_status === "pending_review" ? "法规RAG候选" : "法规RAG辅助";
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

  function regulationEvidenceLines(finding: Finding) {
    const header = [
      finding.regulation_title,
      finding.regulation_attachment_filename,
      finding.regulation_evidence_locator,
      finding.regulation_attachment_sha256 ? `SHA ${shortSha(finding.regulation_attachment_sha256)}` : "",
    ].filter(Boolean).join(" · ");
    const quoteLines = finding.regulation_evidence_quote
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    return header ? [header, ...quoteLines] : quoteLines;
  }

  function findingDetailLine(finding: Finding) {
    return compactText(finding.description || finding.possible_impact || "需人工复核该项资料与证据。", 92);
  }

  function firstEvidenceLine(finding: Finding) {
    return compactText(evidenceLines(finding)[0] ?? "暂无可展示证据，请人工补充资料后复核。", 104);
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <ClipboardCheck size={22} />
          </div>
          <div>
            <span>注册资料预审</span>
            <small>Evidence-first workbench</small>
          </div>
        </div>
        <div className="sidebar-section-title">项目建档</div>
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
        <div className="sidebar-section-title">项目切换</div>
        <div className="project-list">
          {projects.length ? (
            projects.map((project) => (
              <button
                key={project.id}
                className={project.id === selectedProjectId ? "selected" : ""}
                onClick={() => setSelectedProjectId(project.id)}
              >
                <FolderKanban size={15} />
                {project.name}
              </button>
            ))
          ) : (
            <p className="sidebar-empty">暂无项目，请先新建项目。</p>
          )}
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="workspace-kicker">三类有源医疗器械注册资料智能预审</p>
            <h1>{selectedProject?.name ?? "未选择项目"}</h1>
            <p>{selectedProject?.registration_scenario ?? status}</p>
            <div className={`status-pill ${busyTask ? "busy" : ""}`}>
              {busyTask && <LoaderCircle size={14} />}
              {status}
            </div>
          </div>
          <button className="secondary-button" onClick={refreshAll}>
            <RefreshCw size={16} />
            刷新
          </button>
        </header>

        <section className="band command-center" aria-label="项目审查概览">
          <div className="metric-grid">
            <article className={`metric-card ${missingRequiredCount ? "warning" : "success"}`}>
              <div className="metric-icon">
                <FileCheck2 size={18} />
              </div>
              <div>
                <span>关键资料</span>
                <strong>{uploadedRequiredCount}/{requiredDocumentCount || documentTypeOptions.length}</strong>
                <p>{missingRequiredCount ? `仍缺 ${missingRequiredCount} 项` : "必需资料已覆盖"}</p>
              </div>
            </article>
            <article className={highRiskCount ? "metric-card danger" : "metric-card"}>
              <div className="metric-icon">
                <ShieldAlert size={18} />
              </div>
              <div>
                <span>风险发现</span>
                <strong>{findings.length}</strong>
                <p>{highRiskCount ? `${highRiskCount} 条高风险` : `${ruleFindingCount} 条规则发现`}</p>
              </div>
            </article>
            <article className={pendingAiCandidateCount ? "metric-card info" : "metric-card"}>
              <div className="metric-icon">
                <Sparkles size={18} />
              </div>
              <div>
                <span>智能候选</span>
                <strong>{aiCandidateCount}</strong>
                <p>{pendingAiCandidateCount ? `${pendingAiCandidateCount} 条待人工确认` : "无待确认候选"}</p>
              </div>
            </article>
            <article className="metric-card success">
              <div className="metric-icon">
                <LibraryBig size={18} />
              </div>
              <div>
                <span>法规证据</span>
                <strong>{verifiedRegulationCount}/{regulations.length}</strong>
                <p>已校验法规来源</p>
              </div>
            </article>
            <article className={latestReport ? "metric-card success" : "metric-card"}>
              <div className="metric-icon">
                <BadgeCheck size={18} />
              </div>
              <div>
                <span>报告状态</span>
                <strong>{latestReport ? "已生成" : "待生成"}</strong>
                <p>{latestReport?.filename ?? "完成复核后生成 Word"}</p>
              </div>
            </article>
          </div>
          <div className="workflow-strip">
            <div className="workflow-title">
              <Route size={18} />
              <span>审查路径</span>
            </div>
            <div className="workflow-steps">
              {workflowSteps.map((step, index) => (
                <div key={step.label} className={`workflow-step ${step.state}`}>
                  <div className="workflow-marker">
                    {step.state === "done" ? <CheckCircle2 size={16} /> : <Circle size={16} />}
                  </div>
                  <div>
                    <strong>{index + 1}. {step.label}</strong>
                    <span>{step.detail}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {selectedProject && (
          <section className="band boss-dashboard" aria-label="老板版注册风险驾驶舱">
            <div className="dashboard-hero">
              <div>
                <p className="workspace-kicker">注册风险驾驶舱</p>
                <h2>{dashboard?.boss_summary ?? "运行规则后生成申报准备度和重大断点摘要"}</h2>
              </div>
              <div className={`readiness-dial ${readinessScore < 70 ? "danger" : readinessScore < 90 ? "warning" : "success"}`}>
                <span>申报准备度</span>
                <strong>{readinessScore}</strong>
              </div>
            </div>
            <div className="dashboard-grid">
              <div className="dashboard-block">
                <span>重大申报断点</span>
                <strong>{dashboard?.risk_counts.red ?? highRiskCount}</strong>
                <p>红色风险优先进入整改闭环</p>
              </div>
              <div className="dashboard-block">
                <span>主数据一致性</span>
                <strong>{matrixAttentionRows.length}</strong>
                <p>{matrixAttentionRows.length ? "存在冲突或覆盖较弱字段" : "暂无明显冲突"}</p>
              </div>
              <div className="dashboard-block">
                <span>责任人分布</span>
                <strong>{ownerEntries.length}</strong>
                <p>{ownerEntries[0] ? `${ownerEntries[0][0]} ${ownerEntries[0][1]} 项` : "待运行规则"}</p>
              </div>
            </div>
            <div className="dashboard-columns">
              <div>
                <h3>下一步动作</h3>
                <div className="action-list">
                  {dashboard?.next_actions.length ? (
                    dashboard.next_actions.map((action, index) => (
                      <div key={`${action.title}-${index}`} className="action-row">
                        <span>{action.owner}</span>
                        <strong>{displayText(action.title)}</strong>
                        <p>{displayText(action.action)}</p>
                        <small>{action.workload}</small>
                      </div>
                    ))
                  ) : (
                    <p className="section-note">运行规则后显示需要跨部门处理的动作。</p>
                  )}
                </div>
              </div>
              <div>
                <h3>一致性矩阵关注项</h3>
                <div className="matrix-list">
                  {matrixAttentionRows.length ? (
                    matrixAttentionRows.slice(0, 5).map((row) => (
                      <div key={row.field} className={`matrix-row ${row.status}`}>
                        <span>{row.status === "conflict" ? "冲突" : "覆盖弱"}</span>
                        <strong>{row.label}</strong>
                        <p>
                          {row.values_by_document
                            .filter((item) => item.value)
                            .slice(0, 3)
                            .map((item) => `${item.filename}：${item.value}`)
                            .join("；") || "未识别到字段证据"}
                        </p>
                      </div>
                    ))
                  ) : (
                    <p className="section-note">资料之间的产品名称、型号、软件版本等字段暂无重点提示。</p>
                  )}
                </div>
              </div>
            </div>
          </section>
        )}

        <section className="band workbench-grid">
          <div className="main-flow">
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
              {documents.length ? (
                documents.map((doc) => (
                  <div key={doc.id} className="table-row">
                    <span>{documentLabel(doc.document_type)}</span>
                    <span>{doc.filename}</span>
                    <span className={doc.parse_status === "parsed" ? "ok" : "warn"}>
                      {parseStatusLabel(doc.parse_status)}
                    </span>
                  </div>
                ))
              ) : (
                <div className="empty-row">
                  <FileText size={16} />
                  <span>尚未上传资料，可加载黄金样例快速进入演示流程。</span>
                </div>
              )}
            </div>
            </form>
          </div>

          <aside className="regulation-dock" aria-label="法规库">
          <div className="panel regulation-panel">
            <div className="panel-title actions-title">
              <div className="panel-title">
                <ShieldCheck size={18} />
                <div>
                  <h2>法规库</h2>
                  <p className="section-note">预置覆盖 II/III 类有源器械注册；导入内容默认待确认，不自动成为规则依据。</p>
                </div>
              </div>
              <button type="button" onClick={downloadPresetAttachments}>
                <Download size={16} />
                下载预置来源
              </button>
            </div>
            <form className="regulation-import-grid" onSubmit={importRegulationFromWeb}>
              <label>
                网页 URL
                <input
                  value={regulationWebDraft.url}
                  onChange={(event) => setRegulationWebDraft({ ...regulationWebDraft, url: event.target.value })}
                  placeholder="https://..."
                />
              </label>
              <label>
                覆盖模块
                <input
                  value={regulationWebDraft.applicable_modules}
                  onChange={(event) =>
                    setRegulationWebDraft({ ...regulationWebDraft, applicable_modules: event.target.value })
                  }
                />
              </label>
              <button type="submit" disabled={!regulationWebDraft.url}>
                <Globe2 size={16} />
                导入网页
              </button>
            </form>
            <form className="regulation-import-grid" onSubmit={importRegulationFromFile}>
              <label>
                法规标题
                <input
                  value={regulationFileDraft.title}
                  onChange={(event) =>
                    setRegulationFileDraft({ ...regulationFileDraft, title: event.target.value })
                  }
                  placeholder="可留空，默认使用文件名"
                />
              </label>
              <label>
                官方链接
                <input
                  value={regulationFileDraft.official_url}
                  onChange={(event) =>
                    setRegulationFileDraft({ ...regulationFileDraft, official_url: event.target.value })
                  }
                />
              </label>
              <input
                type="file"
                accept=".doc,.docx,.pdf,.txt,.md"
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
                  setRegulationImportFile(event.target.files?.[0] ?? null)
                }
              />
              <button type="submit" disabled={!regulationImportFile}>
                <FileUp size={16} />
                导入文件
              </button>
            </form>
            <form className="regulation-import-grid attachment-url-form" onSubmit={importAttachmentFromUrl}>
              <label>
                归属法规
                <select
                  value={attachmentUrlDraft.regulation_id}
                  onChange={(event) =>
                    setAttachmentUrlDraft({ ...attachmentUrlDraft, regulation_id: event.target.value })
                  }
                >
                  <option value="">选择法规</option>
                  {regulations.map((regulation) => (
                    <option key={regulation.id} value={regulation.id}>
                      {regulation.title}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                官方附件 URL
                <input
                  value={attachmentUrlDraft.url}
                  onChange={(event) =>
                    setAttachmentUrlDraft({ ...attachmentUrlDraft, url: event.target.value })
                  }
                  placeholder="https://...doc、...docx 或 ...pdf"
                />
              </label>
              <input
                value={attachmentUrlDraft.filename}
                onChange={(event) =>
                  setAttachmentUrlDraft({ ...attachmentUrlDraft, filename: event.target.value })
                }
                placeholder="文件名可留空"
              />
              <button
                type="submit"
                disabled={!attachmentUrlDraft.regulation_id || !attachmentUrlDraft.url}
              >
                <Download size={16} />
                下载附件
              </button>
            </form>
            <form className="regulation-manual-form" onSubmit={createRegulation}>
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
                placeholder="附件 SHA，可先留空"
              />
              <button type="submit">
                <Plus size={16} />
                手工录入
              </button>
            </form>
            <form className="regulation-search-form" onSubmit={searchRegulationText}>
              <input
                value={regulationSearchQuery}
                onChange={(event) => setRegulationSearchQuery(event.target.value)}
                placeholder="检索已抽取的法规附件正文"
              />
              <button type="submit" disabled={!regulationSearchQuery.trim()}>
                <Search size={16} />
                检索正文
              </button>
            </form>
            {regulationSearchResults.length > 0 && (
              <div className="regulation-search-results">
                {regulationSearchResults.map((result, index) => (
                  <div key={`${result.regulation_id}-${result.attachment_id}-${result.locator}-${index}`}>
                    <strong>{result.regulation_title}</strong>
                    <span>
                      {result.attachment_filename || "网页正文"} · {result.locator}
                      {result.attachment_sha256 ? ` · ${shortSha(result.attachment_sha256)}` : ""}
                    </span>
                    <p>{result.snippet}</p>
                  </div>
                ))}
              </div>
            )}
            <div className="regulation-filter-bar">
              <label>
                快速筛选
                <input
                  value={regulationListQuery}
                  onChange={(event) => setRegulationListQuery(event.target.value)}
                  placeholder="标题、文号、模块"
                />
              </label>
              <label>
                校验状态
                <select
                  value={regulationStatusFilter}
                  onChange={(event) => setRegulationStatusFilter(event.target.value)}
                >
                  <option value="all">全部法规</option>
                  <option value="verified">已校验</option>
                  <option value="pending">待校验</option>
                </select>
              </label>
              <span>显示 {visibleRegulations.length}/{filteredRegulations.length} 条</span>
            </div>
            <div className="regulation-list">
              {visibleRegulations.length ? visibleRegulations.map((regulation) => (
                <div key={regulation.id} className="regulation-card">
                  <div className="regulation-card-main">
                    <div>
                      <div className="regulation-title-line">
                        <strong>{regulation.title}</strong>
                        <span className={`source-badge ${regulation.source_type}`}>
                          {regulationSourceLabels[regulation.source_type] ?? regulation.source_type}
                        </span>
                      </div>
                      <p className="regulation-meta">
                        {[regulation.reference_number, regulation.publication_date, regulation.device_scope]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    </div>
                    <span className={regulation.verification_status === "verified" ? "ok" : "warn"}>
                      {regulationStatusLabel(regulation.verification_status)}
                    </span>
                  </div>
                  <div className="regulation-chip-row">
                    {regulation.coverage_classes.map((item) => (
                      <span key={item} className="mini-chip">
                        {item}类
                      </span>
                    ))}
                    {regulation.applicable_modules.map((item) => (
                      <span key={item} className="mini-chip muted">
                        {moduleLabel(item)}
                      </span>
                    ))}
                  </div>
                  <div className="regulation-evidence-row">
                    <span>{sourceEvidence(regulation)}</span>
                    {regulation.official_url && (
                      <a href={regulation.official_url} target="_blank" rel="noreferrer">
                        <ExternalLink size={14} />
                        官方链接
                      </a>
                    )}
                  </div>
                  <div className="button-row regulation-actions">
                    <button
                      type="button"
                      disabled={!canVerifyRegulation(regulation)}
                      title={canVerifyRegulation(regulation) ? "确认校验" : "需补齐官方链接，并下载抽取至少一个可校验来源"}
                      onClick={() => verifyRegulation(regulation.id)}
                    >
                      <Check size={16} />
                      确认校验
                    </button>
                    <button type="button" onClick={() => summarizeRegulationImpact(regulation.id)}>
                      <Sparkles size={16} />
                      智能摘要
                    </button>
                  </div>
                  <details className="regulation-details">
                    <summary>查看附件与正文</summary>
                    {regulation.source_note && <p className="regulation-note">{regulation.source_note}</p>}
                    {attachmentsFor(regulation).length > 0 && (
                      <div className="attachment-list">
                        {attachmentsFor(regulation).slice(0, 3).map((attachment) => (
                          <div key={attachment.id} className="attachment-row">
                            <span>{attachmentSourceLabels[attachment.source_type] ?? attachment.source_type}</span>
                            <strong>{attachment.filename}</strong>
                            <span>
                              {attachmentStatusLabel(attachment)} ·
                              {attachment.segment_count} 段 · {shortSha(attachment.sha256)}
                            </span>
                            {attachment.source_url &&
                              attachment.verification_usable &&
                              !isAttachmentEvidenceReady(attachment) && (
                                <button
                                  type="button"
                                  className="inline-action"
                                  onClick={() => downloadKnownAttachment(regulation.id, attachment.id)}
                                >
                                  <Download size={14} />
                                  下载抽取
                                </button>
                              )}
                            {attachment.download_error && (
                              <span className="attachment-error">{attachment.download_error}</span>
                            )}
                          </div>
                        ))}
                        {attachmentsFor(regulation).length > 3 && (
                          <span className="regulation-note">
                            还有 {attachmentsFor(regulation).length - 3} 个附件未展开
                          </span>
                        )}
                      </div>
                    )}
                    {regulation.text_preview && <p className="impact-draft">{regulation.text_preview}</p>}
                    {regulationImpacts[regulation.id] && (
                      <p className="impact-draft">{regulationImpacts[regulation.id].summary}</p>
                    )}
                  </details>
                </div>
              )) : (
                <div className="empty-state">
                  <Search size={18} />
                  <div>
                    <strong>没有匹配的法规</strong>
                    <p>调整标题、文号、模块或校验状态筛选后再试。</p>
                  </div>
                </div>
              )}
            </div>
            {filteredRegulations.length > visibleRegulationCount && (
              <button
                type="button"
                className="secondary-button load-more-button"
                onClick={() => setVisibleRegulationCount((count) => count + 20)}
              >
                加载更多法规
              </button>
            )}
          </div>
          </aside>

          <div className="main-flow">
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
                <button onClick={runRegulatoryRagReview} disabled={!selectedProjectId || Boolean(busyTask)}>
                  {busyTask === "regulatory-rag" ? <LoaderCircle size={16} /> : <ShieldCheck size={16} />}
                  {busyTask === "regulatory-rag" ? "RAG审查中" : "法规RAG审查"}
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
            <div className="risk-overview">
              <span>
                <BarChart3 size={15} />
                规则发现 {ruleFindingCount}
              </span>
              <span>
                <Sparkles size={15} />
                智能候选 {aiCandidateCount}
              </span>
              <span>
                <AlertTriangle size={15} />
                高风险 {highRiskCount}
              </span>
            </div>
            <div className="finding-filter-bar" aria-label="风险清单筛选">
              {(Object.keys(findingFilterLabels) as FindingFilter[]).map((filter) => (
                <button
                  key={filter}
                  type="button"
                  className={findingFilter === filter ? "finding-filter-button active" : "finding-filter-button"}
                  onClick={() => setFindingFilter(filter)}
                >
                  {findingFilterLabels[filter]}
                  <span>{findingFilterCounts[filter]}</span>
                </button>
              ))}
            </div>
            <div className="findings">
              {findingGroups.length ? (
                findingGroups.map((group) => (
                  <section key={group.area} className="finding-group">
                    <div className="finding-group-head">
                      <h3>{findingAreaLabels[group.area]}</h3>
                      <span>{group.findings.length} 条</span>
                    </div>
                    {group.findings.map((finding) => (
                      <article key={finding.id} className={`finding ${finding.risk_level}`}>
                        <div className="finding-head">
                          <span className={`risk-badge ${finding.risk_level}`}>
                            {riskLevelLabels[finding.risk_level]}
                          </span>
                          <span className={`area-badge area-${findingArea(finding)}`}>
                            {findingAreaLabels[findingArea(finding)]}
                          </span>
                          <span className={`source-badge ${finding.source_type}`}>{sourceLabel(finding)}</span>
                          <span className={`review-badge ${finding.review_status}`}>
                            {reviewStatusLabels[finding.review_status]}
                          </span>
                        </div>
                        <div className="finding-title-row">
                          <h3>{displayText(finding.title)}</h3>
                          <span>{finding.rule_id}</span>
                        </div>
                        <p className="finding-summary">{displayText(findingDetailLine(finding))}</p>
                        <p className="finding-evidence-preview">依据：{displayText(firstEvidenceLine(finding))}</p>
                        {finding.recommended_action && (
                          <p className="action-text">建议：{displayText(compactText(finding.recommended_action, 72))}</p>
                        )}
                        {(finding.owner || finding.workload || finding.category) && (
                          <div className="finding-owner-line">
                            {finding.category && <span>{finding.category}</span>}
                            {finding.owner && <span>{finding.owner}</span>}
                            {finding.workload && <span>{finding.workload}</span>}
                          </div>
                        )}
                        <details className="finding-details">
                          <summary>证据与处理建议</summary>
                          <div className="evidence-block">
                            <strong>资料依据</strong>
                            {evidenceLines(finding).map((line, index) => (
                              <p key={`${finding.id}-${index}`}>{displayText(line)}</p>
                            ))}
                          </div>
                          {finding.regulation_evidence_quote && (
                            <div className="evidence-block regulation-evidence-block">
                              <strong>法规依据</strong>
                              {regulationEvidenceLines(finding).map((line, index) => (
                                <p key={`${finding.id}-regulation-${index}`}>{displayText(line)}</p>
                              ))}
                            </div>
                          )}
                          {finding.ai_rationale && (
                            <p className="ai-rationale">智能理由：{displayText(finding.ai_rationale)}</p>
                          )}
                          {finding.possible_impact && (
                            <p className="impact-text">可能影响：{displayText(finding.possible_impact)}</p>
                          )}
                        </details>
                        {["llm_candidate", "regulatory_rag_candidate"].includes(finding.source_type) && finding.review_status === "pending_review" && (
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
                  </section>
                ))
              ) : (
                <div className="empty-state">
                  <ShieldCheck size={18} />
                  <div>
                    <strong>{findings.length ? "当前筛选下暂无发现" : "尚未形成风险清单"}</strong>
                    <p>
                      {findings.length
                        ? "切换筛选条件可查看其他类型结果。"
                        : "完成资料加载和主数据抽取后，运行规则与智能分析生成可复核发现。"}
                    </p>
                  </div>
                </div>
              )}
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
          </div>
      </section>
      </section>
    </main>
  );
}
