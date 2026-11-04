# 任务拆分

> **本文件是「现在在推什么」的唯一主位置。**
> 当前阶段＝**阶段 A、B0、B1 已完成；下一步进入 B2 确定性规则扩展**（as of 2026-11-04）。
> 完成的判定**必须有证据指针**（文档 / commit / 命令输出），不靠记忆。

## 阶段 A · 备料（事实层）—— ✅ 已完成 2026-10-31

| 产出 | 证据（单一主位置） |
|---|---|
| 赛题精读：四项工作 / 15 步流程与**转移白名单** / 9 状态 / 7 结果码 / 数据规模与陷阱 | [`00-brief/competition.md`](../00-brief/competition.md) |
| 数据形态：字段面 / step 与 tool 频次 / 金额精度与反算偏差 / 流程字典终态表达 | [`00-brief/dataset.md`](../00-brief/dataset.md) |
| 9 条业务规则 × 轨迹里能用什么字段核对 × 关联根因标签 | [`00-brief/rules.md`](../00-brief/rules.md) |
| 官方答案长什么样：`03_` 标注分布 + `05_` 示范口径 | [`00-brief/labeled-reference.md`](../00-brief/labeled-reference.md) |
| INV-T01 手工复现（A/B 逐事件 + 首错传播链，**与官方标注一致**） | [`00-brief/walkthrough-INV-T01.md`](../00-brief/walkthrough-INV-T01.md) |
| 判定式模型（Jev）现状与可借鉴点（**不含决策**） | [`00-brief/research/jev-decision-models.md`](../00-brief/research/jev-decision-models.md) |

## 阶段 B0 · 判据固化 —— ✅ 已完成 2026-11-04

- [x] **T-014** 定「证据不足（`INSUFFICIENT_EVIDENCE`）」的判定门槛 —— ✅ 证据：[`10-spec/spec.md`](../10-spec/spec.md)「证据充分性与 `INSUFFICIENT_EVIDENCE` 门槛」
- [x] **T-015** 定「首因 vs 连锁后果」的操作性判据 —— ✅ 证据：[`10-spec/spec.md`](../10-spec/spec.md)「首因与传播链判定」、[`30-tdd/cases.md`](../30-tdd/cases.md)「首因与传播链回归」
- [x] **T-016** 定 `quality_score` 的可复现计算口径 —— ✅ 证据：[`10-spec/spec.md`](../10-spec/spec.md)「质量评分与责任分配」、[`20-design/decisions.md`](../20-design/decisions.md) ADR-002、[`30-tdd/cases.md`](../30-tdd/cases.md)「评分与信用分配回归」
- [x] **T-017** 定「确定性校验 / 模型判断」的边界 —— ✅ 证据：[`20-design/decisions.md`](../20-design/decisions.md) ADR-001

> T-014～T-017 是 `10-spec` 与 `30-tdd` 的输入。没有这些口径不能进入阶段 B1。
> 建议执行顺序：**T-017 → T-014 → T-015 → T-016**；先锁定 MVP 的确定性边界，再定义证据、首因和评分。

## 阶段 B1 · `INV-T01` 单 Case 纵向 MVP —— ✅ 已完成 2026-11-04

- [x] **T-001** 读透 15 个流程步骤 —— ✅ 证据：[`00-brief/competition.md`](../00-brief/competition.md) §二（含 `possible_next_steps` 白名单）
- [x] **T-002** 统计训练集 scenario 分布 —— ✅ 证据：[`00-brief/dataset.md`](../00-brief/dataset.md)「scenario 覆盖」（训练 14 + 验证 8 全列）
- [x] **T-003** 实现事件读取与索引 —— ✅ 证据：[`invoice_eval/data.py`](../../invoice_eval/data.py)、[`tests/test_data.py`](../../tests/test_data.py)
- [x] **T-018** 实现流程转移白名单校验 —— ✅ 证据：[`invoice_eval/workflow.py`](../../invoice_eval/workflow.py)、[`tests/test_workflow.py`](../../tests/test_workflow.py)
- [x] **T-004** 实现金额口径/计算校验 —— ✅ 证据：[`invoice_eval/amounts.py`](../../invoice_eval/amounts.py)、[`tests/test_amounts.py`](../../tests/test_amounts.py)
- [x] **T-005** 实现确认前置校验 —— ✅ 证据：[`invoice_eval/confirmation.py`](../../invoice_eval/confirmation.py)、[`tests/test_confirmation.py`](../../tests/test_confirmation.py)
- [x] **T-019** 区分工具保护性拒绝与工具故障 —— ✅ 证据：[`invoice_eval/tooling.py`](../../invoice_eval/tooling.py)、[`tests/test_tooling.py`](../../tests/test_tooling.py)
- [x] **T-008** 实现确定性根因归因 —— ✅ 证据：[`invoice_eval/evaluator.py`](../../invoice_eval/evaluator.py)、[`tests/test_evaluator.py`](../../tests/test_evaluator.py)
- [x] **T-020** 实现评分与 A/B 输出 —— ✅ 证据：[`invoice_eval/scoring.py`](../../invoice_eval/scoring.py)、[`invoice_eval/cli.py`](../../invoice_eval/cli.py)、[`tests/test_evaluator.py`](../../tests/test_evaluator.py)

## 阶段 B2 · 确定性规则扩展（未开始）

- [ ] **T-006** 实现重复/取消/超时校验
- [ ] **T-007** 实现批量/红票校验

## 阶段 C · 模型增强与批量验证（未开始）

- [ ] **T-009** 接入模型层（复杂解释）；确定性版本必须先通过训练集回归
- [ ] **T-010** 用训练集回归，对比参考标注
- [ ] **T-011** 跑验证集，过格式校验

## 阶段 D · 交付（未开始）

- [ ] **T-012** 写方法说明
- [ ] **T-013** 写版本评估报告

## 后续候选（未排期，不影响当前 MVP）

- [ ] **T-021** 评估是否试点反事实最小修复与对象感知信用分配 —— 前置：T-010 完成，且训练集出现至少两个真实归因缺失或重复；即使试点也只能影响内部归因与 `downstream_impact`，不得改变 schema、布尔结论或评分规则。设计与门槛见 [`20-design/counterfactual-attribution.md`](../20-design/counterfactual-attribution.md)、[`20-design/decisions.md`](../20-design/decisions.md) ADR-004
