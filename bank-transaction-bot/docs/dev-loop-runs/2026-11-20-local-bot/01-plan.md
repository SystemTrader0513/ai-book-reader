# Local Investigation Bot Implementation Plan

**Goal:** 无密钥、无依赖即可运行，业务与对话隔离。
**Architecture:** 标准库 HTTP 服务；JSON 本体类图与类型目录；模拟银行适配器；Decimal 业务规则；脱敏诊断视图；原生 HTML/CSS/JS。
**Spec:** 00-requirements.md

## Tasks
- [x] 1. 测试先行：定义 diagnose(id, intent) 输出合同，覆盖历史、当前、四层、六限额、七类别、未知/冲突/跳过及风险脱敏。
- [x] 2. 实现 config/ontology.json、config/policy.json、config/scenarios.json 与 app/domain.py、app/service.py。本体父类遍历用于原因分类及候选动作；规则显式计算限额，不做完整 OWL 推理。
- [x] 3. 实现 app/conversation.py 可选兼容 Chat Completions 意图适配，默认本地意图识别；app/server.py 仅 localhost 演示，固定静态文件路径和请求限制。
- [x] 4. static 网页，场景列表、聊天、归因证据、额度展示、本体目录、错误恢复。
- [x] 5. docs/INTERNAL_MIGRATION.md、README.md、启动脚本及验收报告。

## Verification
python3 -m unittest discover -s tests -v；HTTP 集成测试；浏览器实测发送消息、切换、错误反馈和移动布局。
## Review Focus
不能把当前限制说成历史原因；SKIPPED 非 PASS；缺失用量非零；风险内部信息不得进入 API；未知 ID 不泄漏记录；Product 层级与产品配置类别独立。
