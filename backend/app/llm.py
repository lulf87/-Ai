from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

DEFAULT_CODEX_CLI_MODEL = "gpt-5.4-mini"
DEFAULT_CODEX_CLI_TIMEOUT_SECONDS = 600
DEFAULT_CODEX_CLI_SLIM_CONTEXT = True
DEFAULT_CODEX_CLI_HTTP_TRANSPORT = True
DEFAULT_LLM_PROVIDER = "codex_cli"
DEFAULT_LLM_ALLOW_LOCAL_FALLBACK = False
CODEX_PROVIDER_VALUES = {"codex", "codex_cli", "codex-cli", "llm", "true", "1"}
LOCAL_PROVIDER_VALUES = {"fake", "local", "demo", "offline", "none", "false", "0"}
CODEX_CLI_SLIM_DISABLED_FEATURES = (
    "plugins",
    "apps",
    "browser_use",
    "computer_use",
    "multi_agent",
    "shell_tool",
    "shell_snapshot",
    "workspace_dependencies",
    "image_generation",
    "tool_search",
    "tool_suggest",
)


@dataclass(frozen=True)
class SanitizedSegment:
    document_id: int
    document_type: str
    filename: str
    locator: str
    excerpt: str


@dataclass(frozen=True)
class LLMProviderResult:
    output_json: dict[str, Any]
    output_text: str
    provider: str
    model_name: str
    model_config: dict[str, Any]


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class LLMProvider(Protocol):
    provider_name: str
    model_name: str

    def extract_master_data(
        self,
        segments: list[SanitizedSegment],
        fallback_master_data: dict[str, Any],
    ) -> LLMProviderResult:
        ...

    def analyze_risks(self, segments: list[SanitizedSegment]) -> LLMProviderResult:
        ...

    def analyze_regulatory_rag(
        self,
        segments: list[SanitizedSegment],
        regulation_hits: list[dict[str, Any]],
    ) -> LLMProviderResult:
        ...

    def summarize_regulation_impact(self, regulation_payload: dict[str, Any]) -> LLMProviderResult:
        ...

    def polish_report(self, report_payload: dict[str, Any]) -> LLMProviderResult:
        ...


