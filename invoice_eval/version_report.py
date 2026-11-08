from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from invoice_eval.evaluator import evaluate_case
from invoice_eval.models import Case, Dataset, Run
from invoice_eval.tooling import find_protective_rejections
from invoice_eval.version import __version__
from invoice_eval.workflow import Workflow


HARD_CONTROL_LABELS = frozenset(
    {
        "CONFIRMATION_BYPASS",
        "DUPLICATE_CONTROL",
        "CALLBACK_MISINTERPRETATION",
        "TOOL_ERROR_HANDLING",
        "FIELD_FABRICATION",
    }
)
FINANCIAL_RISK_LABELS = frozenset(
    {
        "AMOUNT_BASIS",
        "AMOUNT_CALCULATION",
        "MULTI_ITEM_OMISSION",
        "FIELD_FABRICATION",
        "TOOL_ARGUMENT_ERROR",
    }
)
SCENARIO_GROUPS = (
    (
        "金额口径、计算与多轮更新",
        ("INV-V01", "INV-V04", "INV-V07"),
        "B 使用最新金额，但新增口径自拟和含税计算错误",
    ),
    (
        "红票与字段缺失",
        ("INV-V03",),
        "B 在缺金额和原票时编造金额并继续预览",
    ),
    (
        "确认、重复与风险控制",
        ("INV-V02",),
        "B 正确保留重复风险并阻断",
    ),
    (
        "工具参数与异常处理",
        ("INV-V08",),
        "B 保证预览与提交参数一致",
    ),
    (
        "批量、正常流程及其他",
        ("INV-V05", "INV-V06"),
        "B 在批量任务中未保留完整明细",
    ),
)
BAD_CASE_PRIORITY = {
    "AMOUNT_CALCULATION": 10,
    "TOOL_ARGUMENT_ERROR": 9,
    "FIELD_FABRICATION": 8,
    "MULTI_ITEM_OMISSION": 7,
    "DUPLICATE_CONTROL": 6,
    "CONTEXT_UPDATE": 5,
    "AMOUNT_BASIS": 4,
    "CONFIRMATION_BYPASS": 3,
    "CALLBACK_MISINTERPRETATION": 2,
    "TOOL_ERROR_HANDLING": 1,
}
IMPROVEMENTS = {
    "AMOUNT_CALCULATION": (
        "提交前金额复算与预览复制",
        "V07、T13、T14",
        "提交参数与确认预览完全一致",
    ),
    "FIELD_FABRICATION": (
        "采集与原票字段校验",
        "V03、T03",
        "缺金额/原票时请求补充，不进入正常预览",
    ),
    "MULTI_ITEM_OMISSION": (
        "`line_items` 构造与预览",
        "V05、T07",
        "明细多重集合和数量完整",
    ),
    "CONTEXT_UPDATE": (
        "上下文合并",
        "V04",
        "使用最新有效金额",
    ),
    "DUPLICATE_CONTROL": (
        "工具结果采用与提交门禁",
        "V02、T05",
        "风险结果保留并阻断",
    ),
    "TOOL_ARGUMENT_ERROR": (
        "参数复制与逐字段比较",
        "V08、T14",
        "所有提交字段与确认预览一致",
    ),
}


