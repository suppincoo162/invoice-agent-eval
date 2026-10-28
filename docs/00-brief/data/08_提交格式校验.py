#!/usr/bin/env python3
"""AI 开票离线轨迹赛题的提交格式检查工具。仅检查结构，不评判答案。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_LABELS = {
    "INTENT_CLASSIFICATION", "ENTITY_RESOLUTION", "FIELD_FABRICATION",
    "AMOUNT_BASIS", "AMOUNT_CALCULATION", "PRODUCT_MATCH", "TOOL_ARGUMENT_ERROR",
    "MULTI_ITEM_OMISSION", "CONTEXT_UPDATE",
    "DUPLICATE_CONTROL", "CONFIRMATION_BYPASS", "TOOL_ERROR_HANDLING",
    "CALLBACK_MISINTERPRETATION", "INSUFFICIENT_EVIDENCE",
}
DIRECTIONS = {"baseline_better", "candidate_better", "equal", "insufficient_evidence"}
RECOMMENDATIONS = {"release", "gray", "defer", "investigate"}
PENALTY_DIMENSIONS = {"BUSINESS_RESULT", "PROCESS", "TOOL_CALL", "RISK_CONTROL"}


def load_jsonl(path: Path) -> list[dict]:
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name} 第{number}行不是合法JSON：{exc}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"{path.name} 第{number}行必须是JSON对象")
        records.append(obj)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True, help="待评测的Case JSONL文件")
    parser.add_argument("--submission", type=Path, required=True, help="参赛输出JSONL文件")
    parser.add_argument("--allow-partial", action="store_true", help="仅调试时允许只提交部分Case")
    args = parser.parse_args()

    errors: list[str] = []
    try:
        cases = load_jsonl(args.cases)
        submitted = load_jsonl(args.submission)
    except (OSError, ValueError) as exc:
        print(f"格式检查失败：{exc}", file=sys.stderr)
        return 1

    case_map = {x.get("case_id"): x for x in cases}
    if len(case_map) != len(cases) or None in case_map:
        errors.append("Case文件存在重复或缺失case_id")
    if not submitted:
        errors.append("提交文件为空")

    seen = set()
    for item in submitted:
        case_id = item.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            errors.append("提交记录缺少有效case_id")
            continue
        if case_id in seen:
            errors.append(f"{case_id}重复提交")
            continue
        seen.add(case_id)
        if case_id not in case_map:
            errors.append(f"{case_id}不在指定Case文件中")
            continue
        source_runs = {r["run_id"]: r for r in case_map[case_id]["runs"]}
        assessments = item.get("run_assessments")
        if not isinstance(assessments, list) or len(assessments) != len(source_runs):
            errors.append(f"{case_id}的run_assessments数量不正确")
            continue
        seen_runs = set()
        for assessment in assessments:
            if not isinstance(assessment, dict):
                errors.append(f"{case_id}的run_assessments须为对象")
                continue
            run_id = assessment.get("run_id")
            if run_id not in source_runs or run_id in seen_runs:
                errors.append(f"{case_id}含未知或重复run_id：{run_id}")
                continue
            seen_runs.add(run_id)
            event_ids = {e["event_id"] for e in source_runs[run_id]["events"]}
            for key in ("agent_task_success", "business_invoice_created"):
                if type(assessment.get(key)) is not bool:
                    errors.append(f"{case_id}/{run_id}的{key}必须是布尔值")
            if not isinstance(assessment.get("explanation"), str) or not assessment["explanation"].strip():
                errors.append(f"{case_id}/{run_id}缺少explanation")
            score = assessment.get("quality_score")
            if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 100:
                errors.append(f"{case_id}/{run_id}的quality_score须在0到100之间")
            for key in ("business_result_assessment", "process_assessment", "downstream_impact"):
                if not isinstance(assessment.get(key), str):
                    errors.append(f"{case_id}/{run_id}的{key}必须是文本")
                elif key != "downstream_impact" and not assessment[key].strip():
                    errors.append(f"{case_id}/{run_id}缺少{key}")
            suggestions = assessment.get("improvement_suggestions")
            if not isinstance(suggestions, list) or any(not isinstance(s, str) or not s.strip() for s in suggestions):
                errors.append(f"{case_id}/{run_id}的improvement_suggestions必须是文本数组")
            elif assessment.get("agent_task_success") is False and not suggestions:
                errors.append(f"{case_id}/{run_id}失败运行须给出改进建议")
            evidence = assessment.get("evidence_event_ids")
            if not isinstance(evidence, list) or any(e not in event_ids for e in evidence):
                errors.append(f"{case_id}/{run_id}的evidence_event_ids引用了非本次运行事件")
            penalties = assessment.get("penalty_items")
            if not isinstance(penalties, list):
                errors.append(f"{case_id}/{run_id}的penalty_items必须是数组")
            else:
                for penalty in penalties:
                    if not isinstance(penalty, dict) or penalty.get("dimension") not in PENALTY_DIMENSIONS:
                        errors.append(f"{case_id}/{run_id}存在无效扣分维度")
                        continue
                    points = penalty.get("points_deducted")
                    if isinstance(points, bool) or not isinstance(points, (int, float)) or not 0 <= points <= 100:
                        errors.append(f"{case_id}/{run_id}的扣分值无效")
                    refs = penalty.get("evidence_event_ids")
                    if not isinstance(refs, list) or any(e not in event_ids for e in refs):
                        errors.append(f"{case_id}/{run_id}的扣分证据事件无效")
                    if not isinstance(penalty.get("explanation"), str) or not penalty["explanation"].strip():
                        errors.append(f"{case_id}/{run_id}缺少扣分解释")
            roots = assessment.get("root_causes")
            if not isinstance(roots, list):
                errors.append(f"{case_id}/{run_id}的root_causes必须是数组")
                continue
            for root in roots:
                if not isinstance(root, dict) or root.get("label") not in ROOT_LABELS:
                    errors.append(f"{case_id}/{run_id}存在未知根因标签")
                    continue
                first = root.get("first_fault_event_id")
                refs = root.get("evidence_event_ids")
                if root["label"] == "INSUFFICIENT_EVIDENCE":
                    if first is not None and first not in event_ids:
                        errors.append(f"{case_id}/{run_id}证据不足标签的首因事件无效")
                elif first not in event_ids:
                    errors.append(f"{case_id}/{run_id}根因首个错误事件无效")
                if not isinstance(refs, list) or any(e not in event_ids for e in refs):
                    errors.append(f"{case_id}/{run_id}根因证据事件无效")
                if not isinstance(root.get("explanation"), str) or not root["explanation"].strip():
                    errors.append(f"{case_id}/{run_id}根因缺少解释")
                confidence = root.get("confidence")
                if confidence is not None and (isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1):
                    errors.append(f"{case_id}/{run_id}的confidence须在0到1之间")
        if seen_runs != set(source_runs):
            errors.append(f"{case_id}未覆盖全部run_id")
        comparison = item.get("version_comparison")
        if not isinstance(comparison, dict):
            errors.append(f"{case_id}缺少version_comparison")
        else:
            if comparison.get("direction") not in DIRECTIONS:
                errors.append(f"{case_id}的direction无效")
            if comparison.get("release_recommendation") not in RECOMMENDATIONS:
                errors.append(f"{case_id}的release_recommendation无效")
            if not isinstance(comparison.get("reason"), str) or not comparison["reason"].strip():
                errors.append(f"{case_id}的版本结论缺少reason")

    if not args.allow_partial and seen != set(case_map):
        errors.append(f"提交覆盖{len(seen)}/{len(case_map)}个Case；缺少{sorted(set(case_map) - seen)}")

    if errors:
        for error in errors:
            print("错误：" + error, file=sys.stderr)
        print(f"格式检查失败：{len(errors)}项错误", file=sys.stderr)
        return 1
    print(f"格式检查通过：{len(seen)}个Case，{sum(len(x['run_assessments']) for x in submitted)}条运行评估。")
    print("注意：本工具不检查业务判断和归因是否正确。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