class FakeLLMProvider:
    provider_name = "fake"
    model_name = "demo-fake-llm"

    def extract_master_data(
        self,
        segments: list[SanitizedSegment],
        fallback_master_data: dict[str, Any],
    ) -> LLMProviderResult:
        fields = {
            key: value
            for key, value in fallback_master_data.items()
            if value not in ("", None)
        }
        evidence = []
        for field_name, value in fields.items():
            if isinstance(value, bool):
                continue
            segment = find_segment(segments, str(value)) or find_segment(segments, field_name)
            if segment:
                evidence.append(
                    {
                        "field_name": field_name,
                        "document_id": segment.document_id,
                        "filename": segment.filename,
                        "locator": segment.locator,
                        "quote": segment.excerpt[:220],
                    }
                )
        return self._result(
            {
                "fields": fields,
                "evidence": evidence,
                "notes": "使用本地安全兜底逻辑生成抽取结果；输入为脱敏摘录。",
            },
            "已基于脱敏摘录生成主数据候选。",
        )

    def analyze_risks(self, segments: list[SanitizedSegment]) -> LLMProviderResult:
        clinical = find_segment(segments, "30例") or find_segment(segments, "免于临床评价")
        disposable = find_segment(segments, "一次性") or find_segment(segments, "重复使用")
        candidates: list[dict[str, Any]] = []
        if clinical:
            candidates.append(
                {
                    "rule_id": "AI-CLINICAL-EVIDENCE-SCOPE",
                    "risk_level": "yellow",
                    "title": "临床评价结论与证据规模需复核",
                    "description": "基于脱敏摘录发现临床评价结论可能强于当前证据规模，建议人工确认临床路径表述是否过度。",
                    "evidence_document": clinical.filename,
                    "evidence_locator": clinical.locator,
                    "evidence_quote": clinical.excerpt[:220],
                    "possible_impact": "可能影响临床评价路径、同品种对比和补正沟通重点。",
                    "recommended_action": "人工复核临床评价结论，必要时补充同品种对比、目录依据或临床证据边界说明。",
                    "ai_rationale": "脱敏摘录同时出现小样本临床描述和较强临床路径结论，适合作为候选问题进入复核。",
                }
            )
        if disposable:
            candidates.append(
                {
                    "rule_id": "AI-LABELING-DISPOSABLE-HANDLING",
                    "risk_level": "yellow",
                    "title": "一次性附件处置说明需复核",
                    "description": "基于脱敏摘录发现一次性附件相关标签表述需要人工确认，避免清洁、处置和复用边界不清。",
                    "evidence_document": disposable.filename,
                    "evidence_locator": disposable.locator,
                    "evidence_quote": disposable.excerpt[:220],
                    "possible_impact": "可能影响说明书标签一致性和风险控制措施完整性。",
                    "recommended_action": "人工核对说明书、风险管理和包装标签中的一次性附件处置表述。",
                    "ai_rationale": "标签类文字在不同资料中容易出现语义边界差异，本项仅作为候选问题，不作为最终结论。",
                }
            )
        return self._result(
            {
                "candidates": candidates,
                "notes": "候选风险默认待人工确认，不直接进入最终报告。",
            },
            f"生成 {len(candidates)} 条候选风险。",
        )

    def analyze_regulatory_rag(
        self,
        segments: list[SanitizedSegment],
        regulation_hits: list[dict[str, Any]],
    ) -> LLMProviderResult:
        candidates: list[dict[str, Any]] = []
        ai_hit = first_regulation_hit(regulation_hits, ["ai_algorithm", "software"])
        ai_segment = (
            find_segment(segments, "自动推荐")
            or find_segment(segments, "智能算法")
            or find_segment(segments, "AI")
        )
        if ai_hit and ai_segment:
            candidates.append(
                regulatory_candidate(
                    hit=ai_hit,
                    segment=ai_segment,
                    rule_id="RAG-AI-ALGORITHM-EVIDENCE",
                    risk_level="yellow",
                    title="智能算法功能与算法资料要求需复核",
                    description="资料出现自动推荐消融参数等智能算法功能，需结合已校验法规依据确认算法资料是否覆盖基本信息、训练验证、性能评价和风险控制。",
                    possible_impact="可能影响软件研究资料、算法研究资料和风险控制证据链完整性。",
                    recommended_action="补充或核对算法资料，明确算法用途、输入输出、训练验证数据、性能评价和风险控制措施。",
                    ai_rationale="项目资料触发智能算法关键词，且已检索到校验法规中的算法资料要求。本项仅作为法规RAG候选，需人工确认。",
                )
            )

        clinical_hit = first_regulation_hit(regulation_hits, ["clinical"])
        clinical_segment = find_segment(segments, "30例") or find_segment(segments, "免于临床评价")
        if clinical_hit and clinical_segment:
            candidates.append(
                regulatory_candidate(
                    hit=clinical_hit,
                    segment=clinical_segment,
                    rule_id="RAG-CLINICAL-EVALUATION-PATH",
                    risk_level="yellow",
                    title="临床评价路径与证据充分性需复核",
                    description="资料中出现少量临床数据或免于临床评价结论，需结合已校验法规依据确认同品种对比、目录依据和临床证据边界。",
                    possible_impact="可能影响临床评价路径选择、同品种对比和补正沟通重点。",
                    recommended_action="人工复核临床评价路径，补充同品种对比、目录依据或临床证据边界说明。",
                    ai_rationale="项目资料触发临床评价关键词，且已检索到校验法规中的临床评价要求。本项仅作为法规RAG候选，需人工确认。",
                )
            )

        labeling_hit = first_regulation_hit(regulation_hits, ["labeling"])
        labeling_segment = find_segment(segments, "一次性") or find_segment(segments, "重复使用")
        if labeling_hit and labeling_segment:
            candidates.append(
                regulatory_candidate(
                    hit=labeling_hit,
                    segment=labeling_segment,
                    rule_id="RAG-LABELING-DISPOSABLE-EVIDENCE",
                    risk_level="yellow",
                    title="一次性附件说明与标签要求需复核",
                    description="资料中出现一次性附件和重复使用相关表述，需结合已校验法规依据确认说明书、标签和风险控制表述边界。",
                    possible_impact="可能影响说明书标签一致性和一次性使用附件的风险控制措施。",
                    recommended_action="核对说明书、标签样稿和风险管理资料，统一一次性使用、处置和警示说明。",
                    ai_rationale="项目资料触发一次性附件关键词，且已检索到校验法规中的说明书标签要求。本项仅作为法规RAG候选，需人工确认。",
                )
            )

        return self._result(
            {
                "candidates": candidates,
                "retrieved_hits": len(regulation_hits),
                "notes": "法规RAG候选默认待人工确认，不直接进入最终报告。",
            },
            f"生成 {len(candidates)} 条法规RAG候选。",
        )

    def summarize_regulation_impact(self, regulation_payload: dict[str, Any]) -> LLMProviderResult:
        modules = regulation_payload.get("applicable_modules") or ["general_submission"]
        title = regulation_payload.get("title", "法规")
        suggestions = [f"复核 {module} 模块规则依据和证据要求" for module in modules]
        return self._result(
            {
                "summary": f"{title} 的智能摘要草稿：需人工核对官方附件后再决定是否更新规则。",
                "change_points": ["提取适用模块", "检查是否影响现有规则触发条件", "确认附件哈希和官方来源"],
                "impacted_modules": modules,
                "suggested_rule_changes": suggestions,
                "verification_status": "pending_review",
            },
            "已生成法规影响草稿，未改变法规校验状态。",
        )

    def polish_report(self, report_payload: dict[str, Any]) -> LLMProviderResult:
        finding_count = report_payload.get("finding_count", 0)
        summary = (
            f"智能辅助分析，非最终注册结论，需人工复核。本次预审基于已确认或规则强制项整理，"
            f"共纳入 {finding_count} 条可报告问题，建议先处理红色风险和证据链断点。"
        )
        return self._result({"summary": summary}, summary)

    def _result(self, output_json: dict[str, Any], output_text: str) -> LLMProviderResult:
        return LLMProviderResult(
            output_json=output_json,
            output_text=output_text,
            provider=self.provider_name,
            model_name=self.model_name,
            model_config={"mode": "deterministic_demo"},
        )


