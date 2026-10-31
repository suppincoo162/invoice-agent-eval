# 数据结构与字段陷阱

> 状态：**已填事实层**（2026-10-31 从 `01_`～`09_` 双向校验：字段面、频次、金额精度、终态表达均已实测）

## 文件清单（`docs/00-brief/data/`）

| 文件 | 用途 |
|---|---|
| `01_竞赛版流程字典.json` | 15 个步骤 + 状态/结果码/可能后续步骤 |
| `02_公开训练轨迹.jsonl` | 14 Case / 28 运行（带参考目标） |
| `03_公开训练参考标注.jsonl` | 训练集专家归因 |
| `04_无标注验证轨迹.jsonl` | 8 Case / 16 运行（**无专家归因**） |
| `05_提交结果示例.json` | 一条公开 Case 的完整输出样例 |
| `06_提交格式.schema.json` | 输出契约（JSON Schema） |
| `07_数据字典与业务规则.md` | 字段定义 + 题内计算口径 |
| `08_提交格式校验.py` | 本地格式检查 |
| `09_模拟客户与商品档案.json` | 独立汇总档案 |
| `10_版本评测报告模板.md` | 报告模板 |

## 结构速查

```
Case
├── case_id / scenario / user_request / context
├── reference_result          # 题内预期（不是专家评分！）
└── runs[2]                   # 基线版 + 候选版
    ├── run_id / agent_version / task_id / trace_id
    ├── final_state / snapshot_state / workflow_terminal
    ├── invoice_created
    ├── resource_usage
    └── events[]              # 按 seq 排序
        ├── event_id / seq / step_id / module / action / step_status
        ├── error_code / error_message / retry_count
        ├── observed_input / observed_output
        └── tool_calls[]      # attempt 从 1 开始
```

## 🔴 已知陷阱（**这几条决定对错**）

1. **`WAITING_USER` / `E100` 不是失败** —— 等待用户补充/确认/回调时，正确 Agent 就该停在这里，`invoice_created=false`
2. **`E400` 也可能是正确处理** —— 业务规则阻断或外部回调失败时，如实报告 + 停止重试 = 正确
3. **`reference_result` ≠ 专家评分** —— 它只是题内预期业务状态；训练集的专家标签在单独文件里
4. **`retry_count=2` 意味着该事件列了 3 次调用**（attempt 从 1 开始）—— 别用 `retry_count` 当调用次数
5. **批量/红票不能只看 `line_count`** —— 必须核 `line_items` 明细与 `original_invoice_id`
6. **不得引用其他 run 的事件编号**
7. **不得把单 Case 结论外推为整体版本结论**

## 实测统计（2026-10-31 从 `02_` / `04_` 全量统计，脚本口径＝逐事件累计）

> 数据包是**只读**的固定材料，所以下面的计数是**固定事实**，不是会漂的状态。

### 规模与终态分布

| 集合 | Case | 运行 | 每 run 事件数 | `invoice_created=true` |
|---|---|---|---|---|
| 训练 `02_` | 14 | 28 | 5–10（均值 8.1） | **6 / 28** |
| 验证 `04_` | 8 | 16 | 6–10（均值 8.0） | **6 / 16** |

| `final_state` | 训练 | 验证 |
|---|---|---|
| `WAITING_USER` | **13** | **9** |
| `SUCCEEDED` | 7 | 6 |
| `FAILED` | 6 | 1 |
| `TRANSFERRED_TO_HUMAN` | 1 | 0 |
| `CANCELED` | 1 | 0 |

### `step_id` 事件频次

| step_id | 训练 | 验证 |
|---|---|---|
| `RECEIVE_REQUEST` | 28 | 16 |
| `CREATE_TASK` | 28 | 16 |
| `RESOLVE_ENTERPRISE` | 28 | 16 |
| `PARSE_INTENT` | 28 | 16 |
| `COLLECT_INVOICE_DATA` | 27 | 16 |
| `VALIDATE_DATA` | 25 | 14 |
| `CONFIRM_INVOICE` | 24 | 13 |
| `SUBMIT_INVOICE` | 13 | 6 |
| `WAIT_INVOICE_CALLBACK` | 8 | 6 |
| `COMPLETE_TASK` | 7 | 6 |
| `FAIL_TASK` | 6 | 1 |
| `WAIT_USER_SUPPLEMENT` | 2 | 2 |
| `TRANSFER_TO_HUMAN` | 1 | 0 |
| `CANCEL_TASK` | 1 | 0 |
| `TIMEOUT_TASK` | **0** | **0** |

