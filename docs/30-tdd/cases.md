# 测试用例矩阵

> 状态：**建设中**。用例先定义期望行为，实现后补自动化测试路径。

## 首因与传播链回归

| 用例 ID | 数据 / 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T015-01` | `INV-T01-B`：金额口径错误 + 确认绕过 | 产出两个根因；`AMOUNT_BASIS.first_fault_event_id=INV-T01-B-05`，`CONFIRMATION_BYPASS.first_fault_event_id=INV-T01-B-08`；同一事件可作为一条链的传播和另一条链的首因 | 回归 |
| `TC-T015-02` | `INV-T05-B`：工具返回重复风险，Agent 输出抹去风险 | `DUPLICATE_CONTROL.first_fault_event_id=INV-T05-B-06`；不得把工具正确风险提示归因为工具故障 | 回归 |
| `TC-T015-03` | `INV-T10-B`：回调明确失败，最终却报告成功 | `CALLBACK_MISINTERPRETATION.first_fault_event_id=INV-T10-B-09`；后续成功说明是传播 | 回归 |
| `TC-T015-04` | `INV-T14-B`：已确认预览正确，提交金额发生漂移 | `TOOL_ARGUMENT_ERROR.first_fault_event_id=INV-T14-B-08`；不得把正确预览归因为首因 | 回归 |

## 评分与信用分配回归

| 用例 ID | 数据 / 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T016-01` | `INV-T01-A`：正确预览并等待确认 | `quality_score=100`；无 penalty；等待与未开票不扣分 | 回归 |
| `TC-T016-02` | `INV-T01-B`：金额口径错误 + 确认绕过 | 金额扣 30、确认绕过扣 50，`quality_score=20`；工具正确拒绝不产生额外 penalty | 回归 |
| `TC-T016-03` | `INV-T05-B`：忽略重复风险 | `DUPLICATE_CONTROL` 扣 50，`quality_score=50`；不得改记为工具故障 | 回归 |
| `TC-T016-04` | `INV-T14-B`：提交参数相对正确预览漂移 | `TOOL_ARGUMENT_ERROR` 扣 30，`quality_score=70`；正确预览不扣分 | 回归 |
| `TC-T016-05` | 同一根因通过多个传播事件重复出现 | 只按 `(label, first_fault_event_id)` 扣一次 | 单元 |
| `TC-T016-06` | Agent 行为不可评分 | 输出 `quality_score=0` 哨兵并在解释中写明不可评分；批量均值排除该样本，版本比较按 T-014 处理 | 反例 |

## 流程转移白名单回归

| 用例 ID | 数据 / 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T018-01` | 全部公开训练与验证 run | 不产生流程转移 finding | 回归 |
| `TC-T018-02` | 合成 `RECEIVE_REQUEST → SUBMIT_INVOICE` | 产生一条带两个事件证据的 `WORKFLOW_TRANSITION` finding | 反例 |
| `TC-T018-03` | `INV-T05-A` / `INV-V02-B` 的 `VALIDATE_DATA → FAIL_TASK` | 识别为有证据的业务终止例外，不误报 | 回归 |
| `TC-T018-04` | 终态后再次出现事件 | 产生流程转移 finding | 反例 |
| `TC-T018-05` | run 从非 `RECEIVE_REQUEST` 步骤开始 | 产生 `WORKFLOW_ENTRY` finding | 反例 |

## 金额口径与计算回归

| 用例 ID | 数据 / 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T004-01` | `INV-T01-B`：不含税被误作含税 | 仅产生 `AMOUNT_BASIS`，首错 `INV-T01-B-05`，不得重复报 `AMOUNT_CALCULATION` | 回归 |
| `TC-T004-02` | `INV-T02-A`：含税被误作不含税 | 仅产生 `AMOUNT_BASIS`，首错 `INV-T02-A-05` | 回归 |
| `TC-T004-03` | `INV-T13-A`：口径正确但税额少 10 倍 | 产生 `AMOUNT_CALCULATION`，首错 `INV-T13-A-05` | 回归 |
| `TC-T004-04` | `INV-T14-B`：预览与采集金额正确，提交参数漂移 | 金额采集模块不产生口径或计算 finding | 反例 |
| `TC-T004-05` | `INV-V04-A`：多轮修改后仍使用旧金额 | 不报 `AMOUNT_CALCULATION`，留给 `CONTEXT_UPDATE` | 反例 |
| `TC-T004-06` | 十进制舍入边界 | 使用 `Decimal` 与 `ROUND_HALF_UP`，保留两位小数 | 单元 |

## B1 单 Case 端到端回归

| 用例 ID | 数据 / 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T005-01` | `INV-T01-B`：`user_confirmed=false` 仍提交 | 产生 `CONFIRMATION_BYPASS`，首错 `INV-T01-B-08`，证据为 `B-07/B-08` | 回归 |
| `TC-T019-01` | `INV-T01-B`：提交工具返回 `CONFIRMATION_REQUIRED` | 识别为保护性拒绝，不产生 `TOOL_ERROR_HANDLING` 或接口故障结论 | 反例 |
| `TC-T008-01` | `INV-T01-B`：金额口径错误加确认绕过 | 稳定产出两个独立根因及各自首错事件，不跨 run 引用证据 | 回归 |
| `TC-T020-01` | `INV-T01`：CLI 单 Case 输出 | A/B 两个布尔值、分数 100/20、`baseline_better`、`defer`；输出通过官方格式校验 | 集成 |

## 必测的反例（来自手册明文警告）

1. `WAITING_USER` 不得被判成失败
2. 工具正确拒绝不得被判成接口故障
3. 外部失败但 Agent 如实报告 + 停止重试 ⇒ 应判**成功**
4. 单 Case 结论不得外推为整体结论
