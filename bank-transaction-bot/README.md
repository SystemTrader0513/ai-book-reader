# Trace · 卡交易拒绝诊断 Bot

可本地运行的网页工程。基于四层控制、七类拒绝原因、六类限额，演示交易排查、证据归因和下一步指引。

**默认全部为 MOCK 数据。无需模型密钥、无需 Node、无需安装第三方 Python 包。**

## 启动

要求 Python 3.9+，现代浏览器。

```bash
cd /Users/minyanhua/Documents/ChatGPT/bank_transaction_chatbok
python3 -m app.server
```

打开 <http://127.0.0.1:8765>。也可以运行 `./run.sh`。终端 Ctrl+C 停止。

端口被占用时：

```bash
python3 -m app.server --port 8877
```

移植后请先进入工程根目录运行相同命令，不依赖原始绝对路径。

## 先体验这些场景

1. 选择“每日线上消费限额 · Card”，点击“为什么被拒？”：历史日限额 1000、已用 700、剩余 300，交易 500 被拒。
2. 同一案例点击“现在剩余额度？”：读取独立当前快照，已用 850、剩余 150，而非复用历史 300。
3. 选择“当时锁定，目前已解除”：分别询问历史原因和当前控制。
4. 选择“只有当前状态，缺少历史证据”：只能推测，不能确认历史原因。
5. 选择“安全限制 · Entity”：只返回泛化解释，原始风险字段不进入 API。
6. 选择“多项限制”：实际记录主因与可能阻碍分别保留。
7. 选择“检查未执行”或“网络超时”：不会说检查通过，也不会强归因为银行控制。

总计 19 个模拟案例，使用固定演示时间，并非真实当前时间。切换案例会清空旧诊断，避免串卡归因。

## 默认模式和可选 AI

默认是**本地关键词意图识别＋确定性业务诊断**。不是离线大模型，不会自由回答任意话题。三种快捷问题可直接调用对应业务路径。

可选启用兼容 Chat Completions 的模型接口，模型仅返回意图枚举：

```bash
export BOT_MODEL_MODE=llm
export BOT_LLM_ENDPOINT='https://your-approved-gateway.example/v1/chat/completions'
export BOT_LLM_MODEL='your-approved-model'
read -s BOT_LLM_API_KEY
export BOT_LLM_API_KEY
python3 -m app.server
```

上面是占位示例，请填内部批准网关；密钥只在后端环境变量中，前端不接触。工程不自动读取 `.env`。

接口要求：HTTPS；请求 `model/messages/temperature`；响应 `choices[0].message.content` 为 `{"intent":"DECLINE"}` 等允许枚举。超时 12 秒、错误、缺密钥或无效输出都会回退本地，并在网页标记。实际外部模型联调未执行；模型合同使用受控测试验证。

开启后会把用户当前问题发送到配置网关；不发送模拟银行原始记录或历史对话。连续 6 位以上数字仅作基础替换，**不等同于生产 DLP**。不要输入真实敏感信息。

## 架构与文件

当前按领域本体、映射、规则、表现四层拆分，披露策略独立于话术：

```text
config/ontology.json      领域类、继承、四层/七原因/六限额及动作适用关系
ontology/                 OWL/Turtle 导出、SHACL 起步约束
mappings/                 原始字段、枚举、版本化响应码线索映射
rules/diagnosis.json      基础诊断与限额诊断决策表
policies/disclosure.json  披露等级、字段遮盖、允许提供的指引
templates/zh-CN.json      解释、缺失证据名称、指引与回复模板
config/runtime.json       模拟用户及默认映射profile
config/scenarios.json     19个模拟案例
config/raw-bank-example.json  旧系统字段结构的模拟映射示例
app/mapping.py            白名单字段映射和类型检查
app/rules.py              受限JSON决策表执行器，无eval
app/diagnosis.py          可信事实构造、调用决策表
app/disclosure.py         表现前的政策过滤
app/presentation.py       已过滤事实到模板
app/service.py            仅编排以上各层
app/conversation.py       对话入口及可选模型意图适配
app/server.py             本机HTTP与输入校验
static/                   网页布局与交互
```

运行时使用 JSON 类图进行类型遍历、原因分类及指引匹配，**不是完整 OWL DL 推理机**，也不默认执行 SHACL。无图数据库依赖。

交给内部 LLM 前，先阅读 [内部平台融合交接文档](docs/LLM_HANDOFF_INTERNAL_MIGRATION.md)：要求先核对内部架构、PRD 和 DDL，再给融合建议与实施顺序。

详细设计、可用规则条件、映射示例和逐层修改方法见 [四层设计与配置指南](docs/FOUR_LAYER_DESIGN.md)。内部业务缺口仍集中在 [内部迁移手册](docs/INTERNAL_MIGRATION.md)。

修改配置后先校验，再重启服务（不热更新）：

```bash
python3 tools/validate_config.py
python3 -m unittest discover -s tests -v
python3 tools/export_ontology.py
python3 tools/package.py
```

校验器回放19个案例的三种意图及旧系统映射示例；打包工具输出 `dist/trace-card-bot.zip`，可整体移植到其他目录。原始 skill 保留，运行时不把其内容作为系统指令执行。

## API

- `GET /api/health`：健康与模式。
- `GET /api/scenarios`：脱敏的模拟候选交易。
- `GET /api/ontology`：演示业务目录。
- `POST /api/chat`：`{"message":"为什么被拒","scenario_id":"online-card"}`。
- 可选 `intent`：`DECLINE / LIMIT / CONTROL / GENERAL / FRAUD_OR_SECURITY / OUT_OF_SCOPE`。

无真实认证、无数据库持久化、无任何写银行状态的接口。仅绑定 `127.0.0.1`。演示 UI 同时展示调试信息，内部客户版上线前必须移除相关诊断标识。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

HTTP 测试需要系统允许绑定本机回环端口；如果在受限沙箱中被拒绝，请在普通终端运行。

详细的未确认定义、API 替换合同、策略差距和上线检查见 [内部迁移手册](docs/INTERNAL_MIGRATION.md)。最新验收见 [四层拆分验收报告](docs/dev-loop-runs/2026-11-22-four-layers/04-acceptance-report.md)。
