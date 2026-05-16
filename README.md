# 注册资料 AI 辅助检查 V0.3 Demo

本项目是一个本地/私有化优先的三类有源医疗器械注册资料预审 Demo。它用于上传脱敏注册资料包，抽取产品主数据，运行规则检查，并导出带证据定位的红黄绿风险报告。

V0.3 在 V0.2 的法规库、真实 LLM 默认和人工确认闭环之上，把产品定位升级为“注册资料发补风险驾驶舱”：新增老板版申报准备度、重大断点、责任人分布、整改动作、主数据一致性矩阵、资料完整性检查、高风险有源触发器和法规义务库雏形。

V0.2 增加的大模型辅助层仍然保留，但大模型不是最终裁判。系统默认使用本机 Codex CLI 作为真实 LLM provider；只有显式设置 `LLM_PROVIDER=fake` 时才进入本地 deterministic demo 模式。接入真实云端模型时，只允许发送脱敏摘录、样例资料片段和法规元数据，不发送原始敏感注册资料。

本 Demo 不做自动注册、不判断最终能否获批、不把 PolicyNote 作为核心法规依据。规则依据只引用人工校验后的 NMPA/CMDE 官方来源。

V0.2 的法规库包含面向 II 类和 III 类有源医疗器械注册的预置法规清单，并支持通过网页 URL 或 `doc`/`docx`/`pdf`/`txt`/`md` 文件导入法规材料。有附件的官方发布页只作为来源入口，法规附件会作为独立数据源保存、计算 SHA、抽取正文并进入本地检索；没有附件且官方网页本身就是法规正文时，系统会保存官方网页正文快照并计算网页内容 SHA。预置法规和导入法规默认均为待确认状态；只有补齐官方链接，并至少有一个已下载/已上传且完成正文抽取的可校验来源 SHA 后，才允许人工标记为已校验并作为规则依据。

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest backend/tests -q
uvicorn backend.app.main:app --reload
```

## LLM Provider

默认 provider 是 `codex_cli`。也就是说，除非你显式指定不走 LLM，后端启动和“智能抽取/智能分析”都会使用本机 `codex exec`：

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

等价显式写法：

```bash
LLM_PROVIDER=codex_cli uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

如果只想离线演示或跑确定性本地测试，必须显式指定：

```bash
LLM_PROVIDER=fake uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

可选环境变量：

- `LLM_PROVIDER`：默认 `codex_cli`；只有显式设为 `fake`/`local`/`demo`/`offline` 才使用本地演示 provider
- `LLM_ALLOW_LOCAL_FALLBACK`：默认 `false`；真实 LLM 调用失败时默认报错，不静默回退到本地结果。如需保留旧演示行为，可显式设为 `1`
- `CODEX_CLI_COMMAND`：Codex CLI 命令路径，默认 `codex`
- `CODEX_CLI_MODEL`：传给 `codex --model` 的模型名，默认 `gpt-5.4-mini`；需要更强推理时可改为 `gpt-5.5`
- `CODEX_CLI_TIMEOUT_SECONDS`：单次调用超时，默认 `600`
- `CODEX_CLI_REASONING_EFFORT`：推理强度，默认 `low`，避免继承本机 Codex 的 `xhigh`
- `CODEX_CLI_REASONING_SUMMARY`：推理摘要，默认 `none`
- `CODEX_CLI_SLIM_CONTEXT`：是否使用瘦身上下文，默认 `true`；会在子调用中关闭插件/工具并忽略项目规则，降低 Codex CLI 输入负担
- `CODEX_CLI_HTTP_TRANSPORT`：是否强制 Codex CLI 使用 HTTP Responses provider，默认 `true`；用于规避 WebSocket 链路里的 `Reconnecting... (timeout waiting for child process to exit)` 问题

Codex CLI provider 只接收系统生成的脱敏摘录、证据位置和法规元数据。启动时会校验真实 LLM 命令是否可用；如果找不到 `codex`，除非显式 `LLM_PROVIDER=fake`，后端会启动失败。真实 LLM 调用失败时默认报错，不再静默变成本地结果；只有显式 `LLM_ALLOW_LOCAL_FALLBACK=1` 时，系统才会回退到 fake provider，并在 `LLMRun.model_config_json` 中记录 `fallback_from`、`fallback_error`、`attempted_model`、`attempted_timeout_seconds`、`attempted_slim_context` 和 `attempted_http_transport`。瘦身上下文不改变应用侧的脱敏、只读 sandbox 和证据边界；它只是不让这个子调用加载当前项目开发规则、浏览器插件和工具上下文。

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

## V0.3 Risk Dashboard

- `GET /projects/{project_id}/dashboard`：返回申报准备度、红/黄/绿风险数、重大申报断点、责任人分布和下一步动作。
- `GET /projects/{project_id}/consistency-matrix`：横向比较不同资料中的产品名称、型号规格、结构组成、适用范围、软件版本、使用寿命和检验/代表型号。
- 规则引擎新增资料完整性检查、软件/网络安全/AI 专项资料缺口、PTQ-检测报告覆盖矩阵、多型号代表性说明、不适用理由、义务库证据缺口等预审项。
- Word 报告第一页新增老板摘要：项目总体风险、申报准备度、重大申报断点、责任人分布和下一步必须完成的动作。
- `knowledge_base/regulatory_obligations_v03.json` 和 `config/risk_rules_v03.json` 是条款级义务库/配置化规则雏形；其中义务条目需注册法规负责人逐条 verified 后，才能作为最终法规结论。

## Regulation Library

- 预置法规覆盖注册通用要求、申报资料、产品技术要求/检验、软件、网络安全、人工智能、临床评价、使用期限、风险管理和说明书标签等模块。
- 预置法规中的官方网页链接用于定位法规来源；点击“下载预置来源”可批量保存当前预置附件并抽取正文。没有附件 URL 的预置法规会保存官方网页正文快照。非 NMPA/CMDE/SAMR 官方直连附件只作为参考来源展示，不满足“确认校验”条件。
- 网页导入会保存网页正文摘要和网页内容 SHA，但不会替代附件文件 SHA，也不会单独满足“确认校验”条件。
- 文件导入和附件 URL 导入会保存文件、计算 SHA，并抽取法规文本分段供后续摘要、正文检索和人工确认。
- 当前检索是本地确定性关键词检索；后续如接入 RAG，应以这些附件正文分段为语料，并在回答中引用附件 SHA 和分段定位。
- 未校验法规不能被规则命中项引用；AI 法规影响摘要仍是草稿，不改变法规校验状态。

## Safety Boundary

- 原始上传资料只读保存并计算 SHA256。
- 所有结论必须引用证据片段或标记为待确认。
- 未人工校验的法规不得作为规则依据。
- 预置或导入法规的适用性必须由人工确认；仅有网页链接、未下载的附件元数据或转载附件 SHA 不等于最终法规依据。
- AI 候选风险默认 `pending_review`，不能直接作为最终红色结论。
- `LLMRun` 只记录输入摘要、配置、输出和耗时，不保存完整原始资料。
- 默认走真实 LLM，但只发送脱敏摘录、证据定位和法规元数据；如需不走 LLM，必须显式设置 `LLM_PROVIDER=fake`。
