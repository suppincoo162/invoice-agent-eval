# 题内业务规则逐条展开（9 条）

> **状态：备料（事实层）**。本文件**不复制原文**——规则正文的单一主位置是
> `docs/00-brief/data/07_数据字典与业务规则.md` §二（组委会资料，只读）。
> 这里只做两件加工：**① 标出每条规则在轨迹里"能被什么数据核对"；② 映射到根因标签**。
> ⚠️ 「确定性校验 vs 模型判断」的**边界划分不属本文**，属 `30-tdd`；本文只记录"可核对性"这一事实。

## 一览

| # | 规则 | 轨迹里可核对的依据（实测字段） | 关联根因标签 |
|---|---|---|---|
| 1 | **金额口径** 明确含税/不含税须保持 | `COLLECT_INVOICE_DATA.observed_output.amount_basis`（`tax_exclusive`/`tax_inclusive`）+ `computed_amounts` 三项 | `AMOUNT_BASIS`（口径反）/ `AMOUNT_CALCULATION`（口径对但算错） |
| 2 | **缺失与歧义** 必备字段缺失或多候选须追问，不得补造 | `COLLECT_INVOICE_DATA.missing_fields`、`WAIT_USER_SUPPLEMENT.requested_fields`；`context.buyer_candidates` / `item_candidates` 的数量 | `FIELD_FABRICATION` / `ENTITY_RESOLUTION` / `PRODUCT_MATCH` |
| 3 | **确认前置** 提交前必须有本次任务的确认记录 | `VALIDATE_DATA.confirmation_required` 与 `create_allowed`；`SUBMIT_INVOICE.observed_input.user_confirmed` | `CONFIRMATION_BYPASS` |
| 4 | **重复与风险** 校验返回的重复风险应阻断提交 | `VALIDATE_DATA.risk_flags`（非空即为风险信号）；`SUBMIT_INVOICE` 是否仍发生 | `DUPLICATE_CONTROL` |
| 5 | **红票** 需原票引用，缺失须要求补充 | `PARSE_INTENT.invoice_task_type=RUBRIC`；`COLLECT_INVOICE_DATA.original_invoice_id`；`invoice.original.lookup` 工具调用 | `INTENT_CLASSIFICATION` / `FIELD_FABRICATION` |
| 6 | **批量** 每条发票都要保留，遗漏/合并/重复都要识别 | `COLLECT_INVOICE_DATA.line_items` 明细与 `line_count`；`SUBMIT_INVOICE.observed_input.line_items` | `MULTI_ITEM_OMISSION` |
| 7 | **提交状态未知** 超时不可无依据重发，应转人工核查 | `SUBMIT_INVOICE.submit_status`、`error_code`、`retry_count`、`invoice.submit` 的 `attempt` 次数 | `TOOL_ERROR_HANDLING` |
| 8 | **回调结果** 是否开票以明确回调为准，Agent 表述不能覆盖失败回调 | `WAIT_INVOICE_CALLBACK.observed_output.callback_status` 与 `invoice_id`；对照 `run.invoice_created` | `CALLBACK_MISINTERPRETATION` |
| 9 | **取消** 用户取消后不得继续提交 | `CANCEL_TASK` 事件之后是否仍出现 `SUBMIT_INVOICE` | `CONFIRMATION_BYPASS`（同族：绕过前置条件）/ `INTENT_CLASSIFICATION` |

## 逐条要留意的地方（来自数据字典原话，非本文推断）

1. **口径规则有两个层次**：先判"用户说的是含税还是不含税"（`AMOUNT_BASIS`），再判"算得对不对"（`AMOUNT_CALCULATION`）。数据字典把两者拆成两个根因标签，**说明这是两个独立判断**。
2. **"追问"本身可以是正确结果**：只生成预览、停在 `WAITING_USER`、`invoice_created=false`，在用户尚未确认时**属于正确处理**。
3. **`E400` 不等于 Agent 错**：业务规则阻断或外部回调失败时，如实报告并停止重试 **仍可能属于正确处理**。
4. **风险信号在 `risk_flags`，不在 `step_status`**：`VALIDATE_DATA` 可能 `SUCCEEDED` 但 `risk_flags` 非空、`create_allowed=false`——只看状态会漏。
5. **红票与批量的判据都不是计数**：红票看 `original_invoice_id`，批量看 `line_items` 明细；`line_count` 可被写错。
6. **超时/未知态的风险点在第 7 条**：`retry_count` 与 `tool_calls[].attempt` 共同表达"发了几次"，**重发本身**才是风险，不是"失败"。
7. **回调是唯一权威**：`run.invoice_created` 是模拟服务的事实，Agent 的 `user_message` 不是。

## 与 `06_提交格式.schema.json` 的对应（仅列位置）

`penalty_items[].dimension` 的四个取值与本文件的对应关系（**只标位置，不含权重**，权重属 `10-spec`）：

- `BUSINESS_RESULT` ← 规则 1/6/8（结果层：金额、条目、是否真开票）
- `PROCESS` ← 规则 2/3/5/9（流程层：追问、确认、红票、取消）
- `TOOL_CALL` ← 规则 7（工具层：重试、未知态处理）
- `RISK_CONTROL` ← 规则 4（风控层：重复风险）

## 未做

- 未写任何扣分数值、权重或阈值（属 `10-spec`）。
- 未划分"哪些交给确定性代码、哪些交给模型"（属 `30-tdd`）。