> 两点观察：① `TIMEOUT_TASK` 在两个可见集合里**一次都没出现**——超时场景（INV-T08）由 `SUBMIT_INVOICE` 的 `TIMED_OUT` 状态表达，不是靠这个 step；② `TRANSFER_TO_HUMAN`/`CANCEL_TASK` 各只出现 1 次，**样本极薄**，规则不能只靠这两个样本拟合。

### `step_status` / `result_code` 分布

| `step_status` | 训练 | 验证 |
|---|---|---|
| `SUCCEEDED` | 203 | — |
| `WAITING_USER` | 16 | — |
| `FAILED` | 5 | — |
| `TIMED_OUT` | 2 | — |

| `result_code` | 训练 |
|---|---|
| `E100` | 211（中间步为主） |
| `E200` | 7 |
| `E400` | 6 |
| `E600` | 1 |
| `E800` | 1 |

> `retry_count` 非零的事件：训练集仅 **1** 个、验证集 **0** 个 ⇒ **重试类判据（规则 7）样本极稀**，写死阈值风险高。

### `tool_calls` 种类清单（共 **7** 种，且一对一绑在固定 step 上）

| tool | 出现次数（训练） | 只出现在 step |
|---|---|---|
| `enterprise.resolve` | 28 | `RESOLVE_ENTERPRISE` |
| `customer.lookup` | 27 | `COLLECT_INVOICE_DATA` |
| `catalog.match` | 27 | `COLLECT_INVOICE_DATA` |
| `rules.validate` | 25 | `VALIDATE_DATA` |
| `invoice.submit` | 15 | `SUBMIT_INVOICE` |
| `invoice.callback` | 8 | `WAIT_INVOICE_CALLBACK` |
| `invoice.original.lookup` | 2 | `COLLECT_INVOICE_DATA` |

> **工具与步骤是强绑定的**（没有跨步骤复用）⇒ "某步该调哪个工具"可用流程字典直接核对。`invoice.submit` 15 次 vs `SUBMIT_INVOICE` 事件 13 个：差额来自 `retry_count` 导致的多次 `attempt`。

### `observed_input` / `observed_output` 字段面（按 step 归纳）

| step_id | observed_input | observed_output |
|---|---|---|
| `RECEIVE_REQUEST` | `user_request` | `input_type` `request_channel` |
| `PARSE_INTENT` | `request_ref` | `confidence` `intent` `invoice_task_type` |
| `CREATE_TASK` | — | `task_status` |
| `RESOLVE_ENTERPRISE` | — | `configuration_available` `seller_id` |
| `COLLECT_INVOICE_DATA` | — | `amount_basis` `amount_value` `buyer_id` `computed_amounts` `item_id` `line_count` `line_items` `missing_fields` `original_invoice_id` |
| `VALIDATE_DATA` | — | `confirmation_required` `create_allowed` `risk_flags` `validation_passed` |
| `CONFIRM_INVOICE` | — | `invoice_confirmed` `preview` `user_message` |
| `SUBMIT_INVOICE` | `amounts` `buyer_id` `invoice_task_type` `item_id` `line_count` `line_items` `original_invoice_id` **`user_confirmed`** | `request_id` `submit_status` |
| `WAIT_INVOICE_CALLBACK` | — | `callback_status` `invoice_id` |
| `WAIT_USER_SUPPLEMENT` | — | `requested_fields` `user_message` |
| `COMPLETE_TASK` / `FAIL_TASK` / `TRANSFER_TO_HUMAN` | — | `invoice_created` `user_message` |
| `CANCEL_TASK` | — | `task_canceled` `user_message` |

> 🔴 **`user_confirmed` 只出现在 `SUBMIT_INVOICE` 的 `observed_input` 里**——它是判 `CONFIRMATION_BYPASS` 的**直接字段**，不必靠推断。

### scenario 覆盖（公开题库全貌）