class CodexCLIProvider:
    provider_name = "codex_cli"

    def __init__(
        self,
        command: str | None = None,
        model_name: str | None = None,
        timeout_seconds: int | None = None,
        reasoning_effort: str | None = None,
        reasoning_summary: str | None = None,
        slim_context: bool | None = None,
        http_transport: bool | None = None,
        allow_local_fallback: bool | None = None,
        runner=None,
        fallback_provider: LLMProvider | None = None,
    ) -> None:
        self.command = command or os.getenv("CODEX_CLI_COMMAND", "codex")
        self.model_name = model_name or os.getenv("CODEX_CLI_MODEL", DEFAULT_CODEX_CLI_MODEL)
        self.timeout_seconds = timeout_seconds or int(
            os.getenv("CODEX_CLI_TIMEOUT_SECONDS", str(DEFAULT_CODEX_CLI_TIMEOUT_SECONDS))
        )
        self.reasoning_effort = reasoning_effort or os.getenv("CODEX_CLI_REASONING_EFFORT", "low")
        self.reasoning_summary = reasoning_summary or os.getenv("CODEX_CLI_REASONING_SUMMARY", "none")
        self.slim_context = (
            env_bool("CODEX_CLI_SLIM_CONTEXT", DEFAULT_CODEX_CLI_SLIM_CONTEXT)
            if slim_context is None
            else slim_context
        )
        self.http_transport = (
            env_bool("CODEX_CLI_HTTP_TRANSPORT", DEFAULT_CODEX_CLI_HTTP_TRANSPORT)
            if http_transport is None
            else http_transport
        )
        self.allow_local_fallback = (
            env_bool("LLM_ALLOW_LOCAL_FALLBACK", DEFAULT_LLM_ALLOW_LOCAL_FALLBACK)
            if allow_local_fallback is None
            else allow_local_fallback
        )
        self._uses_default_runner = runner is None
        self.runner = runner or run_codex_command
        self.fallback_provider = fallback_provider or FakeLLMProvider()

    def extract_master_data(
        self,
        segments: list[SanitizedSegment],
        fallback_master_data: dict[str, Any],
    ) -> LLMProviderResult:
        prompt = codex_prompt(
            task="extract_master_data",
            payload={
                "fallback_master_data": fallback_master_data,
                "segments": segments_payload(segments),
            },
            output_contract={
                "fields": "object with extracted master-data fields",
                "evidence": "array of {field_name, document_id, filename, locator, quote}",
                "notes": "short Chinese note",
            },
        )
        return self._run_or_fallback(
            prompt=prompt,
            fallback=lambda: self.fallback_provider.extract_master_data(
                segments, fallback_master_data
            ),
        )

    def analyze_risks(self, segments: list[SanitizedSegment]) -> LLMProviderResult:
        prompt = codex_prompt(
            task="analyze_risks",
            payload={"segments": segments_payload(segments)},
            output_contract={
                "candidates": (
                    "array of {rule_id, risk_level, title, description, evidence_document, "
                    "evidence_locator, evidence_quote, possible_impact, recommended_action, ai_rationale}; "
                    "evidence_quote must be readable Chinese lines like "
                    "'综述资料（01_overview.md，全文）：产品名称：...' and must explain which file says what"
                ),
                "notes": "short Chinese note",
            },
        )
        return self._run_or_fallback(
            prompt=prompt,
            fallback=lambda: self.fallback_provider.analyze_risks(segments),
        )

    def analyze_regulatory_rag(
        self,
        segments: list[SanitizedSegment],
        regulation_hits: list[dict[str, Any]],
    ) -> LLMProviderResult:
        prompt = codex_prompt(
            task="analyze_regulatory_rag",
            payload={
                "segments": segments_payload(segments),
                "regulation_hits": regulation_hits,
            },
            output_contract={
                "candidates": (
                    "array of {rule_id, risk_level, title, description, evidence_document, "
                    "evidence_locator, evidence_quote, possible_impact, recommended_action, "
                    "ai_rationale, regulation_id, regulation_title, regulation_attachment_id, "
                    "regulation_attachment_filename, regulation_attachment_sha256, "
                    "regulation_evidence_locator, regulation_evidence_quote}; use only the provided "
                    "regulation_hits and keep every candidate pending-review wording"
                ),
                "retrieved_hits": "number of regulation hits reviewed",
                "notes": "short Chinese note",
            },
        )
        return self._run_or_fallback(
            prompt=prompt,
            fallback=lambda: self.fallback_provider.analyze_regulatory_rag(
                segments, regulation_hits
            ),
        )

    def summarize_regulation_impact(self, regulation_payload: dict[str, Any]) -> LLMProviderResult:
        prompt = codex_prompt(
            task="summarize_regulation_impact",
            payload={"regulation": regulation_payload},
            output_contract={
                "summary": "Chinese draft summary",
                "change_points": "array of concise change points",
                "impacted_modules": "array of module ids",
                "suggested_rule_changes": "array of draft rule changes",
                "verification_status": "must be pending_review",
            },
        )
        return self._run_or_fallback(
            prompt=prompt,
            fallback=lambda: self.fallback_provider.summarize_regulation_impact(
                regulation_payload
            ),
        )

    def polish_report(self, report_payload: dict[str, Any]) -> LLMProviderResult:
        prompt = codex_prompt(
            task="polish_report",
            payload={"report": report_payload},
            output_contract={"summary": "Chinese executive summary with required boundary statement"},
        )
        return self._run_or_fallback(
            prompt=prompt,
            fallback=lambda: self.fallback_provider.polish_report(report_payload),
        )

    def _run_or_fallback(self, prompt: str, fallback) -> LLMProviderResult:
        try:
            output_json, output_text = self._run(prompt)
            return LLMProviderResult(
                output_json=output_json,
                output_text=output_text,
                provider=self.provider_name,
                model_name=self.model_name,
                model_config={
                    "command": self.command,
                    "timeout_seconds": self.timeout_seconds,
                    "reasoning_effort": self.reasoning_effort,
                    "reasoning_summary": self.reasoning_summary,
                    "slim_context": self.slim_context,
                    "http_transport": self.http_transport,
                    "allow_local_fallback": self.allow_local_fallback,
                    "sandbox": "read-only",
                    "input_policy": "desensitized_excerpts_only",
                },
            )
        except Exception as exc:
            if not self.allow_local_fallback:
                raise RuntimeError(str(exc) or exc.__class__.__name__) from exc
            result = fallback()
            model_config = dict(result.model_config)
            model_config["fallback_from"] = self.provider_name
            model_config["fallback_error"] = str(exc)
            model_config["attempted_model"] = self.model_name
            model_config["attempted_timeout_seconds"] = self.timeout_seconds
            model_config["attempted_reasoning_effort"] = self.reasoning_effort
            model_config["attempted_reasoning_summary"] = self.reasoning_summary
            model_config["attempted_slim_context"] = self.slim_context
            model_config["attempted_http_transport"] = self.http_transport
            model_config["attempted_allow_local_fallback"] = self.allow_local_fallback
            return LLMProviderResult(
                output_json=result.output_json,
                output_text=result.output_text,
                provider=result.provider,
                model_name=result.model_name,
                model_config=model_config,
            )

    def _run(self, prompt: str) -> tuple[dict[str, Any], str]:
        if self._uses_default_runner and shutil.which(self.command) is None:
            raise RuntimeError(f"Codex CLI command not found: {self.command}")
        with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False) as output_file:
            output_path = Path(output_file.name)
        try:
            command = [self.command]
            if self.model_name:
                command.extend(["--model", self.model_name])
            if self.http_transport:
                command.extend(
                    [
                        "-c",
                        'model_provider="openai_http"',
                        "-c",
                        'model_providers.openai_http.name="OpenAI"',
                        "-c",
                        'model_providers.openai_http.wire_api="responses"',
                        "-c",
                        "model_providers.openai_http.requires_openai_auth=true",
                        "-c",
                        "model_providers.openai_http.supports_websockets=false",
                        "-c",
                        "features.responses_websockets=false",
                        "-c",
                        "features.responses_websockets_v2=false",
                    ]
                )
            if self.slim_context:
                for feature in CODEX_CLI_SLIM_DISABLED_FEATURES:
                    command.extend(["--disable", feature])
            command.extend(
                [
                    "--ask-for-approval",
                    "never",
                    "-c",
                    f'model_reasoning_effort="{self.reasoning_effort}"',
                    "-c",
                    f'model_reasoning_summary="{self.reasoning_summary}"',
                    "-c",
                    "notify=[]",
                    "exec",
                    "--sandbox",
                    "read-only",
                    "--skip-git-repo-check",
                    "--ephemeral",
                ]
            )
            if self.slim_context:
                command.append("--ignore-rules")
            command.extend(
                [
                    "--color",
                    "never",
                    "--output-last-message",
                    str(output_path),
                    "-",
                ]
            )
            result = self.runner(command, prompt, self.timeout_seconds)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "Codex CLI failed")
            output_text = output_path.read_text(encoding="utf-8").strip()
            if not output_text:
                output_text = result.stdout.strip()
            return parse_json_object(output_text), output_text
        finally:
            output_path.unlink(missing_ok=True)


