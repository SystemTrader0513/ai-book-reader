# Implementation log

2026-11-22，原地串行实现，保留原43项测试、模拟案例、网页和原始skill；未提交/发布。

1. 编写test_layers.py，首先观察configuration模块缺失导致失败，再实现独立ConfigBundle、BankMapper和受限RuleEngine。
2. ontology.json actions移除label/instruction；模板收拢业务话术、指引和缺失证据名称。config/policy.json移除，拆为config/runtime.json与policies/disclosure.json。
3. 把service.py中的条件树改为rules/diagnosis.json基础/限额两张有序表。service保留编排，DiagnosisEngine只构造事实及调用规则，DisclosurePolicy先过滤再由Presenter渲染。
4. 原43项 + 初次12项分层测试通过。随后增加响应码线索、上下文占位符、SILENT和冲突回归。
5. 配置映射在每次adapter读取时实际执行，额外源字段不透传；提供legacy-demo profile和raw-bank-example；响应码按模拟网络和版本识别，HINT_ONLY不用于确认主因。
6. 独立只读审查发现两项IMPORTANT：风险PASS被泛化为拒绝原因、规范化目标枚举校验不全。先写失败回归，再修复角色敏感泛化模板与BankMapper构造/运行时枚举域校验。代理复查19项分层测试通过，两项已解决。
7. 浏览器实际选取线上限额案例，历史剩余300与当前150正确分开；结构化结果包含五个配置版本。console error/warn为空；截图artifacts/workbench.jpg。
8. 全部62项测试通过；配置校验回放57次标准案例查询及1次旧系统映射；compileall使用/tmp缓存前缀通过（系统默认缓存目录受限，未修改系统权限）。
9. README、集中迁移手册、FOUR_LAYER_DESIGN说明配置边界、修改示例、重启要求与生产缺口。打包和异目录验证另见验收报告。

10. 加强SILENT回归，确保自然语言也不暴露安全限制类别；改用中性模板。压缩包已在独立目录运行全部62项与配置回放。