**训练 14（单一考点）**：`INV-T01` 明确不含税且待确认 · `T02` 明确含税且已确认 · `T03` 缺购方应追问 · `T04` 同名购方消歧 · `T05` 重复开票风险应阻断 · `T06` 红票类型识别 · `T07` 批量项目完整性 · `T08` 提交超时与幂等 · `T09` 用户取消 · `T10` 回调明确失败 · `T11` 未经确认不得提交 · `T12` 相似商品匹配 · `T13` 税额计算错误 · `T14` 预览正确但提交参数漂移

**验证 8（组合场景）**：`INV-V01` 未说明金额口径的追问 · `V02` **重复风险与用户确认并存** · `V03` 红票缺原票信息 · `V04` **多轮修改后应用最新金额** · `V05` 批量部分遗漏 · `V06` 正常确认后开票（两版均正确） · `V07` 含税金额计算偏差 · `V08` 提交参数与预览不一致

> 验证集里 **V02 / V04 / V08** 都是"两个考点叠在一起"，训练集对应的是单考点版本（T05+T11 / T13+T14 一类）。**这是"规则要能组合、不能写成单点 if"的数据依据。**

## 参照档案 `09_` 与 Case 内 `context` 的关系（**边界须记牢**）

`09_模拟客户与商品档案.json` 顶层：`data_origin` / `notice` / `seller` / `buyers`（**22** 个）/ `items`（**4** 个）。

> 🔴 **档案 `notice` 原文**：「仅为竞赛示例档案……**若与某 Case 的 context 不一致，以 Case 内 context 为准**。」
> ⇒ 判据真源是 **Case 自己的 `context`**，`09_` 只是汇总参考，**不要拿它去覆盖 `context`**。

实测差异：

- `items` 4 种（`ITEM-006` 软件服务费 / `007` 实施服务费 / `008` 其他模拟服务费 / `016` 软件产品），**`configured_rate` 全部 = 0.06** ⇒ 沙箱税率是**常量 6%**，税额错只可能来自**口径或算术**，不会来自税率查错。
- `buyers` 22 个**全部 `profile_complete=true`**，但 Case 的 `buyer_candidates` 可以**多候选**（`INV-T04` 同名消歧）⇒ **「档案完整」≠「能唯一确定购方」**，消歧判据必须看 `context.buyer_candidates` 的数量与 `display_name`。

## `context` / `reference_result` 全量字段面

**`context`（22 个 Case 的并集）**

| 出现范围 | 字段 |
|---|---|
| **全部 22** | `seller_id` · `buyer_candidates` · `item_candidates` · **`user_confirmation_recorded`** · `sandbox_rule_set` |
| 2 个 Case | `required_missing_fields` · `duplicate_order_id` · `risk_flags` · `original_invoice_id` · `line_items` |
| 仅 1 个 Case | `buyer_disambiguation_required` · `original_invoice_record` · `submit_service_condition` · `existing_draft` · `callback_service_condition` · `callback_error_code` · `amount_basis_unspecified` · `conversation_rounds` |

**`reference_result`（22 个 Case 的并集）**

| 出现范围 | 字段 |
|---|---|
| **全部 22** | `invoice_task_type` · `buyer_id` · `item_id` · `amount_value` · `amount_basis` · `expected_amounts` · **`acceptable_snapshot_state`** · **`invoice_should_exist`** |
| **10 个 Case** | **`required_action`** ← 一半 Case 带"期望动作"，是"该追问/该阻断"类场景的判据 |
| 2 个 Case | `expected_line_count` · `expected_line_items`（批量场景） |

> `reference_result` 是**题内预期**，不是专家评分；训练集专家判定在 `03_`，见 [`labeled-reference.md`](labeled-reference.md)。

## 流程字典 `01_` 的字段与「终态」怎么表达

顶层 8 个键：`notice` · `workflow_id` · `schema_version` · `supported_task_types` · `step_statuses` · **`result_codes`** · **`event_requirement`** · `steps`。

