# 数据结构与字段陷阱

> 状态：**骨架**（待从数据字典 + 实际数据双向校验）

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

## 待补清单

- [x] 15 个 `step_id` 与 `module` 的实际分布（见上「step_id 事件频次」）
- [x] 每种 scenario 的覆盖情况（见上「scenario 覆盖」，训练 14 + 验证 8 全列）
- [x] `observed_input`/`output` 的字段结构（见上「字段面」表）
- [x] `tool_calls` 的 tool 种类清单（见上，共 7 种）
- [ ] `09_模拟客户与商品档案.json` 与各 Case `context` 的字段差异（未开始）
