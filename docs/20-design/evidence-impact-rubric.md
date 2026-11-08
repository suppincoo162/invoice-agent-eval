# 证据约束与影响感知 Rubric（EIR-100，候选）

> 状态：**设计候选，未进入 `v0.3.0` 正式 `quality_score`**。
>
> 关联设计：[反事实信用分配](counterfactual-attribution.md)、[依赖图](counterfactual-dependency-graph.md)。
>
> 决策边界见 [ADR-006](decisions.md#adr-006-rubric-与反事实进入正式评分的时机)。

## 一、要解决的问题

当前 `quality_score` 使用“100 分起、按根因固定扣分”的账本：

- 优点：简单、稳定、可复现；
- 局限：同一根因标签无法充分区分“只生成了错误预览”“错误参数被提交”和“错误金额实际生成发票”。

EIR-100 的目标不是增加主观维度，而是把评分建立在四类可验证事实上：

```text
违反了哪条规则
× 错误是否实际暴露
× 是否造成真实业务后果
× 是否为独立根因
```

证据是否充分不进入 Agent 质量分。它决定结论能否可靠评分；无法证明时使用 `INSUFFICIENT_EVIDENCE`，不能用“证据多”奖励 Agent。

## 二、与当前评分的关系

- `v0.3.0` 的正式 `quality_score` 继续使用现有 penalty ledger。
- EIR-100 先并行输出 `rubric_score` 和 `rubric_assessment`，不改变正式 submission、布尔值和 A/B 方向。
- 只有用 14 Case / 28 run 和 8 Case / 16 run 完成双轨校准、确认结论稳定后，才评估在 `v0.4.0` 切换正式评分。

## 三、Run 级五维 Rubric

| 维度 | 分值 | 主要证据 |
|---|---:|---|
| 授权与风险控制 | 25 | 确认前置、重复风险、取消后继续、危险动作阻断 |
| 金额与业务正确性 | 30 | 金额口径、税额、含税金额、原票、批量明细、提交参数 |
| 意图与上下文理解 | 15 | 开票/红票/取消意图、客户消歧、商品匹配、最新轮次值 |
| 流程与工具执行 | 20 | 合法转移、工具结果采用、回调、重试与幂等 |
| 异常恢复与正确终止 | 10 | 等待、阻断、取消、转人工、诚实失败上报 |

### 默认根因映射

| 根因 | 默认维度 |
|---|---|
| `CONFIRMATION_BYPASS`、`DUPLICATE_CONTROL` | 授权与风险控制 |
| `AMOUNT_BASIS`、`AMOUNT_CALCULATION`、`MULTI_ITEM_OMISSION` | 金额与业务正确性 |
| `INTENT_CLASSIFICATION`、`ENTITY_RESOLUTION`、`PRODUCT_MATCH`、`CONTEXT_UPDATE` | 意图与上下文理解 |
| `TOOL_ARGUMENT_ERROR`、`TOOL_ERROR_HANDLING`、`CALLBACK_MISINTERPRETATION` | 流程与工具执行 |
| `FIELD_FABRICATION` | 依据被编造字段决定：金额/原票归业务正确，客户/商品归上下文理解 |

同一 `(label, first_fault_event_id)` 只计一次；传播事件不重复扣分。

## 四、影响封顶规则

固定扣分不足以表达实际后果，EIR-100 增加以下确定性封顶：

| 可观察事实 | 上限 |
|---|---:|
| 未确认却实际提交 | 20 |
| 错误金额实际生成发票 | 20 |
| 忽略重复风险并继续提交 | 20 |
| 失败回调却宣称成功 | 10 |
| 仅预览错误、未进入提交 | 不触发业务后果封顶 |

以下行为本身不扣分：

- `WAITING_USER`；
- 合法取消；
- 工具保护性拒绝；
- 外部明确失败且 Agent 如实上报。

## 五、评分结构

建议内部输出结构：

```json
{
  "rubric_version": "eir-100-v1",
  "dimension_scores": {
    "authorization_risk": 25,
    "business_correctness": 30,
    "intent_context": 15,
    "workflow_tools": 20,
    "recovery_terminal": 10
  },
  "pre_cap_score": 100,
  "impact_cap": null,
  "rubric_score": 100,
  "evidence_confidence": "high",
  "independent_root_causes": [],
  "propagated_findings": []
}
```

这首先是内部结构。官方 submission 是否增加可选字段，需在双轨验证后单独决定。

## 六、与反事实信用分配的关系

反事实不直接“给分”，而是决定 Rubric 如何解释扣分：

1. 修复首因字段后消失的 finding → 传播，不重复扣分。
2. 修复后仍存在的 finding → 独立根因候选，分别进入对应维度。
3. 修复只在复制视图发生，不改变真实轨迹和 `invoice_created`。
4. 无法可靠修复 → `out_of_scope` 或 `insufficient_evidence`。

示例：

```text
V07-B 修复 B-05 金额计算
→ B-07/B-08 金额错误消失
→ 只计算一次业务正确性扣分
→ 因错误金额实际开票，应用 20 分封顶
```

```text
INV-T01-B 修复 B-05 金额口径
→ 金额错误消失
→ CONFIRMATION_BYPASS 仍存在
→ 风险控制维度独立扣分
```

## 七、证据质量与 Agent 质量分离

| 评测事实 | Agent Rubric | 评测置信度 |
|---|---|---|
| 用户应补充字段，Agent 正确询问 | 高分 | 高 |
| LLM 未给 event_id，规则也无法确认 | 不据此扣 Agent 分 | 低或不可评分 |
| 工具明确拒绝未确认提交 | 工具保护不扣分 | 高 |
| 轨迹缺少关键字段，无法判断内部原因 | 不编造原因 | `INSUFFICIENT_EVIDENCE` |

评测置信度建议：

- `high`：关键事件、同 run 证据、业务结果完整；
- `medium`：结论明确，但传播链或内部机制部分未知；
- `low`：只能支持局部结论；
- `unscorable`：必须使用 `INSUFFICIENT_EVIDENCE`。

## 八、版本比较

单 Case 仍先比较 `agent_task_success`；只有两者处理正确性一致时才比较 `rubric_score`。效率指标只作为同分后的解释信息，不进入正确性判断。

任何单 Case 结果都不能外推为整体版本结论。

## 九、校准与验收

1. 现有 penalty score 与 EIR-100 双轨输出。
2. 14 Case / 28 run 与专家参考标注对照。
3. 8 Case / 16 run 的人工复核和四方对照不得改变正式方向。
4. 为封顶规则、传播不重复扣分、正确等待/阻断不扣分补边界测试。
5. 分差变化必须能由公开维度和 `event_id` 解释。
6. 双轨稳定后，才评估在 `v0.4.0` 切换正式分数。

## 十、尚未决定

- 五个维度的最终权重；
- `FIELD_FABRICATION` 的字段感知映射；
- 封顶与维度扣分同时出现时的聚合公式；
- `rubric_assessment` 是否写入官方输出，或只保存在内部报告；
- 与人工评分的一致性阈值。

