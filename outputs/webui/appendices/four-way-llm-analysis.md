# 四源报告 LLM 分析附录

> 模型：`deepseek-flash`
> Prompt：`four-way-analysis-v1`
> 评测器：`0.3.0`
> 定位：仅基于确定性事实包提供解释；正式结论仍以确定性评测器为准。

## 事实

- 确定性四源报告的类型为 four_way_report_v1，生成时间为 2026-11-09T21:54:09+08:00，case_count 为 8。 （Case：INV-V01, INV-V02, INV-V03, INV-V04, INV-V05, INV-V06, INV-V07, INV-V08；事件：无）
- deterministic 与 human 的 present_count 均为 8 且 missing_cases 为空；local_llm 的 present_count 为 7、missing_cases 为 ["INV-V04"]、INV-V04 状态为 contract_rejected: successful run cannot include a root cause；cloud_llm 的 present_count 为 8 且 missing_cases 为空。 （Case：INV-V01, INV-V02, INV-V03, INV-V04, INV-V05, INV-V06, INV-V07, INV-V08；事件：无）
- deterministic 与 human 的方向一致为 8/8（rate 1.0），agent_task_success、business_invoice_created、root_causes、first_faults、assessment_evidence 的 run_metrics 一致均为 16/16（rate 1.0），evidence_jaccard 为 1.0。 （Case：INV-V01, INV-V02, INV-V03, INV-V04, INV-V05, INV-V06, INV-V07, INV-V08；事件：无）
- deterministic 与 cloud_llm 的方向一致为 8/8（rate 1.0），root_causes 一致为 15/16（rate 0.9375），first_faults 一致为 16/16（rate 1.0），assessment_evidence 一致为 5/16（rate 0.3125），evidence_jaccard 为 0.7687。 （Case：INV-V01, INV-V02, INV-V03, INV-V04, INV-V05, INV-V06, INV-V07, INV-V08；事件：无）
- deterministic 与 local_llm、human 与 local_llm、local_llm 与 cloud_llm 的方向一致均为 4/7（rate 0.5714）；deterministic 与 local_llm 的 agent_task_success 一致为 10/14（rate 0.7143），root_causes 一致为 9/14（rate 0.6429），assessment_evidence 一致为 2/14（rate 0.1429），evidence_jaccard 为 0.5415。 （Case：INV-V01, INV-V02, INV-V03, INV-V04, INV-V05, INV-V06, INV-V07, INV-V08；事件：无）
- direction_agreement 为 false 的 Case 是 INV-V01、INV-V02、INV-V08；local_llm 在这三个 Case 的方向分别为 equal、baseline_better、equal，而 deterministic、human、cloud_llm 在 INV-V01 均为 baseline_better、在 INV-V02 均为 candidate_better、在 INV-V08 均为 candidate_better。 （Case：INV-V01, INV-V02, INV-V08；事件：无）
- disagreements 中 core_disagreement 为 true 的 Case 是 INV-V01、INV-V02、INV-V03、INV-V08；core_disagreement 为 false 且 evidence_only 为 true 的 Case 是 INV-V04、INV-V05、INV-V06、INV-V07。 （Case：INV-V01, INV-V02, INV-V03, INV-V04, INV-V05, INV-V06, INV-V07, INV-V08；事件：无）
- INV-V01-B 中 deterministic 与 human 的 root_causes 为 AMOUNT_BASIS、first_faults 为 INV-V01-B-05；local_llm 记录 agent_task_success=true 且 root_causes 为空；cloud_llm 的 root_causes 为 FIELD_FABRICATION、first_faults 为 INV-V01-B-05，其 assessment_evidence 包含 INV-V01-B-05、INV-V01-B-06、INV-V01-B-07。 （Case：INV-V01；事件：INV-V01-B-05, INV-V01-B-06, INV-V01-B-07）
- INV-V02-A 中 deterministic、human、cloud_llm 的 root_causes 为 DUPLICATE_CONTROL、first_faults 为 INV-V02-A-06，local_llm 记录 agent_task_success=true 且 root_causes 为空；INV-V02-B 中 local_llm 的 root_causes 为 CALLBACK_MISINTERPRETATION、first_faults 为 INV-V02-B-07，而 deterministic、human、cloud_llm 记录 agent_task_success=true 且 root_causes 为空。 （Case：INV-V02；事件：INV-V02-A-06, INV-V02-A-07, INV-V02-B-06, INV-V02-B-07）
- INV-V03-B 中 deterministic、human、cloud_llm 的 root_causes 为 FIELD_FABRICATION、first_faults 为 INV-V03-B-05；local_llm 的 root_causes 为 CONFIRMATION_BYPASS、first_faults 仍为 INV-V03-B-05；human 的 unknown 指出编造金额与缺原票继续处理在同一首因事件下被合并为 FIELD_FABRICATION，根因粒度可能偏粗。 （Case：INV-V03；事件：INV-V03-B-04, INV-V03-B-05, INV-V03-B-06, INV-V03-B-07）
- local_llm 对 INV-V04 的状态为 contract_rejected: successful run cannot include a root cause，direction 为 null，且 source_records 的 local_llm 中没有 INV-V04 的 run 记录。 （Case：INV-V04；事件：无）
- INV-V05-B 中 deterministic、human、local_llm、cloud_llm 的 root_causes 均为 MULTI_ITEM_OMISSION、first_faults 均为 INV-V05-B-05；human 的 unknown 指出轨迹不足以判断第三个条目是被丢弃、错误合并还是以其他方式重建；cloud_llm 的 unknown 指出轨迹未说明第三行是在解析、采集还是汇总环节被丢弃。 （Case：INV-V05；事件：INV-V05-B-05, INV-V05-B-06, INV-V05-B-07）
- INV-V06 的四源 direction 均为 equal；INV-V06-A 与 INV-V06-B 在四源中的 agent_task_success 与 business_invoice_created 均为 true，root_causes 与 first_faults 均为空。 （Case：INV-V06；事件：INV-V06-A-05, INV-V06-A-06, INV-V06-A-07, INV-V06-A-08, INV-V06-A-09, INV-V06-A-10, INV-V06-B-05, INV-V06-B-06, INV-V06-B-07, INV-V06-B-08, INV-V06-B-09, INV-V06-B-10）
- INV-V07-B 中四源 root_causes 均为 AMOUNT_CALCULATION、first_faults 均为 INV-V07-B-05；deterministic 的解释为 tax_amount 应为 60.00、实际为 66.00，inclusive_amount 应为 1060.00、实际为 1066.00。 （Case：INV-V07；事件：INV-V07-B-05, INV-V07-B-08）
- INV-V08-A 中 deterministic、human、cloud_llm 的 root_causes 为 TOOL_ARGUMENT_ERROR、first_faults 为 INV-V08-A-08；local_llm 记录 agent_task_success=true 且 root_causes 为空；human 的 unknown 指出 A-06 未暴露校验所用金额、A-07 已记录正确预览 3710、A-08 才首次出现 3711；cloud_llm 的 unknown 指出回调仅返回成功状态与 invoice_id、未回显最终入账金额。 （Case：INV-V08；事件：INV-V08-A-06, INV-V08-A-07, INV-V08-A-08）
- local_llm 的 metadata 为 model=deepseek-r1:14b、prompt_version=llm-audit-v5、evaluator_version=0.3.0-dev；cloud_llm 的 metadata 为 model=deepseek-flash、prompt_version=llm-audit-v5、evaluator_version=0.3.0-dev；deterministic 与 human 的 model、prompt_version、evaluator_version 均为 null。 （Case：INV-V01, INV-V02, INV-V03, INV-V04, INV-V05, INV-V06, INV-V07, INV-V08；事件：无）

