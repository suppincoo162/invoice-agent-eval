# 官方参考标注（`03_`）与示范答案（`05_`）的形状

> **状态：备料（事实层）**。本文只记录**官方给了什么形状的答案**，不含我们的评分口径。
> 数据源：`docs/00-brief/data/03_公开训练参考标注.jsonl`（14 行）与 `05_提交结果示例.json`（1 条完整示范）。
> ⚠️ 本文件**只描述训练集**。验证集 `04_` **没有专家标注**，不能拿它当答案。

## 一、`03_` 的结构（每个 Case 一行）

| 字段 | 类型 | 说明 |
|---|---|---|
| `case_id` | string | 14 个训练 Case 全覆盖 |
| `run_assessments[]` | array | 每个 Case **恰好 2 条**（对应 A/B 两次运行） |
| `run_assessments[].run_id` | string | 与 `02_` 轨迹里的 `run_id` 一一对应 |
| `run_assessments[].agent_task_success` | boolean | **官方判定**（不是轨迹里的状态） |
| `run_assessments[].business_invoice_created` | boolean | **官方判定** |
| `run_assessments[].root_causes[]` | array | 每项含 `label` / `first_fault_event_id` / `evidence_event_ids[]` / `explanation` |
| `run_assessments[].reference_snapshot_state` | string | 该 run **应该**处于的快照态（可与实际 `final_state` 不同） |
| `version_direction_on_this_case` | enum | 单 Case 的版本方向 |
| `single_case_caveat` | string | 固定提醒「单个 Case 不能证明整体版本优劣」 |

## 二、`03_` 的分布（全量统计）

**版本方向**：`baseline_better` **8** · `candidate_better` **6** —— **没有** `equal`，也**没有** `insufficient_evidence`。

**两个布尔值的组合分布**（28 条运行）：

| `(agent_task_success, business_invoice_created)` | 条数 |
|---|---|
| `(true, false)` | **11** |
| `(false, false)` | **11** |
| `(false, true)` | **3** |
| `(true, true)` | **3** |

> 🔴 最关键的一条事实：**`(true, false)` 有 11 条、`(false, true)` 只有 3 条**——「做对了但没开票」是**最常见**的组合。这从答案侧再次印证「不能把开票率当成功率」（对应 `AGENTS.md` 硬约束 3）。

**根因密度**：13 个 Case 各 **1** 个根因；**`INV-T01` 独有 2 个**（`AMOUNT_BASIS` + `CONFIRMATION_BYPASS`）⇒ 全训练集合计 **15 个根因实例**。

**根因的必备结构**（15/15 全部满足）：

- **每个根因都有 `first_fault_event_id`**（无 null）
- **每个根因的证据事件恰好 2 条**（min = max = **2**）

> 这两条是**官方答案的固定形状**。我们的输出若给出 1 条证据或 5 条证据，虽然 schema 可能放行，但**与官方形态不同**——这属于 `10-spec` 要不要对齐的口径问题，本文不判。

**用到的标签（12 种 / 共 15 个实例）**：

| 标签 | 次数 | | 标签 | 次数 |
|---|---|---|---|---|
| `AMOUNT_BASIS` | 2 | | `MULTI_ITEM_OMISSION` | 1 |
| `CONFIRMATION_BYPASS` | 2 | | `TOOL_ERROR_HANDLING` | 1 |
| `INTENT_CLASSIFICATION` | 2 | | `CALLBACK_MISINTERPRETATION` | 1 |
| `FIELD_FABRICATION` | 1 | | `PRODUCT_MATCH` | 1 |
| `ENTITY_RESOLUTION` | 1 | | `AMOUNT_CALCULATION` | 1 |
| `DUPLICATE_CONTROL` | 1 | | `TOOL_ARGUMENT_ERROR` | 1 |

> **训练集里一次都没出现的标签：`CONTEXT_UPDATE`**（多轮修改后仍用旧值）。
> 它对应的场景在**验证集** `INV-V04`（多轮修改后应使用最新金额）——而验证集**没有官方标注** ⇒ 这个标签只有"标签定义"，**没有可对照的答案样例**。

## 三、`05_` 示范答案（`INV-T01` 的完整输出）

这是组委会给的**唯一一条完整答案样例**（A 版 = 正确处理，B 版 = 有错），形状如下：

| | A 版（baseline） | B 版（candidate） |
|---|---|---|
| `agent_task_success` | `true` | `false` |
| `business_invoice_created` | `false` | `false` |
| `quality_score` | **100** | **20** |
| `penalty_items` | `[]` | **2 条**：`BUSINESS_RESULT` 扣 **30** ＋ `RISK_CONTROL` 扣 **50** |
| `root_causes` | `[]` | `AMOUNT_BASIS`（`INV-T01-B-05`）＋ `CONFIRMATION_BYPASS`（`INV-T01-B-08`） |
| `evidence_event_ids` | `[A-05, A-07]` | （在 penalty 与 root_causes 内各自带证据） |

`version_comparison` 示例：

```json
{"direction": "baseline_better", "release_recommendation": "defer",
 "reason": "候选版在本Case出现错误金额和确认绕过；这说明局部严重退化，整体版本结论仍需更多Case支持。"}
```

**两条要注意的示范性质**（原文声明，不是我们的推断）：

1. `quality_score` 是**队伍自己设计的**质量分，**不是赛事评分权重**；示例里的 `100 / 20` 只是示范。
2. 扣分数值（30 / 50）**不强制相同**——`06_提交格式.schema.json` 的说明写明「演示口径：100 分起按可证实问题扣分，不强制相同扣分数值」。⇒ **抄分数数值没有意义，要抄的是"扣分必须带证据事件"这个结构**。

## 四、这份材料能校准的三件事

1. **`reference_snapshot_state` 与 `final_state` 是两回事**：官方标注里给的是"应该处于"，轨迹给的是"实际处于"。两者不同才是问题所在。
2. **官方根因也是"一个 Case 多个根因"**（`INV-T01` = 2 个），说明"一次运行只报一个根因"是过窄的写法。
3. **`evidence_event_ids` 是硬结构**：`root_causes[]` 与 `penalty_items[]` 都要求带它，且官方样例每条都给了 2 个 ⇒ 证据链是答案的组成部分，不是附加说明。

## 五、本文件未做

- 未比较"我们的判定"与"官方标注"的差距（那是实现阶段的评估）。
- 未把示范扣分数值当作规范（schema 明说非强制）。
- 未使用验证集做任何对照（它没有标注）。