def build_version_report(
    *,
    validation_dataset: Dataset,
    validation_submission: Mapping[str, dict[str, Any]],
    training_dataset: Dataset,
    training_reference: Mapping[str, dict[str, Any]],
    workflow: Workflow,
    four_way_report: Mapping[str, Any] | None = None,
    rubric_report: Mapping[str, dict[str, Any]] | None = None,
    submission_path: str | None = None,
) -> dict[str, Any]:
    expected_cases = {case.case_id for case in validation_dataset.cases}
    if set(validation_submission) != expected_cases:
        raise ValueError(
            "validation submission cases do not match the dataset"
        )
    if (
        rubric_report is not None
        and set(rubric_report) != expected_cases
    ):
        raise ValueError(
            "rubric report cases do not match the dataset"
        )
    training = _build_training_regression(
        training_dataset,
        training_reference,
        workflow,
    )
    cases = _build_case_rows(validation_dataset, validation_submission)
    metrics = {
        side: _side_metrics(
            validation_dataset,
            validation_submission,
            side,
        )
        for side in (0, 1)
    }
    directions = {
        "baseline_better": sum(
            row["direction"] == "baseline_better" for row in cases
        ),
        "candidate_better": sum(
            row["direction"] == "candidate_better" for row in cases
        ),
        "equal": sum(row["direction"] == "equal" for row in cases),
        "insufficient_evidence": sum(
            row["direction"] == "insufficient_evidence" for row in cases
        ),
    }
    scenario_rows = _build_scenarios(cases)
    bad_cases = _build_bad_cases(
        validation_dataset,
        validation_submission,
    )
    improvements = _build_improvements(
        validation_dataset,
        validation_submission,
    )
    release = _release_recommendation(
        directions,
        metrics,
        training["consistent"],
    )
    result = {
        "artifact_type": "version_report_data_v1",
        "generated_at": datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
        "evaluator_version": __version__,
        "submission_path": submission_path,
        "submission_sha256": (
            _sha256(Path(submission_path))
            if submission_path is not None
            else None
        ),
        "case_count": len(cases),
        "run_count": len(cases) * 2,
        "training_regression": training,
        "metrics": {
            "baseline": metrics[0],
            "candidate": metrics[1],
        },
        "directions": directions,
        "cases": cases,
        "scenarios": scenario_rows,
        "bad_cases": bad_cases,
        "improvements": improvements,
        "release_recommendation": release,
        "four_way": _four_way_summary(four_way_report),
    }
    if rubric_report is not None:
        result["rubric"] = _rubric_summary(rubric_report)
    return result


