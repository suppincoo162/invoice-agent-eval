# 任务拆分

> **本文件是「现在在推什么」的唯一主位置。**
> 当前阶段＝**`v0.3.0-dev`：确定性评测、证据完整性修复与训练/验证集回归已完成；下一步完成四方对照和 `v0.3.0` 交付**（as of 2026-11-08）。
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

## 阶段 B2 · 确定性规则扩展 —— ✅ 已完成 2026-11-04

- [x] **T-006** 实现重复/取消/超时校验 —— ✅ 证据：[`invoice_eval/risk_controls.py`](../../invoice_eval/risk_controls.py)、[`tests/test_risk_controls.py`](../../tests/test_risk_controls.py)
- [x] **T-007** 实现批量/红票校验 —— ✅ 证据：[`invoice_eval/invoice_types.py`](../../invoice_eval/invoice_types.py)、[`tests/test_invoice_types.py`](../../tests/test_invoice_types.py)
- [x] **T-022** 补齐 run 级证据：错误结果同时覆盖根因与最终业务结果，正确完整流程覆盖关键校验与终态 —— ✅ 证据：[`invoice_eval/evaluator.py`](../../invoice_eval/evaluator.py)、[`tests/test_validation_regression.py`](../../tests/test_validation_regression.py)、[`30-tdd/cases.md`](../30-tdd/cases.md) `TC-T011-10`～`TC-T011-12`

## 阶段 C · 模型增强与批量验证（模型盲审试点完成，正式主链路仍不接入）

- [x] **T-009** 实现可选 LLM 独立盲审试点 —— ✅ 证据：[`invoice_eval/llm_audit.py`](../../invoice_eval/llm_audit.py)、[`invoice_eval/audit_compare.py`](../../invoice_eval/audit_compare.py)、[`tests/test_llm_audit.py`](../../tests/test_llm_audit.py)、ADR-003；本地 `deepseek-r1:8b` 与云端 `deepseek-flash` 均完成 `INV-V03`
- [x] **T-010** 用训练集回归，对比参考标注 —— ✅ 证据：[`tests/test_training_regression.py`](../../tests/test_training_regression.py)（14 Case / 28 run 的布尔、根因、首错、证据和方向全部一致）
- [x] **T-011** 跑验证集，过格式校验 —— ✅ 证据：[`tests/test_validation_regression.py`](../../tests/test_validation_regression.py)（8 Case / 16 run，场景方向一致且通过官方校验）
- [x] **T-023** 强化 LLM 盲审契约：成功 run 也必须保留非空证据，有根因时不得标记处理成功 —— ✅ 证据：[`invoice_eval/llm_audit.py`](../../invoice_eval/llm_audit.py)、[`tests/test_llm_audit.py`](../../tests/test_llm_audit.py)、Prompt `llm-audit-v5`
- [x] **T-024** 统一版本语义：正式发布目标 `v0.3.0`，当前开发标识 `v0.3.0-dev`，Prompt 与人工初审快照独立标识 —— ✅ 证据：[`invoice_eval/version.py`](../../invoice_eval/version.py)、ADR-005、[`50-deliverables/method.md`](../50-deliverables/method.md)
- [x] **T-025** 实现确定性四源报告生成器，区分核心诊断分歧与证据范围差异 —— ✅ 证据：[`invoice_eval/four_way.py`](../../invoice_eval/four_way.py)、[`tests/test_four_way.py`](../../tests/test_four_way.py)、[`50-deliverables/four-way-report.md`](../50-deliverables/four-way-report.md)
- [x] **T-026** 实现可选四源 LLM 分析层，强制区分事实、推断、未知并校验事件锚点 —— ✅ 证据：[`invoice_eval/four_way_analysis.py`](../../invoice_eval/four_way_analysis.py)、[`tests/test_four_way_analysis.py`](../../tests/test_four_way_analysis.py)、Prompt `four-way-analysis-v1`
- [x] **T-027** 重构唯一主报告：业务结论、产品场景、研发证据分层，四源与 LLM 材料改为附录 —— ✅ 证据：[`50-deliverables/version-report.md`](../50-deliverables/version-report.md)、[`50-deliverables/four-way-report.md`](../50-deliverables/four-way-report.md)
- [x] **T-031** 从结构化输入确定性生成官方七节主报告和机器摘要 —— ✅ 证据：[`invoice_eval/version_report.py`](../../invoice_eval/version_report.py)、[`tests/test_version_report.py`](../../tests/test_version_report.py)
- [x] **T-032** 完成 Rubric 三路对抗审计并修复 P0/P1 —— ✅ 证据：[`50-deliverables/rubric-adversarial-audit-2026-11-08.md`](../50-deliverables/rubric-adversarial-audit-2026-11-08.md)、`117 passed`、`verify --with-rubric` 5/5

## 阶段 D · 交付 —— ✅ 已完成 2026-11-04
### 交付件核对清单（官方手册 §六 要求，2026-11-04 补）

| 交付件 | 状态 | 位置 |
|---|---|---|
| 可运行程序 | ✅ | `python -m invoice_eval evaluate --cases … --output …` |
| 源代码 | ✅ | `invoice_eval/`（17 模块） |
| **依赖说明** | ✅ | `README.md`「运行与环境（依赖说明）」——Python ≥3.10，**无第三方依赖** |
| 方法说明 | ✅ | `docs/50-deliverables/method.md`（含 `quality_score` 构成） |
| 版本评估报告 | ✅ | `docs/50-deliverables/version-report.md` |

> 漏项教训：14 份文档都写了，唯独「依赖说明」没人核对——**因为交付件从来没有 checklist**。本表就是那个 checklist，交稿前逐行打勾。

- [x] **T-012** 写方法说明 —— ✅ 证据：[`50-deliverables/method.md`](../50-deliverables/method.md)
- [x] **T-013** 写版本评估报告 —— ✅ 证据：[`50-deliverables/version-report.md`](../50-deliverables/version-report.md)

## 后续候选（未排期，不影响当前 MVP）

- [x] **T-028** 固化 EIR-100 Rubric 候选设计：五维评分、影响封顶、证据置信度分离 —— ✅ 证据：[`20-design/evidence-impact-rubric.md`](../20-design/evidence-impact-rubric.md)、ADR-006
- [x] **T-029** 实现 Rubric 双轨输出并完成 28+16 校准 —— ✅ 证据：[`invoice_eval/rubric.py`](../../invoice_eval/rubric.py)、[`tests/test_rubric.py`](../../tests/test_rubric.py)、`scripts/verify.py --with-rubric`
- [ ] **T-030** 实现反事实最小修复薄切片 —— 验收：金额、上下文、提交漂移、批量明细四类；仅内部视图；无法修复时明确降级
- [ ] **T-021** 评估是否试点反事实最小修复与对象感知信用分配 —— 前置：T-010 完成，且训练集出现至少两个真实归因缺失或重复；即使试点也只能影响内部归因与 `downstream_impact`，不得改变 schema、布尔结论或评分规则。设计与门槛见 [`20-design/counterfactual-attribution.md`](../20-design/counterfactual-attribution.md)、[`20-design/decisions.md`](../20-design/decisions.md) ADR-004
