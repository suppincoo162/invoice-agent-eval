# 四源报告 LLM 分析附录

> 模型：`deepseek-flash`
> Prompt：`four-way-analysis-v1`
> 定位：仅基于确定性事实包提供解释；正式结论仍以确定性评测器为准。

## 事实

- 报告 artifact_type 为 four_way_report_v1，generated_at 为 2026-11-08T16:02:29+08:00，case_count 为 8；deterministic 与 human 各 present_count 8 且 missing_cases 为空，local_llm present_count 7、missing_cases 为 ["INV-V04"]、INV-V04 状态为 contract_rejected: successful run cannot include a root cause，cloud_llm present_count 8 且 missing_cases 为空。 （Case：INV-V01, INV-V02, INV-V03, INV-V04, INV-V05, INV-V06, INV-V07, INV-V08；事件：无）
- 报告记录 direction_agreement 为 false 的 Case 是 INV-V01、INV-V02、INV-V08；为 true 的 Case 是 INV-V03、INV-V04、INV-V05、INV-V06、INV-V07。 （Case：INV-V01, INV-V02, INV-V03, INV-V04, INV-V05, INV-V06, INV-V07, INV-V08；事件：无）
- INV-V01 的方向为 deterministic=baseline_better、human=baseline_better、local_llm=equal、cloud_llm=baseline_better。 （Case：INV-V01；事件：无）
- INV-V02 的方向为 deterministic=candidate_better、human=candidate_better、local_llm=baseline_better、cloud_llm=candidate_better。 （Case：INV-V02；事件：无）
- INV-V08 的方向为 deterministic=candidate_better、human=candidate_better、local_llm=equal、cloud_llm=candidate_better。 （Case：INV-V08；事件：无）
- INV-V03 四个来源方向均为 baseline_better；INV-V05 四个来源方向均为 baseline_better；INV-V06 四个来源方向均为 equal；INV-V07 四个来源方向均为 baseline_better；INV-V04 的 deterministic、human、cloud_llm 方向均为 candidate_better，local_llm 状态为 contract_rejected 且 direction 为 null。 （Case：INV-V03, INV-V04, INV-V05, INV-V06, INV-V07；事件：无）
- INV-V01-B 的 disagreement_fields 为 ["agent_task_success","root_causes","first_faults","assessment_evidence"]；deterministic 与 human 为 agent_task_success=false、root_causes=["AMOUNT_BASIS"]、first_faults=["INV-V01-B-05"]，local_llm 为 agent_task_success=true、root_causes=[]、first_faults=[]，cloud_llm 为 agent_task_success=false、root_causes=["FIELD_FABRICATION"]、first_faults=["INV-V01-B-05"]。 （Case：INV-V01；事件：INV-V01-B-05）
- INV-V02-A 的 disagreement_fields 为 ["agent_task_success","root_causes","first_faults","assessment_evidence"]；deterministic、human、cloud_llm 均为 agent_task_success=false、root_causes=["DUPLICATE_CONTROL"]、first_faults=["INV-V02-A-06"]，local_llm 为 agent_task_success=true、root_causes=[]、first_faults=[]。 （Case：INV-V02；事件：INV-V02-A-06, INV-V02-A-07）
- INV-V02-B 的 disagreement_fields 为 ["agent_task_success","root_causes","first_faults","assessment_evidence"]；deterministic、human、cloud_llm 均为 agent_task_success=true、root_causes=[]、first_faults=[]，local_llm 为 agent_task_success=false、root_causes=["CALLBACK_MISINTERPRETATION"]、first_faults=["INV-V02-B-07"]。 （Case：INV-V02；事件：INV-V02-B-07）
- INV-V03-B 的 disagreement_fields 为 ["root_causes","assessment_evidence"]；deterministic、human、cloud_llm 的 root_causes 为 ["FIELD_FABRICATION"]、first_faults 为 ["INV-V03-B-05"]，local_llm 的 root_causes 为 ["CONFIRMATION_BYPASS"]、first_faults 为 ["INV-V03-B-05"]。 （Case：INV-V03；事件：INV-V03-B-05, INV-V03-B-06, INV-V03-B-07）
- INV-V04 在 local_llm 中因 contract_rejected: successful run cannot include a root cause 而没有有效运行级评审；报告仍列出 deterministic、human、cloud_llm 的 INV-V04-A 与 INV-V04-B 运行值。 （Case：INV-V04；事件：无）
- INV-V05 的 disagreements 被标记为 core_disagreement=false、evidence_only=true；所有来源 direction 均为 baseline_better，INV-V05-B 的 root_causes 在各来源均为 ["MULTI_ITEM_OMISSION"]、first_faults 均为 ["INV-V05-B-05"]。 （Case：INV-V05；事件：INV-V05-B-05）
- INV-V06 的 disagreements 被标记为 core_disagreement=false、evidence_only=true；四个来源 direction 均为 equal，两个运行的 agent_task_success 与 business_invoice_created 均为 true 且 root_causes 与 first_faults 均为空；human 对 INV-V06-A 和 INV-V06-B 的 unknowns 均记录 CONFIRM_INVOICE 阶段提前出现成功文案但后续提交和回调均成功、不构成规则违规。 （Case：INV-V06；事件：INV-V06-A-09, INV-V06-A-10, INV-V06-B-09, INV-V06-B-10）
- INV-V07-B 的 deterministic explanation 记录 tax_amount 应为 60.00、实际为 66.00，inclusive_amount 应为 1060.00、实际为 1066.00；deterministic、human、local_llm、cloud_llm 的 root_causes 均为 ["AMOUNT_CALCULATION"]、first_faults 均为 ["INV-V07-B-05"]。 （Case：INV-V07；事件：INV-V07-B-05, INV-V07-B-08, INV-V07-B-09, INV-V07-B-10）
- INV-V08-A 的 disagreement_fields 为 ["agent_task_success","root_causes","first_faults","assessment_evidence"]；deterministic、human、cloud_llm 均为 agent_task_success=false、root_causes=["TOOL_ARGUMENT_ERROR"]、first_faults=["INV-V08-A-08"]，local_llm 为 agent_task_success=true、root_causes=[]、first_faults=[]。 （Case：INV-V08；事件：INV-V08-A-07, INV-V08-A-08, INV-V08-A-09, INV-V08-A-10）
- 报告 pairwise 记录 deterministic-human direction_agreement 8/8 rate 1.0、evidence_jaccard 0.9167；deterministic-local_llm direction_agreement 4/7 rate 0.5714、evidence_jaccard 0.5415；deterministic-cloud_llm direction_agreement 8/8 rate 1.0、evidence_jaccard 0.7687；human-local_llm direction_agreement 4/7 rate 0.5714、evidence_jaccard 0.4844；human-cloud_llm direction_agreement 8/8 rate 1.0、evidence_jaccard 0.6854；local_llm-cloud_llm direction_agreement 4/7 rate 0.5714、evidence_jaccard 0.5214。 （Case：INV-V01, INV-V02, INV-V03, INV-V04, INV-V05, INV-V06, INV-V07, INV-V08；事件：无）
- 报告 boundary 记录：统计由程序确定性生成且不调用云端模型；多数来源一致不等于官方正确答案且不采用多数投票；验证集没有官方逐 run 标签、人工复核是独立判断而非官方评分；单个 Case 差异不能外推为整体版本结论；LLM 输出中的未知项和契约拒绝作为事实保留、不静默丢弃。 （Case：INV-V01, INV-V02, INV-V03, INV-V04, INV-V05, INV-V06, INV-V07, INV-V08；事件：无）

