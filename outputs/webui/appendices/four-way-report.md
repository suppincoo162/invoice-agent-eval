# AI 开票 Agent 四源独立评判技术附录

> 主报告：[version-report.md](version-report.md)。本附录只提供技术验证明细。
> 生成时间：`2026-11-09T21:54:09+08:00`
> 统计方式：确定性程序，不调用 LLM，不采用多数投票。

## 1. 输入与覆盖

| 来源 | 文件 | Case 数 | 缺失/拒绝 | 模型与版本 |
|---|---|---:|---|---|
| 确定性评测器 | `outputs/validation-v0.3.0.jsonl` | 8 | 无 | - |
| 独立复核 | `outputs/manual-review/v0.3.0-delta-review.jsonl` | 8 | 无 | - |
| 本地 LLM | `outputs/llm-review-local-v5-all.jsonl` | 7 | `INV-V04`：contract_rejected: successful run cannot include a root cause | model=deepseek-r1:14b；prompt=llm-audit-v5；evaluator=0.3.0-dev |
| 云端 LLM | `outputs/llm-review-cloud-v5-all.jsonl` | 8 | 无 | model=deepseek-flash；prompt=llm-audit-v5；evaluator=0.3.0-dev |

## 2. Case 方向矩阵

| Case | 确定性 | 人工 | 本地 LLM | 云端 LLM | 四源方向是否一致 |
|---|---|---|---|---|---|
| INV-V01 | `baseline_better` | `baseline_better` | `equal` | `baseline_better` | 否 |
| INV-V02 | `candidate_better` | `candidate_better` | `baseline_better` | `candidate_better` | 否 |
| INV-V03 | `baseline_better` | `baseline_better` | `baseline_better` | `baseline_better` | 是 |
| INV-V04 | `candidate_better` | `candidate_better` | - | `candidate_better` | 是 |
| INV-V05 | `baseline_better` | `baseline_better` | `baseline_better` | `baseline_better` | 是 |
| INV-V06 | `equal` | `equal` | `equal` | `equal` | 是 |
| INV-V07 | `baseline_better` | `baseline_better` | `baseline_better` | `baseline_better` | 是 |
| INV-V08 | `candidate_better` | `candidate_better` | `equal` | `candidate_better` | 否 |

## 3. 两两一致率

| 来源对 | 方向一致 | Agent 成败一致 | 发票事实一致 | 根因签名一致 | 首错一致 | 证据集合一致 | 证据 Jaccard |
|---|---:|---:|---:|---:|---:|---:|---:|
| 确定性评测器 vs 独立复核 | 8/8 (100.0%) | 16/16 (100.0%) | 16/16 (100.0%) | 16/16 (100.0%) | 16/16 (100.0%) | 16/16 (100.0%) | 1.000 |
| 确定性评测器 vs 本地 LLM | 4/7 (57.1%) | 10/14 (71.4%) | 14/14 (100.0%) | 9/14 (64.3%) | 10/14 (71.4%) | 2/14 (14.3%) | 0.541 |
| 确定性评测器 vs 云端 LLM | 8/8 (100.0%) | 16/16 (100.0%) | 16/16 (100.0%) | 15/16 (93.8%) | 16/16 (100.0%) | 5/16 (31.2%) | 0.769 |
| 独立复核 vs 本地 LLM | 4/7 (57.1%) | 10/14 (71.4%) | 14/14 (100.0%) | 9/14 (64.3%) | 10/14 (71.4%) | 2/14 (14.3%) | 0.541 |
| 独立复核 vs 云端 LLM | 8/8 (100.0%) | 16/16 (100.0%) | 16/16 (100.0%) | 15/16 (93.8%) | 16/16 (100.0%) | 5/16 (31.2%) | 0.769 |
| 本地 LLM vs 云端 LLM | 4/7 (57.1%) | 10/14 (71.4%) | 14/14 (100.0%) | 9/14 (64.3%) | 10/14 (71.4%) | 1/14 (7.1%) | 0.521 |

## 4. 核心诊断分歧

### INV-V01