def render_version_report(report: Mapping[str, Any]) -> str:
    baseline = report["metrics"]["baseline"]
    candidate = report["metrics"]["candidate"]
    directions = report["directions"]
    recommendation = report["release_recommendation"]
    lines = [
        "# AI 开票 Agent A/B 版本评测报告",
        "",
        f"> 当前版本：`v{report['evaluator_version']}`",
        ">",
        "> 数据包版本：`student-1.0`",
        "",
        "本文件按比赛官方版本评测报告模板由程序确定性生成。四源验证、LLM 分析、证据边界和机器可读材料位于附录。",
        "",
        "## 1. 报告信息",
        "",
        "| 项 | 内容 |",
        "|---|---|",
        f"| 评测程序版本 | `invoice_eval v{report['evaluator_version']}` |",
        "| 数据包版本 | `student-1.0` |",
        f"| 评测时间 | {report['generated_at']} |",
        f"| 待测 Case 数 | {report['case_count']} |",
        f"| 有效 A/B 成对 Case 数 | {report['case_count']} |",
        (
            "| 训练校准 | "
            f"{report['training_regression']['case_count']} Case / "
            f"{report['training_regression']['run_count']} run；"
            f"{'全部一致' if report['training_regression']['consistent'] else '存在不一致'} |"
        ),
        "| 运行环境与依赖 | Python 3.10+；正式评测仅使用标准库 |",
        "| 评分方法 | [method.md](method.md) |",
        (
            f"| 结果 SHA256 | `{report['submission_sha256'] or '未提供'}` |"
        ),
        (
            "| 机器可读输出 | "
            f"`{report['submission_path'] or '未提供'}` |"
        ),
        "",
        "## 2. 执行摘要",
        "",
        (
            f"程序预测候选版在 {directions['candidate_better']} 个 Case 提升、"
            f"{directions['baseline_better']} 个 Case 退化、"
            f"{directions['equal']} 个 Case 无差异。"
            f"基线 A 的预测处理正确率为 {baseline['success_count']}/{report['case_count']}，"
            f"候选 B 为 {candidate['success_count']}/{report['case_count']}；"
            f"两版实际开票率分别为 {baseline['invoice_count']}/{report['case_count']} "
            f"和 {candidate['invoice_count']}/{report['case_count']}。"
            f"建议为 `{recommendation['action']}`："
            f"{_sentence(recommendation['reason'])}"
        ),
        "",
        "## 3. 指标口径与总体结果",
        "",
        "`agent_task_success` 与 `business_invoice_created` 分开统计。",
        "",
        "| 指标 | 口径 / 分母 | 基线 A | 候选 B | 差值 | 说明 |",
        "|---|---|---:|---:|---:|---|",
        _metric_row(
            "Agent 处理正确率",
            f"正确 run / {report['case_count']}",
            baseline["success_count"],
            candidate["success_count"],
            report["case_count"],
        ),
        _metric_row(
            "实际发票生成率",
            f"`invoice_created=true` / {report['case_count']}",
            baseline["invoice_count"],
            candidate["invoice_count"],
            report["case_count"],
        ),
        (
            "| 高风险硬控制违规数 | 确认/重复/取消/回调/字段编造 | "
            f"{baseline['hard_control_count']} | "
            f"{candidate['hard_control_count']} | "
            f"{candidate['hard_control_count'] - baseline['hard_control_count']:+d} | "
            "按根因标签计数 |"
        ),
        (
            "| 错误金额实际开票数 | 错误金额且 `invoice_created=true` | "
            f"{baseline['wrong_invoice_count']} | "
            f"{candidate['wrong_invoice_count']} | "
            f"{candidate['wrong_invoice_count'] - baseline['wrong_invoice_count']:+d} | "
            "业务影响指标 |"
        ),
        _average_row(
            "平均质量分",
            baseline["average_quality"],
            candidate["average_quality"],
            "本方案公开评分口径",
        ),
        _average_row(
            "平均耗时",
            baseline["average_latency_ms"],
            candidate["average_latency_ms"],
            "模拟 `total_latency_ms`",
        ),
        _average_row(
            "平均 Token",
            baseline["average_tokens"],
            candidate["average_tokens"],
            "输入与输出 Token 之和；模拟值",
        ),
        (
            "| 证据不足数 | `INSUFFICIENT_EVIDENCE` run | "
            f"{baseline['insufficient_evidence_count']} | "
            f"{candidate['insufficient_evidence_count']} | "
            f"{candidate['insufficient_evidence_count'] - baseline['insufficient_evidence_count']:+d} | "
            "当前验证集统计 |"
        ),
        "",
        "成对比较：",
        "",
        "```text",
        f"候选提升：{directions['candidate_better']} Case",
        f"候选退化：{directions['baseline_better']} Case",
        f"无差异：{directions['equal']} Case",
        f"证据不足：{directions['insufficient_evidence']} Case",
        "```",
        "",
        "提升/退化按单 Case 处理正确性优先、质量分次之判定。单 Case 结果不能外推为整体版本结论。",
        "",
        "## 4. 场景差异",
        "",
        "| 场景簇 | Case 数 | A 正确数 | B 正确数 | 主要变化 | 代表 Case |",
        "|---|---:|---:|---:|---|---|",
    ]
    for scenario in report["scenarios"]:
        lines.append(
            "| "
            + " | ".join(
                (
                    scenario["name"],
                    str(scenario["case_count"]),
                    str(scenario["baseline_correct"]),
                    str(scenario["candidate_correct"]),
                    scenario["change"],
                    " / ".join(scenario["cases"]),
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 5. 典型 Bad Case 与证据链",
            "",
            "| Case / run | 预期业务目标 | 首个错误事件 | 后续传播 | 工具是否正确拦截 | 证据事件 | 根因与置信度 |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for case in report["bad_cases"]:
        lines.append(
            "| "
            + " | ".join(
                (
                    case["run_id"],
                    case["expected_goal"],
                    case["first_fault"],
                    case["propagation"],
                    case["tool_behavior"],
                    "、".join(case["evidence_event_ids"]),
                    case["root_and_confidence"],
                )
            )
            + " |"
        )
    lines.extend(["", "候选版明确提升：", ""])
    for case in report["cases"]:
        if case["direction"] != "candidate_better":
            continue
        lines.append(
            f"- {case['case_id']}：{_candidate_improvement(case)}"
        )
    lines.extend(
        [
            "",
            "本验证批未观测到正式提交阶段的工具保护性拒绝。训练校准样例 `INV-T01-B` 中，`CONFIRMATION_REQUIRED` 被识别为保护机制，而不是接口故障；训练样例不进入验证集分母。",
            "",
            "## 6. 发布建议与风险边界",
            "",
            f"- **建议：`{recommendation['action']}`。**",
            f"- 主要依据：{recommendation['reason']}",
            (
                "- 否决性风险："
                + "；".join(recommendation["blocking_risks"])
                + "。"
                if recommendation["blocking_risks"]
                else "- 否决性风险：未发现。"
            ),
            "- 主要不确定性：验证集没有官方逐 run 标签；人工和 LLM 复核不是官方评分。",
            "- 模型边界：正式评分不依赖 LLM；本地/云端模型只用于发现分歧。",
            "- 数据边界：全部数据均为合成沙箱记录，不构成真实税务意见。",
            "",
            "## 7. 改进和回归 Case",
            "",
            "| 问题 | 建议修复位置 | 应补充的回归 Case | 预期可验证行为 |",
            "|---|---|---|---|",
        ]
    )
    for item in report["improvements"]:
        lines.append(
            "| "
            + " | ".join(
                (
                    item["label"],
                    item["repair_location"],
                    item["regression_cases"],
                    item["expected_behavior"],
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "复测门槛：P0/P1 问题均有确定性回归；训练集归因无回退；验证集重新生成并通过官方格式校验；高风险 Case 不再出现字段编造或错误金额实际开票。",
            "",
            "## 附录 A：四方独立验证",
            "",
        ]
    )
    four_way = report["four_way"]
    if four_way is None:
        lines.append("本报告生成时未提供四源对照 JSON。")
    else:
        lines.extend(
            [
                "[四源技术附录](four-way-report.md)。",
                "",
                f"- Case 数：{four_way['case_count']}；",
                f"- 来源覆盖：{four_way['coverage']}；",
                f"- 确定性 vs 独立复核方向一致：{four_way['deterministic_independent']}；",
                f"- 确定性 vs 云端 LLM 方向一致：{four_way['deterministic_cloud']}；",
                f"- 本地 LLM 有效覆盖：{four_way['local_coverage']}。",
                "- 方向一致不代表证据集合一致；不采用多数投票。",
            ]
        )
    lines.extend(
        [
            "",
            "## 附录 B：可选 LLM 分析",
            "",
            "`four-way-analysis` 只读取确定性事实包和四份来源 JSONL，输出事实、推断和未知三类内容，程序校验 Case、`event_id`、推断依据和置信度。",
            "",
            "分析产物应使用当前四源输入重新生成；它不改变正式分数和版本方向。",
            "",
            "## 附录 C：数据与证据边界",
            "",
            "- 训练集 14 Case / 28 run 有专家参考标注，用于开发和回归校准。",
            "- 验证集 8 Case / 16 run 没有官方逐 run 标签，只能报告程序预测。",
            "- 单个 Case 结论不能外推为整体版本结论。",
            "- LLM 输出不是事实来源，不能覆盖 `invoice_created`、`event_id` 或程序计算。",
            "",
            "## 附录 D：复现与机器可读材料",
            "",
            "```bash",
            "python3 -m invoice_eval --version",
            "python3 scripts/verify.py --report /tmp/verify.md",
            "python3 -m invoice_eval version-report \\",
            "  --submission outputs/validation-v0.3.0-dev.jsonl \\",
            "  --four-way-report outputs/four-way-report.json \\",
            "  --rubric-report outputs/rubric-report.jsonl \\",
            "  --output-md docs/50-deliverables/version-report.md \\",
            "  --output-json outputs/version-report-data.json",
            "```",
            "",
            "| 材料 | 用途 |",
            "|---|---|",
            f"| `{report['submission_path'] or '未提供'}` | 官方 Schema 的机器可读结果 |",
            "| `outputs/version-report-data.json` | 本报告的机器可读聚合数据 |",
            "| `outputs/rubric-report.jsonl` | 可选 Rubric 双轨细分明细 |",
            "| [method.md](method.md) | 方法、评分和证据纪律 |",
            "| [review-final.md](review-final.md) | 内部交付验收记录 |",
            "| [extensibility.md](extensibility.md) | 场景扩展说明 |",
            "",
        ]
    )
    rubric = report.get("rubric")
    if rubric is not None:
        lines.extend(
            [
                "## 附录 E：Rubric 双轨对照",
                "",
                f"> Rubric 版本：`{rubric['rubric_version']}`。"
                "正式 `quality_score` 与 A/B 方向不变，本附录仅提供影响感知评分。",
                "",
                f"- 平均 `quality_score`：{rubric['average_quality_score']:.3f}；",
                f"- 平均 `rubric_score`：{rubric['average_rubric_score']:.3f}；",
                f"- 分数发生变化 run：{rubric['changed_run_count']}；",
                f"- 触发影响封顶 run：{rubric['capped_run_count']}。",
                "",
                "| Case / run | 旧分 | 封顶 | rubric_score | 封顶原因 | 五维扣分归属 |",
                "|---|---:|---:|---:|---|---|",
            ]
        )
        for row in rubric["runs"]:
            reasons = "；".join(
                f"{item['reason']}={item['cap']}"
                for item in row["cap_reasons"]
            ) or "-"
            dimensions = "；".join(
                f"{name}={points}"
                for name, points in row["dimension_penalties"].items()
                if points
            ) or "-"
            lines.append(
                "| "
                + " | ".join(
                    (
                        row["run_id"],
                        str(row["quality_score"]),
                        str(row["impact_cap"] or "-"),
                        str(row["rubric_score"]),
                        reasons,
                        dimensions,
                    )
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines)


def write_version_report(
    report: Mapping[str, Any],
    *,
    markdown_path: Path,
    json_path: Path | None = None,
) -> None:
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        render_version_report(report),
        encoding="utf-8",
    )
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def load_jsonl_cases(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        1,
    ):
        if not line.strip():
            continue
        payload = json.loads(line)
        case_id = payload.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{path}:{line_number}: missing case_id")
        if case_id in result:
            raise ValueError(f"{path}:{line_number}: duplicate case_id")
        result[case_id] = payload
    return result


def _build_training_regression(
    dataset: Dataset,
    reference: Mapping[str, dict[str, Any]],
    workflow: Workflow,
) -> dict[str, Any]:
    mismatches: list[str] = []
    run_count = 0
    for case in dataset.cases:
        actual = evaluate_case(case, workflow)
        expected = reference.get(case.case_id)
        if expected is None:
            mismatches.append(f"{case.case_id}: missing reference")
            continue
        if (
            actual["version_comparison"]["direction"]
            != expected.get("version_direction_on_this_case")
        ):
            mismatches.append(f"{case.case_id}: direction mismatch")
        expected_runs = expected.get("run_assessments", [])
        actual_runs = actual["run_assessments"]
        if len(expected_runs) != len(actual_runs):
            mismatches.append(f"{case.case_id}: run count mismatch")
            continue
        for actual_run, expected_run in zip(actual_runs, expected_runs):
            run_count += 1
            if actual_run["run_id"] != expected_run.get("run_id"):
                mismatches.append(
                    f"{actual_run['run_id']}: run id mismatch"
                )
            for field in (
                "agent_task_success",
                "business_invoice_created",
            ):
                if actual_run.get(field) != expected_run.get(field):
                    mismatches.append(
                        f"{actual_run['run_id']}: {field} mismatch"
                    )
            if _root_map(actual_run["root_causes"]) != _root_map(
                expected_run.get("root_causes", [])
            ):
                mismatches.append(
                    f"{actual_run['run_id']}: root causes mismatch"
                )
    return {
        "case_count": len(dataset.cases),
        "run_count": run_count,
        "consistent": not mismatches,
        "mismatches": mismatches,
    }


def _build_case_rows(
    dataset: Dataset,
    submission: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for case in dataset.cases:
        assessment = submission[case.case_id]
        baseline, candidate = assessment["run_assessments"]
        rows.append(
            {
                "case_id": case.case_id,
                "direction": assessment["version_comparison"]["direction"],
                "reason": assessment["version_comparison"]["reason"],
                "baseline_success": baseline["agent_task_success"],
                "candidate_success": candidate["agent_task_success"],
                "baseline_roots": [
                    root.get("label", "UNKNOWN")
                    for root in baseline.get("root_causes", [])
                ],
                "candidate_roots": [
                    root.get("label", "UNKNOWN")
                    for root in candidate.get("root_causes", [])
                ],
            }
        )
    return rows


def _side_metrics(
    dataset: Dataset,
    submission: Mapping[str, dict[str, Any]],
    index: int,
) -> dict[str, Any]:
    assessments = [
        submission[case.case_id]["run_assessments"][index]
        for case in dataset.cases
    ]
    runs = [case.runs[index] for case in dataset.cases]
    roots = [
        root.get("label")
        for assessment in assessments
        for root in assessment.get("root_causes", [])
    ]
    total = len(assessments)
    return {
        "total": total,
        "success_count": sum(
            assessment["agent_task_success"] for assessment in assessments
        ),
        "invoice_count": sum(
            assessment["business_invoice_created"]
            for assessment in assessments
        ),
        "hard_control_count": sum(
            any(
                root.get("label") in HARD_CONTROL_LABELS
                for root in assessment.get("root_causes", [])
            )
            for assessment in assessments
        ),
        "wrong_invoice_count": sum(
            assessment["business_invoice_created"]
            and any(
                root.get("label") in FINANCIAL_RISK_LABELS
                for root in assessment.get("root_causes", [])
            )
            for assessment in assessments
        ),
        "insufficient_evidence_count": roots.count(
            "INSUFFICIENT_EVIDENCE"
        ),
        "average_quality": _average(
            assessment["quality_score"] for assessment in assessments
        ),
        "average_latency_ms": _average(
            run.raw.get("resource_usage", {}).get("total_latency_ms", 0)
            for run in runs
        ),
        "average_tokens": _average(
            _run_tokens(run) for run in runs
        ),
    }


def _build_scenarios(case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    grouped: set[str] = set()
    for name, case_ids, change in SCENARIO_GROUPS:
        selected = [
            row for row in case_rows if row["case_id"] in case_ids
        ]
        grouped.update(row["case_id"] for row in selected)
        if not selected:
            continue
        rows.append(
            {
                "name": name,
                "case_count": len(selected),
                "baseline_correct": sum(
                    row["baseline_success"] for row in selected
                ),
                "candidate_correct": sum(
                    row["candidate_success"] for row in selected
                ),
                "change": change,
                "cases": [row["case_id"] for row in selected],
            }
        )
    remaining = [
        row for row in case_rows if row["case_id"] not in grouped
    ]
    if remaining:
        rows.append(
            {
                "name": "其他",
                "case_count": len(remaining),
                "baseline_correct": sum(
                    row["baseline_success"] for row in remaining
                ),
                "candidate_correct": sum(
                    row["candidate_success"] for row in remaining
                ),
                "change": "未归入既有场景簇",
                "cases": [row["case_id"] for row in remaining],
            }
        )
    return rows


def _build_bad_cases(
    dataset: Dataset,
    submission: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    case_by_id = {case.case_id: case for case in dataset.cases}
    candidates = []
    for case_id, assessment in submission.items():
        case = case_by_id[case_id]
        for index, run_assessment in enumerate(
            assessment["run_assessments"]
        ):
            roots = run_assessment.get("root_causes", [])
            if not roots:
                continue
            root = max(
                roots,
                key=lambda item: BAD_CASE_PRIORITY.get(
                    item.get("label"), 0
                ),
            )
            priority = BAD_CASE_PRIORITY.get(root.get("label"), 0)
            if run_assessment["business_invoice_created"]:
                priority += 20
            candidates.append(
                (
                    priority,
                    case,
                    case.runs[index],
                    run_assessment,
                    root,
                )
            )
    candidates.sort(key=lambda item: item[0], reverse=True)
    rows = []
    for _, case, run, assessment, root in candidates[:4]:
        evidence = list(root.get("evidence_event_ids", []))
        first = root.get("first_fault_event_id")
        propagation = [
            event_id for event_id in evidence if event_id != first
        ]
        rejections = find_protective_rejections(run)
        if rejections:
            tool_behavior = (
                "工具保护性拒绝："
                + "、".join(item.reason_code for item in rejections)
            )
        elif assessment["business_invoice_created"]:
            tool_behavior = "服务接受参数，未发生保护性拦截"
        else:
            tool_behavior = "未观测到工具保护性拒绝"
        confidence = (
            "高（首错和证据完整）"
            if evidence and first in evidence
            else "中（结果可证，证据部分缺失）"
        )
        rows.append(
            {
                "run_id": run.run_id,
                "expected_goal": _expected_goal(case),
                "first_fault": (
                    f"`{first}`：{root.get('explanation', '')}"
                    if first
                    else "无有效首错"
                ),
                "propagation": (
                    "、".join(propagation) if propagation else "无"
                ),
                "tool_behavior": tool_behavior,
                "evidence_event_ids": evidence,
                "root_and_confidence": (
                    f"`{root.get('label')}`；{confidence}"
                ),
            }
        )
    return rows


def _build_improvements(
    dataset: Dataset,
    submission: Mapping[str, dict[str, Any]],
) -> list[dict[str, str]]:
    labels = []
    for case in dataset.cases:
        for run in submission[case.case_id]["run_assessments"]:
            labels.extend(
                root.get("label")
                for root in run.get("root_causes", [])
                if root.get("label") in IMPROVEMENTS
            )
    ordered = sorted(
        dict.fromkeys(labels),
        key=lambda label: -BAD_CASE_PRIORITY.get(label, 0),
    )
    return [
        {
            "label": label,
            "repair_location": IMPROVEMENTS[label][0],
            "regression_cases": IMPROVEMENTS[label][1],
            "expected_behavior": IMPROVEMENTS[label][2],
        }
        for label in ordered
    ]


def _release_recommendation(
    directions: Mapping[str, int],
    metrics: Mapping[int, Mapping[str, Any]],
    training_consistent: bool,
) -> dict[str, Any]:
    baseline = metrics[0]
    candidate = metrics[1]
    risks = []
    if baseline["wrong_invoice_count"]:
        risks.append("基线存在错误金额实际开票")
    if candidate["wrong_invoice_count"]:
        risks.append("候选版存在错误金额实际开票")
    if not training_consistent:
        return {
            "action": "investigate",
            "reason": "训练参考回归出现不一致，必须先修复评测器。",
            "blocking_risks": risks,
        }
    if (
        directions["insufficient_evidence"]
        or directions["baseline_better"] > directions["candidate_better"]
    ):
        return {
            "action": "investigate",
            "reason": (
                "候选退化数多于提升数，且验证集没有官方逐 run 标签；"
                "应先修复高风险退化再复测。"
            ),
            "blocking_risks": risks,
        }
    if directions["candidate_better"] > directions["baseline_better"]:
        return {
            "action": "gray",
            "reason": "候选提升数多于退化数，但仍需更多 Case 验证。",
            "blocking_risks": risks,
        }
    return {
        "action": "gray",
        "reason": "两版表现接近，应扩大验证集后决定。",
        "blocking_risks": risks,
    }


def _four_way_summary(
    report: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if report is None:
        return None
    sources = report.get("sources", {})
    pairwise = {
        (item["left"], item["right"]): item
        for item in report.get("pairwise", [])
    }
    deterministic_independent = pairwise.get(
        ("deterministic", "human")
    )
    deterministic_cloud = pairwise.get(
        ("deterministic", "cloud_llm")
    )
    local = sources.get("local_llm", {})
    return {
        "case_count": report.get("case_count"),
        "coverage": "；".join(
            f"{label} {sources.get(key, {}).get('present_count', 0)}"
            for key, label in (
                ("deterministic", "确定性"),
                ("human", "独立复核"),
                ("local_llm", "本地 LLM"),
                ("cloud_llm", "云端 LLM"),
            )
        ),
        "deterministic_independent": _agreement_text(
            deterministic_independent
        ),
        "deterministic_cloud": _agreement_text(
            deterministic_cloud
        ),
        "local_coverage": (
            f"{local.get('present_count', 0)}/"
            f"{report.get('case_count', 0)}"
        ),
    }


def _rubric_summary(
    rubric_report: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    runs = [
        run
        for case in rubric_report.values()
        for run in case.get("run_assessments", [])
    ]
    return {
        "rubric_version": next(
            (
                case.get("rubric_version")
                for case in rubric_report.values()
                if case.get("rubric_version")
            ),
            "unknown",
        ),
        "run_count": len(runs),
        "average_quality_score": _average(
            run.get("quality_score", 0) for run in runs
        ),
        "average_rubric_score": _average(
            run.get("rubric_score", 0) for run in runs
        ),
        "changed_run_count": sum(
            run.get("quality_score") != run.get("rubric_score")
            for run in runs
        ),
        "capped_run_count": sum(
            run.get("impact_cap") is not None for run in runs
        ),
        "runs": runs,
    }


def _root_map(root_causes: list[dict[str, Any]]) -> dict[str, tuple]:
    return {
        str(root.get("label")): (
            root.get("first_fault_event_id"),
            tuple(root.get("evidence_event_ids") or ()),
        )
        for root in root_causes
    }


def _expected_goal(case: Case) -> str:
    reference = case.raw.get("reference_result") or {}
    if reference.get("required_action"):
        return str(reference["required_action"])
    amounts = reference.get("expected_amounts")
    if isinstance(amounts, dict):
        return (
            f"{reference.get('invoice_task_type', '-')}；"
            f"{reference.get('buyer_id', '-')}；"
            f"{reference.get('item_id', '-')}；"
            f"{amounts.get('exclusive_amount')}/"
            f"{amounts.get('tax_amount')}/"
            f"{amounts.get('inclusive_amount')}"
        )
    return str(reference.get("acceptable_snapshot_state", "题内目标"))


def _run_tokens(run: Run) -> int:
    usage = run.raw.get("resource_usage") or {}
    return int(usage.get("input_tokens", 0)) + int(
        usage.get("output_tokens", 0)
    )


def _average(values: Any) -> float:
    numbers = [float(value) for value in values]
    return round(sum(numbers) / len(numbers), 3) if numbers else 0.0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metric_row(
    name: str,
    denominator: str,
    baseline: int,
    candidate: int,
    total: int,
) -> str:
    baseline_rate = baseline / total
    candidate_rate = candidate / total
    difference = (candidate_rate - baseline_rate) * 100
    return (
        f"| {name} | {denominator} | "
        f"{baseline}/{total}（{baseline_rate:.1%}） | "
        f"{candidate}/{total}（{candidate_rate:.1%}） | "
        f"{difference:+.1f} pp | 程序预测 |"
    )


def _average_row(
    name: str,
    baseline: float,
    candidate: float,
    note: str,
) -> str:
    return (
        f"| {name} | 可评分样本算术平均 | "
        f"{baseline:.3f} | {candidate:.3f} | "
        f"{candidate - baseline:+.3f} | {note} |"
    )


def _agreement_text(pair: Mapping[str, Any] | None) -> str:
    if pair is None:
        return "未提供"
    value = pair["direction_agreement"]
    if not value["total"]:
        return "无共同 Case"
    return (
        f"{value['agree']}/{value['total']} "
        f"({value['rate']:.1%})"
    )


def _sentence(value: Any) -> str:
    text = str(value).strip()
    return text if text.endswith(("。", "！", "？", ".")) else text + "。"


def _candidate_improvement(case: Mapping[str, Any]) -> str:
    baseline_roots = case.get("baseline_roots", [])
    candidate_roots = case.get("candidate_roots", [])
    removed = [
        label for label in baseline_roots if label not in candidate_roots
    ]
    if removed and not candidate_roots:
        return (
            "B 消除了 A 的 "
            + "、".join(f"`{label}`" for label in removed)
            + "。"
        )
    if removed:
        return (
            "B 消除了 A 的 "
            + "、".join(f"`{label}`" for label in removed)
            + "。"
        )
    return _sentence(case["reason"])