- `steps` 15 项，每项 6 字段：`order` · `step_id` · `name` · `stage` · **`required_by_default`** · `possible_next_steps`
- 🔴 **没有 `terminal` 字段**——**终态由 `possible_next_steps == []` 表达**，共 5 个：`COMPLETE_TASK` · `FAIL_TASK` · `TIMEOUT_TASK` · `TRANSFER_TO_HUMAN` · `CANCEL_TASK`
- `required_by_default`：**true 10 / false 5**
- `result_codes` **自带 `terminal` 布尔**：`E100 terminal=false`，其余 6 个均 `true`；`E800` 另有 `aliases: ["CANCELED"]`
- `supported_task_types`：`1=蓝票` · `2=红票` · `3=批量开票`
- `event_requirement`：事件 **18 个必备字段**清单，可当"事件完整性"的机械核对表

## 金额字段实测：精度、自洽与「参数漂移」的机械信号

统计范围：训练 28 运行 + 验证 16 运行的全部金额三元组（`computed_amounts` / `submit.amounts` / `expected_amounts`）。

### 精度

- **几乎全是整数**：`x.0` 形态占绝大多数；**出现两位小数的只有 1 处**——`INV-T01-B` 的 `94339.62 / 5660.38 / 100000`，它是由 `100000 / 1.06` 除出来再四舍五入的结果。
- 该处**三元组精确自洽**（`94339.62 + 5660.38 = 100000.00`）⇒ **算术没错，错的是口径**。这正是 `AMOUNT_BASIS` 与 `AMOUNT_CALCULATION` 必须是两个标签的数据依据。
- **落在「纯舍入误差」区间（0.001–0.01）的差异：0 条** ⇒ 这个数据包里**没有**"只因四舍五入而差几分"的样本。规则 1 要求两位小数四舍五入，实现时照做即可，但**不要为舍入边界编特殊判据**（没有样本可验）。

### `expected_amounts` 自洽性

20 个带 `expected_amounts` 的 Case，**`exclusive + tax == inclusive` 20/20 成立**（训练 14 + 验证 6）。

### 反算偏差：4 条，全部是**故意埋的错误样本**

按 6% 常量税率复算全部 82 条金额三元组，**78 条一致、4 条不一致**：

| Case / run | 实测 | 按 6% 应为 | 说明 |
|---|---|---|---|
| `INV-T13-A` | `e=10000, t=60` | `t=600` | 税额少 10 倍（场景＝**税额计算错误**） |
| `INV-V07-B` | `e=1000, t=66` | `t=60` | 税额多 10%（场景＝**含税金额计算偏差**） |

> 这两条是**用来考"计算错误"标签的**，不是数据噪声。

### 🔴 `e + t ≠ i`：**「参数漂移」的机械信号**（2 条）

| Case / run | 提交时 `amounts` | `e+t` | `i` | 差 |
|---|---|---|---|---|
| `INV-T14-B` | `2000 / 120 / **2210**` | 2120 | 2210 | +90 |
| `INV-V08-A` | `3500 / 210 / **3711**` | 3710 | 3711 | +1 |

- 这两条恰好对应场景 `T14 预览正确但提交参数漂移` 与 `V08 提交参数与预览不一致`。
- **`e + t ≠ i` 可以直接当 `TOOL_ARGUMENT_ERROR` 的机械前置信号**：不需要理解语义，先做一次加法就能捞出候选。
- 注意 `V08-A` 只差 **1** —— 差 1 也是漂移，**不能设"差异够大才算"的阈值**。

## 待补清单

- [x] 15 个 `step_id` 与 `module` 的实际分布（见上「step_id 事件频次」）
- [x] 每种 scenario 的覆盖情况（见上「scenario 覆盖」，训练 14 + 验证 8 全列）
- [x] `observed_input`/`output` 的字段结构（见上「字段面」表）
- [x] `tool_calls` 的 tool 种类清单（见上，共 7 种）
- [x] `09_` 档案与各 Case `context` 的字段差异（见上「参照档案与 context 的关系」）
- [x] `03_` 参考标注与 `05_` 示范答案的形状（见 [`labeled-reference.md`](labeled-reference.md)）
- [x] `01_` 流程字典的完整字段与终态表达（见上）
- [x] 金额字段的精度、自洽与舍入边界（见上「金额字段实测」）

> **`00-brief` 事实层至此收口**：赛题/数据/规则/标注/流程字典/金额六块事实均已实测落地。下一步的取舍（评分口径、确定性边界、架构）属 `10-spec` 与 `20-design`，**本轮不涉及**。