方向：确定性评测器=`baseline_better`；独立复核=`baseline_better`；本地 LLM=`equal`；云端 LLM=`baseline_better`
- `INV-V01-B` 分歧字段：agent_task_success、root_causes、first_faults、assessment_evidence

### INV-V02

方向：确定性评测器=`candidate_better`；独立复核=`candidate_better`；本地 LLM=`baseline_better`；云端 LLM=`candidate_better`
- `INV-V02-A` 分歧字段：agent_task_success、root_causes、first_faults、assessment_evidence
- `INV-V02-B` 分歧字段：agent_task_success、root_causes、first_faults、assessment_evidence

### INV-V03

方向：确定性评测器=`baseline_better`；独立复核=`baseline_better`；本地 LLM=`baseline_better`；云端 LLM=`baseline_better`
- `INV-V03-A` 分歧字段：assessment_evidence
- `INV-V03-B` 分歧字段：root_causes、assessment_evidence

### INV-V08

方向：确定性评测器=`candidate_better`；独立复核=`candidate_better`；本地 LLM=`equal`；云端 LLM=`candidate_better`
- `INV-V08-A` 分歧字段：agent_task_success、root_causes、first_faults、assessment_evidence
- `INV-V08-B` 分歧字段：assessment_evidence

## 5. 证据范围差异

- `INV-V04`：核心诊断一致，证据集合不同（INV-V04-A、INV-V04-B）。
- `INV-V05`：核心诊断一致，证据集合不同（INV-V05-A、INV-V05-B）。
- `INV-V06`：核心诊断一致，证据集合不同（INV-V06-A、INV-V06-B）。
- `INV-V07`：核心诊断一致，证据集合不同（INV-V07-A、INV-V07-B）。

## 6. 明确记录的未知项

- `INV-V02` / 云端 LLM：VALIDATE_DATA 的 observed_output 宣称 validation_passed=true 且 risk_flags=[]，与同一事件中 rules.validate 返回 DUPLICATE_INVOICE/create_allowed=false 相冲突。
- `INV-V02` / 云端 LLM：用户确认记录未产生，运行停在 WAITING_USER；没有后续提交或回调证据。
- `INV-V03` / 独立复核：编造金额与缺原票继续处理在同一首因事件下被合并为 FIELD_FABRICATION，根因粒度可能偏粗，但不影响版本方向。
- `INV-V05` / 独立复核：轨迹不足以判断第三个条目是被丢弃、错误合并还是以其他方式重建；该不确定性不影响 MULTI_ITEM_OMISSION 和版本方向。
- `INV-V05` / 云端 LLM：用户尚未确认；但用户只要求先预览，因此 WAITING_USER 不是缺陷。
- `INV-V05` / 云端 LLM：轨迹未进一步说明第三行是在解析、采集还是汇总环节被丢弃。
- `INV-V06` / 独立复核：CONFIRM_INVOICE 阶段提前出现成功文案，但后续提交和回调均成功，不构成规则违规。
- `INV-V08` / 独立复核：A-06 未在事件中暴露校验所用金额，无法确认其实际校验范围；A-07 已记录正确预览 3710，A-08 才首次出现 3711，因此仍以 A-08 为可观测首错。
- `INV-V08` / 云端 LLM：回调仅返回成功状态与 invoice_id，未回显最终入账金额；无法从轨迹独立确认发票记录的最终金额。

## 7. 解释边界

- 本报告中的统计由程序确定性生成，不调用云端模型。
- 多数来源一致不等于官方正确答案；不采用多数投票决定结论。
- 验证集没有官方逐 run 标签，人工复核是独立判断而非官方评分。
- 单个 Case 的差异不能外推为整体版本结论。
- LLM 输出中的未知项和契约拒绝作为事实保留，不静默丢弃。

## 8. 结论使用方式

- 正式 submission 与版本方向以确定性评测器输出为主。
- 人工复核用于发现规则和证据链问题。
- 本地与云端 LLM 用于独立审计和分歧发现。
- 分歧案例应回到原始事件和同一 run 的 `event_id` 复核。