## 推断

- [high] local_llm 与 deterministic/human 的方向一致率、run 字段一致率和证据 Jaccard 均低于 cloud_llm，因此在本报告范围内 local_llm 的判断与 deterministic/human 的差异更大；这不等于 local_llm 错误。 依据：deterministic-local 方向一致 4/7（rate 0.5714），deterministic-cloud 方向一致 8/8（rate 1.0）；deterministic-local evidence_jaccard 0.5415，deterministic-cloud evidence_jaccard 0.7687；deterministic-local assessment_evidence 一致 2/14，deterministic-cloud assessment_evidence 一致 5/16。
- [high] cloud_llm 与 deterministic/human 在方向上 8/8 一致，但逐事件证据选择并不完全一致，因此方向一致不能推出证据选择一致，也不能据此认定其结论正确。 依据：deterministic-cloud 方向一致 8/8（rate 1.0）；deterministic-cloud assessment_evidence 一致 5/16（rate 0.3125）；deterministic-cloud evidence_jaccard 为 0.7687。
- [medium] deterministic 与 human 在本报告范围内的 run 字段与证据 Jaccard 完全一致，提示两者采用高度一致的口径；但边界声明称人工复核不是官方评分，因此不能把该一致当作官方正确答案。 依据：deterministic-human 方向一致 8/8（rate 1.0）；deterministic-human 各 run_metrics 均为 16/16（rate 1.0）；deterministic-human evidence_jaccard 为 1.0；boundary 声明验证集没有官方逐 run 标签，人工复核是独立判断而非官方评分。
- [medium] INV-V01-B 中 deterministic/human 归为 AMOUNT_BASIS，cloud_llm 归为 FIELD_FABRICATION，但三者首因事件均为 INV-V01-B-05，差异更可能来自根因标签分类而非首错定位；该判断仍需逐事件内容确认。 依据：INV-V01-B deterministic 与 human 的 root_causes 为 AMOUNT_BASIS、first_faults 为 INV-V01-B-05；INV-V01-B cloud_llm 的 root_causes 为 FIELD_FABRICATION、first_faults 为 INV-V01-B-05；cloud_llm 的 assessment_evidence 包含 INV-V01-B-05、INV-V01-B-06、INV-V01-B-07。
- [medium] INV-V03-B 中 local_llm 将同一首因 INV-V03-B-05 归类为 CONFIRMATION_BYPASS，而 deterministic/human/cloud_llm 归为 FIELD_FABRICATION，human 还提示合并粒度偏粗，说明根因标签的粒度或分类存在分歧。 依据：INV-V03-B deterministic、human、cloud_llm 的 root_causes 为 FIELD_FABRICATION、first_faults 为 INV-V03-B-05；INV-V03-B local_llm 的 root_causes 为 CONFIRMATION_BYPASS、first_faults 为 INV-V03-B-05；human 的 unknown 指出编造金额与缺原票继续处理在同一首因事件下被合并为 FIELD_FABRICATION，根因粒度可能偏粗。
- [medium] INV-V02-A 的关键争议在重复开票阻断是否被识别：deterministic/human/cloud_llm 均记录 DUPLICATE_CONTROL，而 local_llm 记录成功且无根因；结合 cloud_llm 指出的 validation_passed 与 rules.validate 返回值冲突，可推断该 Case 存在校验结果解释分歧，但报告未提供事件载荷，无法确认 local_llm 的具体推理。 依据：INV-V02-A deterministic、human、cloud_llm 的 root_causes 为 DUPLICATE_CONTROL、first_faults 为 INV-V02-A-06；INV-V02-A local_llm 记录 agent_task_success=true 且 root_causes 为空；cloud_llm 的 unknown 指出 VALIDATE_DATA 的 observed_output 宣称 validation_passed=true 且 risk_flags=[]，与同一事件中 rules.validate 返回 DUPLICATE_INVOICE/create_allowed=false 相冲突。
- [medium] INV-V08-A 中除 local_llm 外均识别 TOOL_ARGUMENT_ERROR，且 human/cloud_llm 的 unknown 都指向预览与提交金额或最终金额不可独立确认的问题；可推断 local_llm 未捕捉到提交参数漂移，但报告只给出事件 ID 与摘要，无法确认其遗漏原因。 依据：INV-V08-A deterministic、human、cloud_llm 的 root_causes 为 TOOL_ARGUMENT_ERROR、first_faults 为 INV-V08-A-08；INV-V08-A local_llm 记录 agent_task_success=true 且 root_causes 为空；human 的 unknown 指出 A-06 未暴露校验所用金额、A-07 已记录正确预览 3710、A-08 才首次出现 3711；cloud_llm 的 unknown 指出回调仅返回成功状态与 invoice_id、未回显最终入账金额。
- [high] INV-V04、INV-V05、INV-V06、INV-V07 的 core_disagreement 为 false 且 evidence_only 为 true，说明这些 Case 的主要差异集中在 assessment_evidence 选择，而不是方向结论；这提示证据集合存在来源间选择差异。 依据：disagreements 中 INV-V04、INV-V05、INV-V06、INV-V07 的 core_disagreement 为 false；disagreements 中 INV-V04、INV-V05、INV-V06、INV-V07 的 evidence_only 为 true；INV-V04、INV-V05、INV-V06、INV-V07 的 run disagreement_fields 均包含 assessment_evidence。
- [high] local_llm 的 INV-V04 被契约拒绝，导致其 pairwise 分母为 7 而非 8；因此 local_llm 的 4/7 方向一致率只适用于契约可接受的 7 个 Case，不能直接与 8/8 的 deterministic-human 或 deterministic-cloud 比较。 依据：local_llm 的 present_count 为 7、missing_cases 为 ["INV-V04"]、INV-V04 状态为 contract_rejected: successful run cannot include a root cause；deterministic 与 local_llm 的方向一致为 4/7（rate 0.5714）；deterministic 与 human、deterministic 与 cloud_llm 的方向一致均为 8/8（rate 1.0）。

