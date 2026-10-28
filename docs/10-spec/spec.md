# 需求规格（What）

> 状态：**骨架**。本层是"做对"的定义源——与代码冲突时以本层为准。

##  deliverables 级别的验收

| # | 需求 | 验收标准 |
|---|---|---|
| R1 | 批量评估每个 Case 的两条 run | 输出逐行符合 schema；`run_assessments` 恰好 2 条 |
| R2 | **分开**报告 Agent 处理正确性与发票生成 | 两个布尔值独立给出，且**不得合并成单一成功率** |
| R3 | 定位首个错误事件 + 传播链 | 每个 `root_cause` 有 `first_fault_event_id` + `evidence_event_ids` |
| R4 | 版本比较 | `direction` + `release_recommendation` + `reason` 三件齐 |
| R5 | 机器可读 + 人读报告 | JSONL 通过 `08_提交格式校验.py`；报告覆盖批量 Case |
| R6 | 分数口径可复现 | `quality_score` 的构成公开且全 Case 一致适用 |

## 硬约束（不许做什么）

1. **不猜测**：缺必要信息或多候选 ⇒ 判「应追问/应选择」，不得判成"Agent 猜对了"
2. **不虚构根因**：证据不足用 `INSUFFICIENT_EVIDENCE`，并说明缺什么证据
3. **不跨 run 引用事件编号**
4. **不把单 Case 外推为整体版本结论**
5. **不把工具正确拦截归因为接口故障**
6. **不把 `WAITING_USER`/`E100` 直接判失败**
7. **不调用真实开票/报税/记账系统**

## 待补清单

- [ ] 把四项工作拆成更细的可验收条目
- [ ] 明确「证据不足」的判定门槛（什么情况下必须用 INSUFFICIENT_EVIDENCE）
- [ ] 明确「首因 vs 连锁后果」的操作性判据
