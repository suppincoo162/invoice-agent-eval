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

## 必测的反例（来自手册明文警告）

1. `WAITING_USER` 不得被判成失败
2. 工具正确拒绝不得被判成接口故障
3. 外部失败但 Agent 如实报告 + 停止重试 ⇒ 应判**成功**
4. 单 Case 结论不得外推为整体结论
