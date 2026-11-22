# 四层结构与配置修改指南（2026-11-22）

本轮将原先混在 service.py 的诊断和话术拆开。四层是职责边界，不要求一层仅一个文件。使用 JSON 是为了保持 Python 3.9+ 无必装依赖；语义上对应原参考文档的 mapping.yaml / rules.yaml / templates.yaml。

## 1. 当前目录与执行链路

| 层 | 配置入口 | 执行代码 | 职责 |
|---|---|---|---|
| 领域本体 | config/ontology.json；ontology/card-decline.ttl | domain.OntologyGraph | 类、父类、四层目录、七原因、六限额、动作适用关系 |
| 映射层 | mappings/normalized-demo.json；mappings/legacy-demo.json | mapping.BankMapper；adapters.MockBankAdapter | 白名单字段、枚举、可选响应码线索 → 标准事实 |
| 规则层 | rules/diagnosis.json | rules.RuleEngine；diagnosis.DiagnosisEngine | 基础证据诊断、限额诊断、确定性、因果角色、升级条件 |
| 规则层中的披露策略 | policies/disclosure.json | disclosure.DisclosurePolicy | FULL/GENERIC/SILENT、字段遮盖、允许提供的指引 |
| 表现层 | templates/zh-CN.json；static/ | presentation.Presenter | 话术、缺失证据名称、动作说明、金额拼接和网页 |

config/runtime.json 是运行设置，包含模拟用户、默认映射 profile 和只读标记，不是领域本体。旧 config/policy.json 已移除，避免出现两个策略源。

执行顺序：

```text
用户问题 → 对话编排（本地或可选模型识别意图）
           ↓
BankAdapter → BankMapper → 规范化交易/控制/限额事实
           ↓
本体类型关系 + DiagnosisEngine → RuleEngine 决策表
           ↓
DisclosurePolicy → 获准的消息键、字段、指引 ID
           ↓
Presenter + templates → safe_summary / customer_response
           ↓
网页聊天与诊断面板
```

service.py 只串联以上步骤。不会把原始风险对象提供给模板或模型。回复增加 configuration_versions，可追溯 ontology/mapping/rules/policy/templates 五个版本；银行源 rule_version 与本地 diagnostic_rule_id 分开。

## 2. 领域本体：定义概念和关系

本体中 actions 仅保留 id 与 applies_to。候选指引根据父类关系匹配，例如 DailyOnlinePurchaseLimit → LimitControl → VIEW_LIMIT。具体标签和办理话术在模板，不在本体。

reason_categories 与 limit_types 的中文名称是领域标签，继续留在本体。四层仍是控制实例属性，不是类型继承树。不预设 Entity > Product > Account > Card 的优先顺序。

TTL 从 JSON 导出，并包含动作适用注解；没有引入完整 OWL 推理机，也未默认执行 SHACL。

## 3. 映射层：真实执行的配置

normalized-demo 是现有19个案例的显式同名映射，适配器每次读取都经过映射，而非直接透传。legacy-demo 展示不同系统字段和枚举如何转换；config/raw-bank-example.json 是完全模拟的输入，不是任何银行接口定义。

字段示例：

```json
{
  "type": {"source": "kindCode", "required": true, "enum": "types"},
  "level": {"source": "layerCode", "required": true, "enum": "levels"}
}
```

同一 profile 的枚举示例：

```json
{
  "types": {"DOP": "DailyOnlinePurchaseLimit"},
  "levels": {"C": "CARD"},
  "evaluations": {"REJECT": "FAIL"}
}
```

每个字段的 source 可以是用点分隔的嵌套路径；只读路径，不支持 Python 表达式。collections 定义控制数组、历史限额、当前限额的位置。required 字段缺失报错，optional 可配置默认值。当前状态缺失的默认值为 null，不是 false 或正常。

只输出声明过的字段；raw_secret、风险分数和内部阈值等额外源字段不会透传。配置值和有效值与用量仍分开；金额必须是可接受的有限非负十进制数。未知控制类型/层级/评估枚举会报 MappingError，不由模型猜测。

响应码映射按“网络@版本:码”限定范围。示例 DEMO_NETWORK@1:61 → LIMIT_RELATED / HINT_ONLY 仅用于演示版本化映射，**不声称真实61在所有网络中的含义**。未知网络/版本返回 UNMAPPED；即使存在限额线索，缺少实际评估记录时仍 UNKNOWN，不能推出具体限额、控制ID或主因。

直接运行旧系统模拟输入：

