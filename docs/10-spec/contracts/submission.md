# 输出契约（对齐 schema）

> 状态：**骨架**。真源＝`data/06_提交格式.schema.json`，本文件是**人读版说明**，两者冲突以 schema 为准。

## 顶层

```json
{ "case_id": "...", "run_assessments": [ {...}, {...} ], "version_comparison": {...} }
```

`run_assessments` **必须恰好 2 条**（minItems=maxItems=2）。

## run_assessments 每条的必填项（12 个）

`run_id` · `agent_task_success`(bool) · `business_invoice_created`(bool) · `quality_score`(0-100) ·
`business_result_assessment`(str) · `process_assessment`(str) · `penalty_items`(arr) ·
`root_causes`(arr) · `downstream_impact`(str) · `improvement_suggestions`(arr) ·
`evidence_event_ids`(arr) · `explanation`(str)

## penalty_items

必填：`dimension`(4 选 1) · `points_deducted`(0-100) · `evidence_event_ids` · `explanation`

## root_causes

必填：`label`(14 选 1) · `first_fault_event_id`(str|null) · `evidence_event_ids` · `explanation`
可选：`confidence`(0-1，须说明校准方法)

## version_comparison

必填：`direction` · `release_recommendation` · `reason`

## 校验命令

```bash
python data/08_提交格式校验.py --cases data/04_无标注验证轨迹.jsonl --submission your_submission.jsonl
```

⚠️ **格式通过 ≠ 答案正确。**