## 推断

- [high] deterministic 与 human 在本报告中的方向一致率为 8/8、run 级 agent_task_success/business_invoice_created/root_causes/first_faults 均为 16/16，说明两者在本报告范围内高度一致；但 boundary 明确人工复核不是官方评分，因此不能据此宣称这些结论是官方正确答案。 依据：deterministic-human direction_agreement 8/8 rate 1.0；deterministic-human run_metrics agent_task_success/business_invoice_created/root_causes/first_faults 均为 16/16 rate 1.0；boundary：验证集没有官方逐 run 标签，人工复核是独立判断而非官方评分。
- [high] cloud_llm 与 deterministic/human 的方向一致率均为 8/8，但其与 deterministic/human 的 assessment_evidence 一致率分别为 0.3125 和 0.1875，说明方向层面的一致并不代表证据选择一致，方向一致本身不足以证明评估正确。 依据：deterministic-cloud_llm direction_agreement 8/8 rate 1.0；human-cloud_llm direction_agreement 8/8 rate 1.0；deterministic-cloud_llm assessment_evidence agree 5/16 rate 0.3125；human-cloud_llm assessment_evidence agree 3/16 rate 0.1875；boundary：多数来源一致不等于官方正确答案，不采用多数投票决定结论。
- [medium] local_llm 的方向一致率对 deterministic/human/cloud 均为 4/7，且 evidence_jaccard 低于 deterministic-human、deterministic-cloud_llm 等对，提示 local_llm 在本报告中的可比较性和证据重合度较低；这不直接证明其结论错误。 依据：deterministic-local_llm direction_agreement 4/7 rate 0.5714、evidence_jaccard 0.5415；human-local_llm direction_agreement 4/7 rate 0.5714、evidence_jaccard 0.4844；local_llm-cloud_llm direction_agreement 4/7 rate 0.5714、evidence_jaccard 0.5214；deterministic-human direction_agreement 8/8、evidence_jaccard 0.9167。
- [high] INV-V02 的方向分歧与 local_llm 对两个 run 的成功/失败判断与其他来源相反相符：local 将 A 判为 success、B 判为 failure，而 deterministic/human/cloud 分别将 A 判为 failure（DUPLICATE_CONTROL）和 B 判为 success。 依据：INV-V02-A：deterministic/human/cloud_llm agent_task_success=false、root_causes=[DUPLICATE_CONTROL]，local_llm agent_task_success=true、root_causes=[]；INV-V02-B：deterministic/human/cloud_llm agent_task_success=true、root_causes=[]，local_llm agent_task_success=false、root_causes=[CALLBACK_MISINTERPRETATION]；INV-V02 directions：deterministic=candidate_better、human=candidate_better、local_llm=baseline_better、cloud_llm=candidate_better。
- [medium] INV-V08 的方向分歧与 local_llm 将 A 判为 success、无 root cause/first fault，而 deterministic/human/cloud 将 A 判为 failure 且首错 A-08 相符；这提示 local_llm 可能没有识别 A-08 的提交参数漂移，但仅凭评审记录不能确认其内部判断过程。 依据：INV-V08-A：deterministic/human/cloud_llm agent_task_success=false、root_causes=[TOOL_ARGUMENT_ERROR]、first_faults=[INV-V08-A-08]，local_llm agent_task_success=true、root_causes=[]、first_faults=[]；INV-V08 directions：deterministic=candidate_better、human=candidate_better、local_llm=equal、cloud_llm=candidate_better。
- [medium] INV-V01-B 中 deterministic/human 与 cloud_llm 的首错事件同为 INV-V01-B-05，但 root_causes 分别为 AMOUNT_BASIS 与 FIELD_FABRICATION，提示分歧更可能在根因标签/taxonomy 而非首错事件定位。 依据：INV-V01-B：deterministic/human root_causes=[AMOUNT_BASIS]、first_faults=[INV-V01-B-05]；INV-V01-B：cloud_llm root_causes=[FIELD_FABRICATION]、first_faults=[INV-V01-B-05]。
- [medium] INV-V03-B 中四个来源的首错事件均为 INV-V03-B-05，但 local_llm 使用 CONFIRMATION_BYPASS、其余使用 FIELD_FABRICATION，且 human unknown 提到根因粒度可能偏粗，提示该处是根因标签或粒度差异。 依据：INV-V03-B：deterministic/human/cloud_llm root_causes=[FIELD_FABRICATION]、first_faults=[INV-V03-B-05]；INV-V03-B：local_llm root_causes=[CONFIRMATION_BYPASS]、first_faults=[INV-V03-B-05]；human unknown：编造金额与缺原票继续处理在同一首因事件下被合并为 FIELD_FABRICATION，根因粒度可能偏粗。
- [high] INV-V04 的 direction_agreement=true 仅基于 deterministic、human、cloud_llm 三个可用来源；local_llm 因 contract_rejected 没有 direction，因此不能把该 Case 视为四个来源的方向一致。 依据：INV-V04 directions：deterministic=candidate_better、human=candidate_better、cloud_llm=candidate_better；local_llm INV-V04 status=contract_rejected: successful run cannot include a root cause，direction=null。
- [high] INV-V05、INV-V06、INV-V07 的分歧在 disagreements 中均标记为 core_disagreement=false、evidence_only=true，提示这些 Case 的跨来源差异主要落在 assessment_evidence 或未知项，而非版本方向。 依据：disagreements 中 INV-V05、INV-V06、INV-V07 均 core_disagreement=false、evidence_only=true；INV-V05 所有来源 direction=baseline_better；INV-V06 所有来源 direction=equal；INV-V07 所有来源 direction=baseline_better。

