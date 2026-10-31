# 手工复现：INV-T01（明确不含税金额且尚待确认）

> **状态：备料（事实层）**。这是工程原则 2「**先取事实再对齐**」的动作——把一条真实 Case 手工走通，
> 而不是先写通用规则。本文件**只记录数据里发生了什么**，**不含评分口径与扣分权重**（属 `10-spec`）。
> 数据源：`docs/00-brief/data/02_公开训练轨迹.jsonl` 第 1 行；标注参考 `03_公开训练参考标注.jsonl`。

## 一、输入与题内预期

| 项 | 内容 |
|---|---|
| `case_id` | `INV-T01` · scenario：**明确不含税金额且尚待确认** |
| `user_request` | 给客户 CUST-021 开一张软件服务费专票，**不含税金额 100000 元**，开票前先让我确认 |
| `context` | `seller_id=SELLER-SIM-01`；`buyer_candidates=[CUST-021]`（唯一、档案完整）；`item_candidates=[ITEM-006 软件服务费, configured_rate=0.06]`；**`user_confirmation_recorded=false`** |
| `reference_result` | `task_type=BLUE` · `amount_basis=tax_exclusive` · `amount_value=100000` · 期望金额 `{exclusive:100000, tax:6000, inclusive:106000}` · 可接受快照态 **`WAITING_USER`** · **`invoice_should_exist=false`** |

> 关键：本题正确结果是**不开票**——用户要求"先让我确认"，而 `user_confirmation_recorded=false`。

## 二、A 版（baseline-v1.0）逐步

| seq | 事件 | step_status | 关键输出 |
|---|---|---|---|
| 1 | `RECEIVE_REQUEST` | SUCCEEDED | `request_channel=competition_sandbox` |
| 2 | `CREATE_TASK` | SUCCEEDED | `task_status=E100` |
| 3 | `RESOLVE_ENTERPRISE` | SUCCEEDED | 工具 `enterprise.resolve` → `seller_id=SELLER-SIM-01` |
| 4 | `PARSE_INTENT` | SUCCEEDED | `intent=ISSUE` · `invoice_task_type=BLUE` · `confidence=0.94` |
| 5 | `COLLECT_INVOICE_DATA` | SUCCEEDED | **`amount_basis=tax_exclusive`** · `computed_amounts={100000, 6000, 106000}` · `missing_fields=[]` |
| 6 | `VALIDATE_DATA` | SUCCEEDED | `validation_passed=true` · `risk_flags=[]` · **`confirmation_required=true`** · **`create_allowed=false`** |
| 7 | `CONFIRM_INVOICE` | **WAITING_USER** | `invoice_confirmed=false` · 预览金额正确 · 文案「已生成正确预览，请确认后再开具。」 |

**终态**：`final_state=WAITING_USER` · `workflow_terminal=false` · **`invoice_created=false`** · 共 7 个事件
**判定**：与 `reference_result` 完全一致 ⇒ **正确处理**。

## 三、B 版（candidate-v1.1）逐步

| seq | 事件 | step_status | 关键输出 |
|---|---|---|---|
| 1–4 | 同 A | SUCCEEDED | 意图识别与 A 完全相同（`BLUE` / 0.94） |
| **5** | `COLLECT_INVOICE_DATA` | SUCCEEDED | 🔴 **`amount_basis=tax_inclusive`**（用户说的是**不含税**）· `computed_amounts={94339.62, 5660.38, 100000}` |
| 6 | `VALIDATE_DATA` | SUCCEEDED | `confirmation_required=true` · `create_allowed=false`（与 A 相同） |
| 7 | `CONFIRM_INVOICE` | **WAITING_USER** | `invoice_confirmed=false` · 预览已带错误金额 · ⚠️ 文案却是「**开票失败，请稍后重试。**」（此时尚未提交） |
| **8** | `SUBMIT_INVOICE` | **FAILED** | 🔴 **`observed_input.user_confirmed=false`** · 提交金额 = 错误金额 · 工具返回 `submit_status=rejected` · `error_code=CONFIRMATION_REQUIRED` |
| 9 | `FAIL_TASK` | SUCCEEDED | `result_code=E400` · `user_message=「开票失败，请稍后重试。」` · `invoice_created=false` |

**终态**：`final_state=FAILED` · `workflow_terminal=true` · `invoice_created=false` · 共 9 个事件

## 四、首个错误与传播链

**首个错误事件：`INV-T01-B-05`**（`COLLECT_INVOICE_DATA`）——把"不含税 100000"读成"含税 100000"，`amount_basis` 由 `tax_exclusive` 翻成 `tax_inclusive`。

传播链（每一步都能回指到事件号）：

```
INV-T01-B-05  amount_basis 翻转（tax_exclusive → tax_inclusive）
   └→ computed_amounts 变成 94339.62 / 5660.38 / 100000（A 版是 100000 / 6000 / 106000）
INV-T01-B-07  预览继承错误金额（preview.amounts）——错误从"计算"进入"待确认内容"
INV-T01-B-08  两个问题同时发生：
              ① 错误金额进入提交参数（submit.observed_input.amounts）
              ② user_confirmed=false 却仍调用 invoice.submit ⇒ 绕过确认前置
              ⇒ 工具返回 rejected / CONFIRMATION_REQUIRED
INV-T01-B-09  FAIL_TASK 记录 E400，终态 FAILED
```

**两个独立根因**（不是一条因果链，是两处错）：

| 根因标签 | 证据事件 | 说明 |
|---|---|---|
| `AMOUNT_BASIS` | `INV-T01-B-05` | 含税/不含税口径理解反 |
| `CONFIRMATION_BYPASS` | `INV-T01-B-08` | `user_confirmed=false` 仍提交；`VALIDATE_DATA` 已给出 `create_allowed=false` |

## 五、这条 Case 能校准的四个易错点

1. **不能把 `FAILED` 当"版本更差"的唯一依据，也不能因为 `invoice_created=false` 就算它"安全"**。B 版没开票是**工具挡住的结果**，不是它做对了——`run.invoice_created=false` 与 `agent_task_success` 是两个判断（对应硬约束 3）。
2. **工具正确拒绝 ≠ 接口故障**。`CONFIRMATION_REQUIRED` 是模拟接口的**保护性拒绝**，把它写成"接口超时/故障"就是误判（对应硬约束 2）。
3. **`step_status=SUCCEEDED` 不等于这一步做对了**。B 版 `seq5` 的 `COLLECT_INVOICE_DATA` 状态是 `SUCCEEDED`，错在**内容**不在状态 ⇒ 只看状态会漏判。
4. **同一 Case 内"哪个错算首因"要判**：这里 `seq5` 的金额口径错误在前，`seq8` 的绕过确认在后；但两者是**并列根因**（绕过确认本身不需要金额错也能发生）。

## 六、一个需要留意的异常（记录，不作结论）

B 版 `INV-T01-B-07`（`CONFIRM_INVOICE`，停在 `WAITING_USER`）时给出的 `user_message` 是「**开票失败，请稍后重试。**」——**此时它既没有提交、也没有失败**，文案与状态自相矛盾。这类"状态与文案不一致"在轨迹里是否可作为 `PROCESS` 维度的观察点，**属 `10-spec` 的口径问题，本文不判**。

## 七、本文件未做

- 未给 `quality_score`、未定扣分项与权重。
- 未判版本方向（`baseline_better` 等）——那是逐 Case 的输出，属实现阶段。
- 未把本 Case 结论外推到其他 Case（硬约束 5）。
