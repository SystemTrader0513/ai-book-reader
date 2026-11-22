# Acceptance Report

## Verdict
PASS_WITH_NOTES：四层拆分的本地模拟工程通过；不代表真实银行集成、模型供应商或生产环境已验收。

## Reviews
计划内联审查；最终独立只读代码审查。两项IMPORTANT均修复且复查通过：风险已排除结论保留；映射规范化枚举完整校验。没有未解决BLOCKER/IMPORTANT。

## Verification
- `python3 -m unittest discover -s tests -v`：62项全部通过，含原43项。输出artifacts/test-results.txt。
- `python3 tools/validate_config.py`：57次标准案例意图回放与1次旧系统映射通过。输出artifacts/config-validation.txt。
- `PYTHONPYCACHEPREFIX=/tmp/trace-bot-pycache python3 -m compileall -q app tools tests`：通过。系统默认缓存目录无写权限，使用临时目录而非提升系统权限。
- 本机8765实际启动、浏览器选案例及历史/当前查询通过；历史剩余300，当前150；结构化结果含五配置版本；console无error/warn。
- 压缩包在独立临时目录中全部62项测试与配置回放通过，详见artifacts/portability-tests.txt。
- 打包：tools/package.py显式包含新增mappings/rules/policies/templates，不包含.env、Git和缓存。

## Coverage
| 要求 | 实现与证据 |
|---|---|
| 领域本体保持纯语义 | actions仅id/applies_to；对应测试与TTL同步 |
| 映射可独立修改 | 字段/枚举/版本化响应码profile；改C映射影响控制层级；未知目标值拒绝 |
| 规则可独立修改 | FIRST_MATCH决策表；改certainty影响诊断；非法操作符/事实引用拒绝；无eval |
| 话术独立 | messages/actions/response模板；只改文案不改金额/确定性；缺失模板与不适用占位符拒绝 |
| 披露独立 | FULL/GENERIC/SILENT；风险源字段白名单隔离；已排除角色不被改写；SILENT隐藏标识 |
| 证据语义保留 | 原历史/当前、缺失、冲突、SKIPPED、ERROR、PASS、币种与十进制测试 |
| 可运行网页 | 本机浏览器实际验证并保存workbench.jpg |
| 可迁移 | FOUR_LAYER_DESIGN、INTERNAL_MIGRATION、版本追踪、打包工具及解压回归 |

## Remaining Limits
- 配置是受信发布文件；未实现热更新和生产审批。修改后须校验、回归并重启。
- 新规则只能组合已有可信事实；新事实或数值运算仍需Python/银行工具实现。未重建真实银行授权引擎。
- 七类/四层/六限额的内部定义和优先规则仍按迁移手册D01–D16补齐。
- 默认为MOCK、只读、轻量类图；无生产认证、完整OWL推理和真实供应商联调。
- 模板统一了后端业务解释，前端UI标签仍在static中；仅提供中文。
