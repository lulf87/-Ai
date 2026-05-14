# 注册资料 AI 辅助检查 V0.2 Demo

本项目是一个本地/私有化优先的三类有源医疗器械注册资料预审 Demo。它用于上传脱敏注册资料包，抽取产品主数据，运行规则检查，并导出带证据定位的红黄绿风险报告。

V0.2 增加大模型辅助层，但大模型不是最终裁判。系统默认使用 deterministic fake provider 供本地演示和测试；接入真实云端模型时，只允许发送脱敏摘录、样例资料片段和法规元数据，不发送原始敏感注册资料。

本 Demo 不做自动注册、不判断最终能否获批、不把 PolicyNote 作为核心法规依据。规则依据只引用人工校验后的 NMPA/CMDE 官方来源。

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest backend/tests -q
uvicorn backend.app.main:app --reload
```

## LLM Provider

默认 provider 是 `fake`，适合离线演示和自动化测试：

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

如果你已经登录并可直接使用 Codex CLI，可以用本机 `codex exec` 作为大模型层：

```bash
LLM_PROVIDER=codex_cli uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

可选环境变量：

- `CODEX_CLI_COMMAND`：Codex CLI 命令路径，默认 `codex`
- `CODEX_CLI_MODEL`：传给 `codex --model` 的模型名，默认 `gpt-5.4-mini`；需要更强推理时可改为 `gpt-5.5`
- `CODEX_CLI_TIMEOUT_SECONDS`：单次调用超时，默认 `600`
- `CODEX_CLI_REASONING_EFFORT`：推理强度，默认 `low`，避免继承本机 Codex 的 `xhigh`
- `CODEX_CLI_REASONING_SUMMARY`：推理摘要，默认 `none`
- `CODEX_CLI_SLIM_CONTEXT`：是否使用瘦身上下文，默认 `true`；会在子调用中关闭插件/工具并忽略项目规则，降低 Codex CLI 输入负担
- `CODEX_CLI_HTTP_TRANSPORT`：是否强制 Codex CLI 使用 HTTP Responses provider，默认 `true`；用于规避 WebSocket 链路里的 `Reconnecting... (timeout waiting for child process to exit)` 问题

Codex CLI provider 只接收系统生成的脱敏摘录、证据位置和法规元数据；如果 CLI 不可用或调用失败，系统会回退到 fake provider，并在 `LLMRun.model_config_json` 中记录 `fallback_from`、`fallback_error`、`attempted_model`、`attempted_timeout_seconds`、`attempted_slim_context` 和 `attempted_http_transport`。瘦身上下文不改变应用侧的脱敏、只读 sandbox 和证据边界；它只是不让这个子调用加载当前项目开发规则、浏览器插件和工具上下文。

另开终端启动前端：

```bash
cd frontend
npm install
npm run dev
```

如需只通过后端端口打开完整界面：

```bash
cd frontend
npm run build
cd ..
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

## Demo Flow

1. 创建项目，填写注册场景和产品特征。
2. 上传综述、产品技术要求、说明书、风险管理、临床评价、检验报告、软件资料等脱敏文件。
3. 抽取产品主数据并人工确认，也可以点击 AI 抽取查看字段证据。
4. 运行规则检查，再点击 AI 风险生成候选问题。
5. 对 AI 候选问题执行确认或驳回。
6. 生成 Word 预审报告；报告只纳入规则命中项和人工确认/编辑后的 AI 候选。

## Safety Boundary

- 原始上传资料只读保存并计算 SHA256。
- 所有结论必须引用证据片段或标记为待确认。
- 未人工校验的法规不得作为规则依据。
- AI 候选风险默认 `pending_review`，不能直接作为最终红色结论。
- `LLMRun` 只记录输入摘要、配置、输出和耗时，不保存完整原始资料。
- 默认本地运行，不配置外部模型；接入云端模型前必须经过脱敏/摘录层。
