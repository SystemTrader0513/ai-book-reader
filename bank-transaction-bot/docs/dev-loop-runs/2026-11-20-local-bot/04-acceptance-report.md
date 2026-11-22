# Acceptance Report

## Verdict
PASS_WITH_NOTES：本地模拟工程功能验收通过；不代表真实银行、模型供应商或生产环境已验收。

## Scope Checked
网页、业务规则、模拟数据适配、本体类图、Turtle 导出同步、API 输入边界、可选模型合同、迁移说明。

## Reviewers Run
计划：架构/测试/产品/风险内联审查。最终：只读代码审查代理，未发现 BLOCKER/IMPORTANT；指出当前风险状态文案沿用历史交易措辞的 NIT，已新增回归并修正。代理独立验证 31 项非 HTTP 测试；其 HTTP 端口受限，完整 HTTP 由主执行器在获准回环环境验证。无提交、无发布。

## Tests Run
`python3 -m unittest discover -s tests -v`：43 tests，OK。原始输出见 artifacts/test-results.txt。
`python3 -m compileall -q app tools tests`：通过。
压缩包移植验证：解压到 `/tmp/trace-card-bot-portability/trace-card-bot`，独立运行全部 43 项测试通过。
启动：`python3 -m app.server --port 8765`，页面和 API 正常。

## Requirement Coverage
| 要求 | 证据 |
|---|---|
| 本机启动，无必装依赖 | Python 3.9.6 实际启动；HTTP 集成测试 |
| 四层归因、七原因、六限额 | 目录、19 案例、对应集合覆盖测试 |
| 本体参与诊断 | 父类遍历决定原因分类与指引；继承环校验；TTL 导出同步测试 |
| 可解释证据和确定性 | 历史/当前分离、缺失、冲突、PASS、SKIPPED、ERROR 测试 |
| 限额准确性 | Decimal、等额边界、负剩余、缺用量、币种冲突、单笔与累计区分 |
| AI 接入及降级 | 兼容模型的意图合同、错误/无效输出/非 HTTPS 回退测试；无真实供应商调用 |
| 网页完整交互 | 浏览器手动选案例、发送、当前额度、场景切换、搜索、本体弹窗 |
| 响应式 | 1440×1000 和 390×844；手机 scrollWidth/clientWidth 均为 390 |
| 可移植与待补说明 | README、INTERNAL_MIGRATION.md 的 D01–D16 及替换合同 |

## Browser Evidence
- 桌面历史诊断显示日限额 1000、用量 700、剩余 300；当前独立快照剩余 150。
- 手机通过手工输入询问缺少历史证据的案例，显示 INFERRED 和缺失证据；无横向溢出。
- 本体目录实际显示四层、七类别、六限额与类层级。
- 观测到的浏览器 error/warn 日志为空。
- 截图：artifacts/desktop.jpg、artifacts/mobile.jpg。

## Fixes Applied
测试先行修正当前/历史额度混用、PASS 归因、ERROR 确定性、无历史快照金额和当前视图沿用历史 FAIL 等问题。修正中屏幕侧栏高度。

## Residual Risks
- 全部业务数据、授权归属和策略均为模拟；固定时间并非系统实时状态。
- 默认不是大模型，自然语言能力有限；可选模型仅做意图分类，未与真实供应商联调。
- JSON 类图不是完整 OWL 推理；SHACL 仅提供起步约束，未在默认请求执行。
- 无生产认证、数据库、完整披露政策、实际银行写操作或生产 HTTP 服务。内部迁移按手册补齐。
- 真实银行适配器需严格规范化与错误合同；不能把当前 fixture schema 当完整生产协议。

## Follow-ups
补齐 D01–D16；接内部授权只读工具；回放脱敏历史数据；实现正式披露视图与模型网关；按内部部署规范上线。