## 未知

- 无法确定任一来源的判断是否为官方正确答案。 缺少证据：验证集没有官方逐 run 标签；人工复核是独立判断而非官方评分。
- 无法确定 local_llm 在 INV-V04 的方向和 run 级字段。 缺少证据：local_llm 对 INV-V04 的契约拒绝状态未提供可用的 run 输出，source_records 的 local_llm 中没有 INV-V04 记录。
- 无法确定 INV-V02-A 中 VALIDATE_DATA 的 validation_passed/risk_flags 与 rules.validate 返回值哪一方为权威事实。 缺少证据：报告仅以 cloud_llm unknown 描述冲突，缺少该事件的原始载荷或权威工具返回记录。
- 无法验证 local_llm 在 INV-V02-B 将 CALLBACK_MISINTERPRETATION 作为根因的具体依据。 缺少证据：缺少 INV-V02-B-07 的事件内容、回调细节与状态处理记录。
- 无法确定 INV-V05-B 第三个条目是在解析、采集还是汇总环节被丢弃。 缺少证据：human 与 cloud_llm 的 unknown 均指出轨迹未进一步说明第三行/第三条目的丢弃环节，缺少更完整的事件级输入输出。
- 无法确定 INV-V06 的 CONFIRM_INVOICE 阶段提前出现成功文案是否对后续提交或用户理解产生可观测影响。 缺少证据：human 仅说明该提前成功文案不构成规则违规，缺少事件文案细节和用户反馈。
- 无法从轨迹独立确认 INV-V08-A 最终发票入账金额。 缺少证据：cloud_llm 的 unknown 指出回调仅返回成功状态与 invoice_id，未回显最终入账金额。
- 无法确认 INV-V08-A 中 A-06 校验所用金额及其实际校验范围。 缺少证据：human 的 unknown 指出 A-06 未在事件中暴露校验所用金额。
- 无法确定 INV-V01-B 中用户真实期望的金额口径。 缺少证据：题内未指定含税/不含税口径，且报告中没有用户补充 amount_basis 的澄清记录。
- 无法确定 INV-V03-B 中真实的原票编号和金额。 缺少证据：题内未提供原票编号和金额，且报告中没有用户补充这些字段的记录。

## 使用边界

- 本附录不是官方标签，也不改变正式 `quality_score` 或版本方向。
- 推断项不是事实；“多源一致”同样不能证明官方正确。
- 需要回到原始轨迹和同一 run 的 `event_id` 复核。