def run_codex_command(command: list[str], prompt: str, timeout_seconds: int) -> CommandResult:
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(input=prompt, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        raise
    return CommandResult(
        returncode=process.returncode,
        stdout=stdout,
        stderr=stderr,
    )


def codex_prompt(task: str, payload: dict[str, Any], output_contract: dict[str, Any]) -> str:
    return (
        "你是医疗器械注册资料预审系统中的大模型辅助层。\n"
        "边界：只能基于输入的脱敏摘录、证据引用和法规元数据工作；不要要求或推断原始上传文件；"
        "不要输出最终获批判断；AI 候选风险必须保持待人工复核语气。\n"
        "面向非技术用户：标题、描述、建议和证据不要使用字段名、枚举值、变量名、英文状态码或开发术语；"
        "证据必须说明“哪份资料/哪个文件写了什么”。\n"
        "若输出风险候选：标题不超过18个汉字；描述、可能影响、建议和智能理由各用一句话，避免重复；"
        "描述不超过70个汉字，可能影响、建议和智能理由各不超过60个汉字；证据摘录只保留关键句。\n"
        "请只输出一个 JSON object，不要 Markdown，不要解释性前后缀。\n"
        f"task={task}\n"
        "input=desensitized_excerpts_only\n"
        f"output_contract={json.dumps(output_contract, ensure_ascii=False)}\n"
        f"payload={json.dumps(payload, ensure_ascii=False)}\n"
    )


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def segments_payload(segments: list[SanitizedSegment]) -> list[dict[str, Any]]:
    return [
        {
            "document_id": segment.document_id,
            "document_type": segment.document_type,
            "filename": segment.filename,
            "locator": segment.locator,
            "excerpt": segment.excerpt,
        }
        for segment in segments
    ]


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end < start:
            raise
        parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Codex CLI response must be a JSON object")
    return parsed


def find_segment(segments: list[SanitizedSegment], term: str) -> SanitizedSegment | None:
    normalized = term.strip()
    if not normalized:
        return None
    for segment in segments:
        if normalized in segment.excerpt:
            return segment
    return None


def first_regulation_hit(
    regulation_hits: list[dict[str, Any]],
    modules: list[str],
) -> dict[str, Any] | None:
    for module in modules:
        for hit in regulation_hits:
            if hit.get("module") == module:
                return hit
    return None


def regulatory_candidate(
    *,
    hit: dict[str, Any],
    segment: SanitizedSegment,
    rule_id: str,
    risk_level: str,
    title: str,
    description: str,
    possible_impact: str,
    recommended_action: str,
    ai_rationale: str,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "risk_level": risk_level,
        "title": title,
        "description": description,
        "evidence_document": segment.filename,
        "evidence_locator": segment.locator,
        "evidence_quote": segment.excerpt[:220],
        "possible_impact": possible_impact,
        "recommended_action": recommended_action,
        "ai_rationale": ai_rationale,
        "regulation_id": hit.get("regulation_id"),
        "regulation_title": hit.get("regulation_title", ""),
        "regulation_attachment_id": hit.get("attachment_id"),
        "regulation_attachment_filename": hit.get("attachment_filename", ""),
        "regulation_attachment_sha256": hit.get("attachment_sha256", ""),
        "regulation_evidence_locator": hit.get("locator", ""),
        "regulation_evidence_quote": hit.get("quote", ""),
    }


def get_llm_provider() -> LLMProvider:
    provider = os.getenv("LLM_PROVIDER", DEFAULT_LLM_PROVIDER).strip().lower()
    if provider in CODEX_PROVIDER_VALUES:
        return CodexCLIProvider()
    if provider in LOCAL_PROVIDER_VALUES:
        return FakeLLMProvider()
    raise ValueError(
        f"Unsupported LLM_PROVIDER={provider!r}; use 'codex_cli' for real LLM or 'fake' "
        "for explicit local demo mode."
    )


def validate_llm_startup_configuration(provider: LLMProvider | None = None) -> None:
    selected_provider = provider or get_llm_provider()
    if (
        isinstance(selected_provider, CodexCLIProvider)
        and selected_provider._uses_default_runner
        and shutil.which(selected_provider.command) is None
    ):
        raise RuntimeError(
            f"Codex CLI command not found: {selected_provider.command}. "
            "Install Codex CLI, set CODEX_CLI_COMMAND, or explicitly set LLM_PROVIDER=fake "
            "for local demo mode."
        )