```python
from app.configuration import ConfigBundle
from app.adapters import MockBankAdapter
from app.service import InvestigationService
b = ConfigBundle()
a = MockBankAdapter(records=[b.read('config/raw-bank-example.json')],
                    mapping=b.read('mappings/legacy-demo.json'), bundle=b)
result = InvestigationService(adapter=a, bundle=b).diagnose('online-card')
```

这会使用 legacy profile 走完全部诊断层，无需修改业务代码。

## 4. 规则层：有序决策表

rules/diagnosis.json 的两个表均采用 FIRST_MATCH，按文件顺序取第一条匹配规则，最后必须有 always 回退。顺序是诊断证据的处理顺序，不是银行四层控制的授权执行优先级。

base 表处理：冲突 → 当前状态缺失/有效/解除 → 历史PASS → ERROR → SKIPPED → 有直接历史证据的FAIL → 当前候选 → 未知。

limit 表处理：保留冲突 → 缺少相应时间快照 → 当前证据不足 → 用量或币种不可算 → 当前额度 → 计算与决策冲突 → 已确认单笔/累计超限 → 保留基础判断。

示例：

```json
{
  "id": "historical-fail",
  "when": {"all": [
    {"fact": "evaluation", "eq": "FAIL"},
    {"fact": "historical_snapshot", "eq": true},
    {"fact": "has_evidence", "eq": true},
    {"fact": "effective_at_transaction", "eq": true}
  ]},
  "set": {
    "certainty": "CONFIRMED",
    "causal_role": {"fact": "recorded_role"},
    "message_key": "recorded",
    "missing_evidence_keys": []
  }
}
```

可用条件只有 all、any、always、fact+eq、fact+in。值比较区分类型，true 不等于数字1。可赋值字段只有 certainty、causal_role、message_key、missing_evidence_keys。唯一动态赋值为 recorded_role。没有 eval、exec、自由 SPARQL、SQL 或任意工具执行。

上下文字段与语义在 app/rules.py 的 FACT_NAMES 和 diagnosis.py 中定义。新增业务类型可复用现有表；新增规则条件若需要新的事实，必须在代码中实现可信事实构造并补测试，不能只编造一个名字写进JSON。

Decimal加法、金额单位和事实构造仍由 Python 确定性函数执行，不是把所有计算逻辑都变成字符串。真实银行的授权规则、额度共享、例外和优先依旧应由内部业务工具提供，本决策表主要解释其证据。

## 5. 披露策略：先过滤，再表现

policies/disclosure.json 对原因类别显式选择 FULL/GENERIC/SILENT。未知类别默认 GENERIC。

- FULL：保留白名单诊断字段及候选指引。
- GENERIC：改用泛化消息键，移除数值限额字段，遮盖指定标识，只提供策略允许的指引。
- SILENT：移除原因类别、层级、控制标识和证据，返回安全的泛化说明与获准联系指引。

策略只引用模板键，不包含中文话术；模板不决定披露等级。当前仍是演示披露矩阵，正式版必须按银行政策验证控制存在性、调试标识、层级与身份权限。修改配置需要可信发布与评审，不交给用户或模型修改。

## 6. 表现层：改文案不改事实

templates/zh-CN.json 包含 messages、evidence_labels、actions、response。规则输出的是 message_key；Presenter 将已过滤事实渲染成中文。前端布局及界面标签保留在 static/，并非把所有UI文字迁入服务端模板。

例如仅修改：

```json
"limit_daily_exceeded": "这笔交易超过当时剩余的{limit_label}，请核对可用额度。"
```

即可改变回复和 safe_summary，不改变 certainty 或金额。基于规则、政策的模板引用在启动时检查；未知占位符、不适用的基础消息占位符会被拒绝。当前只提供中文一套模板，不宣称已实现多语言选择。

## 7. 修改与验证流程

1. 按对应层编辑配置，并更新各自version。
2. 执行 `python3 tools/validate_config.py`：检查跨层引用，并回放19个案例的三种意图和旧系统模拟映射。
3. 执行 `python3 -m unittest discover -s tests -v`。
4. 重启服务。配置在启动时加载，不是热更新。
5. 查看返回的 configuration_versions 与 diagnostic_rule_id，核对实际生效版本。
6. 执行 `python3 tools/export_ontology.py` 同步TTL（本体变化时）。
7. 执行 `python3 tools/package.py` 重新生成 dist/trace-card-bot.zip。

内部定义缺口仍见 INTERNAL_MIGRATION.md 的 D01–D16。字段映射扩展不等于已经完成真实银行认证、数据访问或生产部署。