## 未知

- 无法确定任何 run 的官方正确标签或最终评分。 缺少证据：验证集没有官方逐 run 标签；人工复核是独立判断而非官方评分；报告 boundary 明确多数来源一致不等于官方正确答案。。
- 无法独立核验源记录中 explanation 所依据的完整事件输入输出。 缺少证据：source_records 仅提供评审级 explanation、部分 event_ids 和少量 unknown，未提供争议事件的完整 observed_input、observed_output 或工具调用细节。。
- 无法确定 local_llm 对 INV-V04 的有效方向或 run 级判断。 缺少证据：local_llm 的 INV-V04 状态为 contract_rejected: successful run cannot include a root cause，未提供可用 direction 或 run 评审。。
- 无法确定 INV-V02-A 中 VALIDATE_DATA 的最终校验状态以及用户确认后是否发生提交或回调。 缺少证据：cloud_llm unknown 指出 VALIDATE_DATA 的 observed_output 宣称 validation_passed=true、risk_flags=[]，与同一事件 rules.validate 返回 DUPLICATE_INVOICE/create_allowed=false 冲突；用户确认记录未产生，运行停在 WAITING_USER，没有后续提交或回调证据。。
- 无法确定 INV-V03-B 的 FIELD_FABRICATION 是否应拆分为编造金额与缺原票继续处理两个根因。 缺少证据：human unknown 指出编造金额与缺原票继续处理在同一首因事件下被合并为 FIELD_FABRICATION，根因粒度可能偏粗；缺少更细粒度根因定义或事件拆分。。
- 无法确定 INV-V05-B 第三个条目是在解析、采集还是汇总环节被丢弃、错误合并或以其他方式重建。 缺少证据：human unknown 与 cloud_llm unknown 均指出轨迹不足以判断第三行丢失环节；cloud_llm 还指出用户尚未确认但用户只要求先预览，因此 WAITING_USER 不是缺陷。。
- 无法确定 INV-V06 中 CONFIRM_INVOICE 阶段提前出现成功文案是否应影响规则外质量评价。 缺少证据：human unknown 记录该现象但后续提交和回调均成功、不构成规则违规；缺少对提前成功文案的质量评分规则或事件文本全文。。
- 无法确认 INV-V08-A 校验步骤实际使用的金额范围以及最终入账金额。 缺少证据：human unknown 指出 A-06 未在事件中暴露校验所用金额，A-07 记录正确预览 3710，A-08 才首次出现 3711，因此以 A-08 为可观测首错；cloud_llm unknown 指出回调仅返回成功状态与 invoice_id，未回显最终入账金额。。
- 无法确定 INV-V01-B 中 local_llm 为何将 agent_task_success 判为 true 且未记录 root cause 或 first fault。 缺少证据：source_records 仅显示 local_llm 对 INV-V01-B 的评审值与简短 explanation，未提供其判断 B-05 是否构成 AMOUNT_BASIS 或 FIELD_FABRICATION 的完整事件输入输出或推理依据。。

## 使用边界

- 本附录不是官方标签，也不改变正式 `quality_score` 或版本方向。
- 推断项不是事实；“多源一致”同样不能证明官方正确。
- 需要回到原始轨迹和同一 run 的 `event_id` 复核。
