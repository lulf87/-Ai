import json
import subprocess

import pytest

from backend.app.llm import (
    CodexCLIProvider,
    CommandResult,
    DEFAULT_CODEX_CLI_MODEL,
    DEFAULT_CODEX_CLI_HTTP_TRANSPORT,
    DEFAULT_CODEX_CLI_SLIM_CONTEXT,
    DEFAULT_CODEX_CLI_TIMEOUT_SECONDS,
    FakeLLMProvider,
    SanitizedSegment,
    get_llm_provider,
    validate_llm_startup_configuration,
)


def test_codex_cli_provider_defaults_to_faster_model_and_long_timeout(monkeypatch):
    monkeypatch.delenv("CODEX_CLI_MODEL", raising=False)
    monkeypatch.delenv("CODEX_CLI_HTTP_TRANSPORT", raising=False)
    monkeypatch.delenv("CODEX_CLI_SLIM_CONTEXT", raising=False)
    monkeypatch.delenv("CODEX_CLI_TIMEOUT_SECONDS", raising=False)

    provider = CodexCLIProvider(command="codex", runner=lambda *args: None)

    assert provider.model_name == DEFAULT_CODEX_CLI_MODEL
    assert provider.timeout_seconds == DEFAULT_CODEX_CLI_TIMEOUT_SECONDS
    assert provider.slim_context == DEFAULT_CODEX_CLI_SLIM_CONTEXT
    assert provider.http_transport == DEFAULT_CODEX_CLI_HTTP_TRANSPORT
    assert provider.allow_local_fallback is False


def test_codex_cli_provider_sends_sanitized_prompt_and_parses_json():
    calls = []

    def runner(command, prompt, timeout_seconds):
        calls.append((command, prompt, timeout_seconds))
        return CommandResult(
            returncode=0,
            stdout=json.dumps(
                {
                    "fields": {"product_name": "AI抽取产品"},
                    "evidence": [
                        {
                            "field_name": "product_name",
                            "filename": "overview.md",
                            "locator": "第1节",
                            "quote": "产品名称：AI抽取产品",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            stderr="",
        )

    provider = CodexCLIProvider(command="codex", runner=runner)

    result = provider.extract_master_data(
        [
            SanitizedSegment(
                document_id=1,
                document_type="overview",
                filename="overview.md",
                locator="第1节",
                excerpt="产品名称：AI抽取产品。[已脱敏]",
            )
        ],
        {"product_name": ""},
    )

    assert result.provider == "codex_cli"
    assert result.output_json["fields"]["product_name"] == "AI抽取产品"
    command, prompt, timeout_seconds = calls[0]
    assert command[0] == "codex"
    assert command[1:3] == ["--model", DEFAULT_CODEX_CLI_MODEL]
    assert 'model_provider="openai_http"' in command
    assert 'model_providers.openai_http.wire_api="responses"' in command
    assert "model_providers.openai_http.supports_websockets=false" in command
    assert "features.responses_websockets=false" in command
    assert "--disable" in command
    assert "plugins" in command
    assert "shell_tool" in command
    assert "--ask-for-approval" in command
    assert "never" in command
    assert 'model_reasoning_effort="low"' in command
    assert 'model_reasoning_summary="none"' in command
    assert "notify=[]" in command
    assert "exec" in command
    assert "--ignore-rules" in command
    assert "read-only" in command
    assert timeout_seconds == DEFAULT_CODEX_CLI_TIMEOUT_SECONDS
    assert "input=desensitized_excerpts_only" in prompt
    assert "植入式心脏起搏器患者禁用" not in prompt


def test_codex_cli_provider_raises_by_default_when_cli_fails():
    def failing_runner(command, prompt, timeout_seconds):
        return CommandResult(returncode=1, stdout="", stderr="not logged in")

    provider = CodexCLIProvider(command="codex", runner=failing_runner)

    with pytest.raises(RuntimeError, match="not logged in"):
        provider.analyze_risks(
            [
                SanitizedSegment(
                    document_id=1,
                    document_type="clinical_evaluation",
                    filename="clinical.md",
                    locator="全文",
                    excerpt="本资料基于 30例 单臂观察数据进行总结。",
                )
            ]
        )


def test_codex_cli_provider_falls_back_to_fake_when_explicitly_allowed():
    def failing_runner(command, prompt, timeout_seconds):
        return CommandResult(returncode=1, stdout="", stderr="not logged in")

    provider = CodexCLIProvider(
        command="codex",
        runner=failing_runner,
        allow_local_fallback=True,
    )

    result = provider.analyze_risks(
        [
            SanitizedSegment(
                document_id=1,
                document_type="clinical_evaluation",
                filename="clinical.md",
                locator="全文",
                excerpt="本资料基于 30例 单臂观察数据进行总结。",
            )
        ]
    )

    assert result.provider == "fake"
    assert result.model_config["fallback_from"] == "codex_cli"
    assert result.model_config["fallback_error"]
    assert result.model_config["attempted_model"] == DEFAULT_CODEX_CLI_MODEL
    assert result.model_config["attempted_timeout_seconds"] == DEFAULT_CODEX_CLI_TIMEOUT_SECONDS
    assert result.model_config["attempted_slim_context"] is True
    assert result.model_config["attempted_http_transport"] is True
    assert result.output_json["candidates"]


def test_codex_cli_provider_falls_back_to_fake_when_cli_times_out():
    def timeout_runner(command, prompt, timeout_seconds):
        raise subprocess.TimeoutExpired(command, timeout_seconds)

    provider = CodexCLIProvider(
        command="codex",
        runner=timeout_runner,
        allow_local_fallback=True,
    )

    result = provider.extract_master_data([], {"product_name": "兜底产品"})

    assert result.provider == "fake"
    assert result.model_config["fallback_from"] == "codex_cli"
    assert "timed out" in result.model_config["fallback_error"]
    assert result.output_json["fields"]["product_name"] == "兜底产品"


def test_get_llm_provider_defaults_to_codex_cli(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    provider = get_llm_provider()

    assert isinstance(provider, CodexCLIProvider)


def test_get_llm_provider_can_select_codex_cli(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "codex_cli")

    provider = get_llm_provider()

    assert isinstance(provider, CodexCLIProvider)


def test_get_llm_provider_can_select_fake_only_when_explicit(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")

    provider = get_llm_provider()

    assert isinstance(provider, FakeLLMProvider)


def test_get_llm_provider_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "accidental-local")

    with pytest.raises(ValueError, match="Unsupported LLM_PROVIDER"):
        get_llm_provider()


def test_startup_validation_rejects_missing_real_llm_command(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "codex_cli")
    monkeypatch.setenv("CODEX_CLI_COMMAND", "/not/a/real/codex")

    with pytest.raises(RuntimeError, match="Codex CLI command not found"):
        validate_llm_startup_configuration()


def test_startup_validation_allows_explicit_local_demo(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")

    validate_llm_startup_configuration()
