# Four Layers Implementation Plan
Goal: 配置与执行分离，无网络依赖运行。
Spec: 00-requirements.md
Architecture: ConfigBundle校验→BankMapper→RuleEngine与DiagnosisEngine→DisclosurePolicy→Presenter；service仅编排。
- [x] 先写 test_layers.py：字段/枚举转换、未知值拒绝、表规则编辑影响判断、模板编辑不影响事实、非法引用拒绝、旧43测试保持。
- [x] 创建 mappings/*.json（规范化/旧系统模拟两种profile）、rules/diagnosis.json（基础与限额决策表）、policies/disclosure.json、templates/zh-CN.json，清理本体指引文案。
- [x] 实现 mapping.py、configuration.py、rules.py、diagnosis.py、disclosure.py、presentation.py；重写适配器/service并接通conversation。
- [x] 验证配置、全部单测与HTTP、实际浏览器、压缩包异目录测试；更新README/迁移文档/四层说明与审查报告。
Review focus: 未知枚举不得默认正常；条件未知不得匹配为false；受限规则不eval；冲突不能被额度分支覆盖；模板缺失启动失败；当前不复用历史证据。
Verification: python3 -m unittest discover -s tests -v；python3 tools/validate_config.py；python3 tools/export_ontology.py；本地HTTP与浏览器。
