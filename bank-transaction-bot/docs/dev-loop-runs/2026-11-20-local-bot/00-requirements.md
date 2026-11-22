# Requirements Baseline

## Goal
交付 Python 3.9+ 可运行的本地网页交易拒绝排查工程，无第三方必装依赖。
## User-visible Behavior
模拟场景选择、聊天排查、四层归因、七类原因、六类限额、证据与确定性、当前和历史状态区别、下一步指引。
## Acceptance Criteria
启动命令成功；HTTP 页面和 API 可用；核心业务及负面测试通过；浏览器实测；迁移文档列出未确认定义、接口合同和生产差距。
## Constraints
用户授权根据已知信息完成工程并记录不确定项；保留原始 skill；不提交 Git、不部署、不访问真实银行数据。
## Assumptions
Entity 暂作独立主体；七类以列举为准；线上/线下日限额拆成两类；AMT 按 ATM；所有数据和规则均为模拟。
## Open Questions
内部定义不阻碍演示，集中进入 docs/INTERNAL_MIGRATION.md。
## Non-goals
真实银行权限、资金操作、完整 OWL DL 推理、生产部署认证。
## Repo Context
main 无提交；仅已有 card-transaction-investigation 与 .DS_Store，不改动。本轮原地串行开发；计划内联审查，最终额外派只读代码审查代理。
