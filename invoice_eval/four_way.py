from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


SOURCES = ("deterministic", "human", "local_llm", "cloud_llm")
SOURCE_LABELS = {
    "deterministic": "确定性评测器",
    "human": "独立复核",
    "local_llm": "本地 LLM",
    "cloud_llm": "云端 LLM",
}
RUN_METRICS = (
    "agent_task_success",
    "business_invoice_created",
    "root_causes",
    "first_faults",
    "assessment_evidence",
)


def load_review_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path}:{line_number}: invalid JSON: {exc}"
                ) from exc
            if not isinstance(record, dict):
                raise ValueError(
                    f"{path}:{line_number}: review must be an object"
                )
            case_id = record.get("case_id")
            if not isinstance(case_id, str) or not case_id:
                raise ValueError(
                    f"{path}:{line_number}: case_id is required"
                )
            if case_id in records:
                raise ValueError(
                    f"{path}:{line_number}: duplicate case_id {case_id}"
                )
            records[case_id] = record
    return records


def load_local_manifest_statuses(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    statuses: dict[str, str] = {}
    for item in payload.get("rejected_cases", []):
        if not isinstance(item, dict):
            continue
        case_id = item.get("case_id")
        status = item.get("status")
        reason = item.get("reason")
        if not isinstance(case_id, str):
            continue
        if isinstance(status, str) and status:
            statuses[case_id] = (
                f"{status}: {reason}"
                if isinstance(reason, str) and reason
                else status
            )
    return statuses


def build_four_way_report(
    *,
    sources: Mapping[str, Mapping[str, dict[str, Any]]],
    source_paths: Mapping[str, str] | None = None,
    status_overrides: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    unknown_sources = set(sources) - set(SOURCES)
    if unknown_sources:
        raise ValueError(
            f"unknown sources: {sorted(unknown_sources)}"
        )

    overrides = status_overrides or {}
    all_cases = sorted(
        {
            case_id
            for records in sources.values()
            for case_id in records
        }
        | {
            case_id
            for source_overrides in overrides.values()
            for case_id in source_overrides
        }
    )
    if not all_cases:
        raise ValueError("no cases found in the four-way inputs")

    case_rows = [
        _build_case_row(
            case_id,
            sources=sources,
            overrides=overrides,
        )
        for case_id in all_cases
    ]
    pairwise = [
        _build_pairwise(left, right, sources)
        for index, left in enumerate(SOURCES)
        for right in SOURCES[index + 1 :]
    ]
    disagreements = [
        _case_disagreement_row(case)
        for case in case_rows
        if case["direction_agreement"] is False
        or any(run["disagreement_fields"] for run in case["runs"])
    ]

    return {
        "artifact_type": "four_way_report_v1",
        "generated_at": datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
        "sources": {
            source: _source_summary(
                source,
                sources.get(source, {}),
                overrides.get(source, {}),
                (source_paths or {}).get(source),
                all_cases,
            )
            for source in SOURCES
        },
        "case_count": len(all_cases),
        "cases": case_rows,
        "pairwise": pairwise,
        "disagreements": disagreements,
        "boundary": [
            "本报告中的统计由程序确定性生成，不调用云端模型。",
            "多数来源一致不等于官方正确答案；不采用多数投票决定结论。",
            "验证集没有官方逐 run 标签，人工复核是独立判断而非官方评分。",
            "单个 Case 的差异不能外推为整体版本结论。",
            "LLM 输出中的未知项和契约拒绝作为事实保留，不静默丢弃。",
        ],
    }


def write_four_way_report(
    report: Mapping[str, Any],
    *,
    json_path: Path,
    markdown_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_four_way_markdown(report),
        encoding="utf-8",
    )


def render_four_way_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# AI 开票 Agent 四源独立评判技术附录",
        "",
        "> 主报告：[version-report.md](version-report.md)。本附录只提供技术验证明细。",
        f"> 生成时间：`{report['generated_at']}`",
        "> 统计方式：确定性程序，不调用 LLM，不采用多数投票。",
        "",
        "## 1. 输入与覆盖",
        "",
        "| 来源 | 文件 | Case 数 | 缺失/拒绝 | 模型与版本 |",
        "|---|---|---:|---|---|",
    ]
    for source in SOURCES:
        summary = report["sources"][source]
        metadata = summary["metadata"]
        model_info = "；".join(
            part
            for part in (
                (
                    f"model={metadata['model']}"
                    if metadata.get("model")
                    else ""
                ),
                (
                    f"prompt={metadata['prompt_version']}"
                    if metadata.get("prompt_version")
                    else ""
                ),
                (
                    f"evaluator={metadata['evaluator_version']}"
                    if metadata.get("evaluator_version")
                    else ""
                ),
            )
            if part
        ) or "-"
        missing = summary["missing_cases"]
        missing_text = (
            "；".join(
                f"`{case_id}`：{summary['statuses'].get(case_id, 'missing')}"
                for case_id in missing
            )
            or "无"
        )
        lines.append(
            "| "
            + " | ".join(
                (
                    SOURCE_LABELS[source],
                    f"`{summary['path']}`" if summary["path"] else "-",
                    str(summary["present_count"]),
                    missing_text,
                    model_info,
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 2. Case 方向矩阵",
            "",
            "| Case | 确定性 | 人工 | 本地 LLM | 云端 LLM | 四源方向是否一致 |",
            "|---|---|---|---|---|---|",
        ]
    )
    for case in report["cases"]:
        lines.append(
            "| "
            + " | ".join(
                (
                    case["case_id"],
                    *(
                        _direction_text(
                            case["sources"][source]["direction"]
                        )
                        for source in SOURCES
                    ),
                    "是"
                    if case["direction_agreement"]
                    else "否",
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 3. 两两一致率",
            "",
            "| 来源对 | 方向一致 | Agent 成败一致 | 发票事实一致 | 根因签名一致 | 首错一致 | 证据集合一致 | 证据 Jaccard |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for pair in report["pairwise"]:
        metrics = pair["run_metrics"]
        lines.append(
            "| "
            + " | ".join(
                (
                    (
                        f"{SOURCE_LABELS[pair['left']]} vs "
                        f"{SOURCE_LABELS[pair['right']]}"
                    ),
                    _ratio_text(pair["direction_agreement"]),
                    _ratio_text(metrics["agent_task_success"]),
                    _ratio_text(metrics["business_invoice_created"]),
                    _ratio_text(metrics["root_causes"]),
                    _ratio_text(metrics["first_faults"]),
                    _ratio_text(metrics["assessment_evidence"]),
                    (
                        f"{pair['evidence_jaccard']:.3f}"
                        if pair["evidence_jaccard"] is not None
                        else "-"
                    ),
                )
            )
            + " |"
        )

    core_disagreements = [
        item
        for item in report["disagreements"]
        if item["core_disagreement"]
    ]
    evidence_only = [
        item
        for item in report["disagreements"]
        if item["evidence_only"]
    ]
    lines.extend(["", "## 4. 核心诊断分歧", ""])
    if not core_disagreements:
        lines.append("未发现方向、Agent 成败、发票事实、根因或首错分歧。")
    else:
        for disagreement in core_disagreements:
            lines.append(f"### {disagreement['case_id']}")
            lines.append("")
            lines.append(
                "方向："
                + "；".join(
                    f"{SOURCE_LABELS[source]}="
                    f"{_direction_text(direction)}"
                    for source, direction in disagreement[
                        "directions"
                    ].items()
                )
            )
            for run in disagreement["runs"]:
                if not run["disagreement_fields"]:
                    continue
                lines.append(
                    f"- `{run['run_id']}` 分歧字段："
                    + "、".join(run["disagreement_fields"])
                )
            lines.append("")

    lines.extend(["## 5. 证据范围差异", ""])
    if not evidence_only:
        lines.append("未发现仅由证据范围造成的差异。")
    else:
        for disagreement in evidence_only:
            changed_runs = [
                run["run_id"]
                for run in disagreement["runs"]
                if "assessment_evidence" in run["disagreement_fields"]
            ]
            lines.append(
                f"- `{disagreement['case_id']}`：核心诊断一致，"
                f"证据集合不同（{'、'.join(changed_runs)}）。"
            )
    lines.append("")

    unknowns = [
        (case["case_id"], source, item)
        for case in report["cases"]
        for source in SOURCES
        for item in case["sources"][source]["unknowns"]
    ]
    lines.extend(["## 6. 明确记录的未知项", ""])
    if unknowns:
        for case_id, source, item in unknowns:
            lines.append(
                f"- `{case_id}` / {SOURCE_LABELS[source]}：{item}"
            )
    else:
        lines.append("无。")
    lines.append("")

    lines.extend(
        [
            "## 7. 解释边界",
            "",
            *[f"- {item}" for item in report["boundary"]],
            "",
            "## 8. 结论使用方式",
            "",
            "- 正式 submission 与版本方向以确定性评测器输出为主。",
            "- 人工复核用于发现规则和证据链问题。",
            "- 本地与云端 LLM 用于独立审计和分歧发现。",
            "- 分歧案例应回到原始事件和同一 run 的 `event_id` 复核。",
            "",
        ]
    )
    return "\n".join(lines)


def _build_case_row(
    case_id: str,
    *,
    sources: Mapping[str, Mapping[str, dict[str, Any]]],
    overrides: Mapping[str, Mapping[str, str]],
) -> dict[str, Any]:
    source_rows: dict[str, dict[str, Any]] = {}
    for source in SOURCES:
        record = sources.get(source, {}).get(case_id)
        if record is None:
            status = overrides.get(source, {}).get(case_id, "missing")
            source_rows[source] = {
                "status": status,
                "direction": None,
                "runs": {},
                "unknowns": [],
            }
            continue
        runs = {
            run.get("run_id"): run
            for run in record.get("run_assessments", [])
            if isinstance(run, dict)
        }
        source_rows[source] = {
            "status": "available",
            "direction": record.get("version_comparison", {}).get(
                "direction"
            ),
            "runs": runs,
            "unknowns": list(
                dict.fromkeys(
                    item
                    for run in runs.values()
                    for item in run.get("unknowns", [])
                    if isinstance(item, str) and item
                )
            ),
        }

    directions = [
        row["direction"]
        for row in source_rows.values()
        if row["direction"] is not None
    ]
    run_ids = sorted(
        {
            run_id
            for row in source_rows.values()
            for run_id in row["runs"]
        }
    )
    run_rows = [
        _build_run_row(run_id, source_rows)
        for run_id in run_ids
    ]
    return {
        "case_id": case_id,
        "sources": {
            source: {
                "status": source_rows[source]["status"],
                "direction": source_rows[source]["direction"],
                "unknowns": source_rows[source]["unknowns"],
            }
            for source in SOURCES
        },
        "direction_agreement": (
            len(set(directions)) <= 1 if directions else None
        ),
        "runs": run_rows,
    }


def _build_run_row(
    run_id: str,
    source_rows: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    values: dict[str, dict[str, Any]] = {}
    for source in SOURCES:
        run = source_rows[source]["runs"].get(run_id)
        if run is None:
            continue
        values[source] = {
            "agent_task_success": run.get("agent_task_success"),
            "business_invoice_created": run.get(
                "business_invoice_created"
            ),
            "root_causes": _root_signature(run.get("root_causes", [])),
            "first_faults": _first_fault_signature(
                run.get("root_causes", [])
            ),
            "assessment_evidence": tuple(
                sorted(run.get("evidence_event_ids", []))
            ),
        }
    disagreement_fields = []
    if len(values) > 1:
        for field in RUN_METRICS:
            unique = {
                _canonical(value[field])
                for value in values.values()
            }
            if len(unique) > 1:
                disagreement_fields.append(field)
    return {
        "run_id": run_id,
        "values": values,
        "disagreement_fields": disagreement_fields,
    }


def _build_pairwise(
    left: str,
    right: str,
    sources: Mapping[str, Mapping[str, dict[str, Any]]],
) -> dict[str, Any]:
    common_cases = sorted(set(sources.get(left, {})) & set(sources.get(right, {})))
    direction_agree = 0
    metric_totals = {metric: 0 for metric in RUN_METRICS}
    metric_agree = {metric: 0 for metric in RUN_METRICS}
    evidence_jaccard_sum = 0.0
    evidence_pairs = 0
    for case_id in common_cases:
        left_case = sources[left][case_id]
        right_case = sources[right][case_id]
        if left_case.get("version_comparison", {}).get(
            "direction"
        ) == right_case.get("version_comparison", {}).get("direction"):
            direction_agree += 1
        left_runs = {
            run.get("run_id"): run
            for run in left_case.get("run_assessments", [])
        }
        right_runs = {
            run.get("run_id"): run
            for run in right_case.get("run_assessments", [])
        }
        for run_id in sorted(set(left_runs) & set(right_runs)):
            left_run = left_runs[run_id]
            right_run = right_runs[run_id]
            comparisons = {
                "agent_task_success": (
                    left_run.get("agent_task_success"),
                    right_run.get("agent_task_success"),
                ),
                "business_invoice_created": (
                    left_run.get("business_invoice_created"),
                    right_run.get("business_invoice_created"),
                ),
                "root_causes": (
                    _root_signature(left_run.get("root_causes", [])),
                    _root_signature(right_run.get("root_causes", [])),
                ),
                "first_faults": (
                    _first_fault_signature(
                        left_run.get("root_causes", [])
                    ),
                    _first_fault_signature(
                        right_run.get("root_causes", [])
                    ),
                ),
                "assessment_evidence": (
                    tuple(sorted(left_run.get("evidence_event_ids", []))),
                    tuple(sorted(right_run.get("evidence_event_ids", []))),
                ),
            }
            for metric, (left_value, right_value) in comparisons.items():
                metric_totals[metric] += 1
                if left_value == right_value:
                    metric_agree[metric] += 1
            left_evidence = set(left_run.get("evidence_event_ids", []))
            right_evidence = set(right_run.get("evidence_event_ids", []))
            union = left_evidence | right_evidence
            evidence_jaccard_sum += (
                len(left_evidence & right_evidence) / len(union)
                if union
                else 1.0
            )
            evidence_pairs += 1
    return {
        "left": left,
        "right": right,
        "direction_agreement": _ratio(direction_agree, len(common_cases)),
        "run_metrics": {
            metric: _ratio(metric_agree[metric], metric_totals[metric])
            for metric in RUN_METRICS
        },
        "evidence_jaccard": (
            round(evidence_jaccard_sum / evidence_pairs, 4)
            if evidence_pairs
            else None
        ),
    }


def _source_summary(
    source: str,
    records: Mapping[str, dict[str, Any]],
    overrides: Mapping[str, str],
    path: str | None,
    all_cases: Iterable[str],
) -> dict[str, Any]:
    metadata_values = {
        key: sorted(
            {
                str(record[key])
                for record in records.values()
                if record.get(key) is not None
            }
        )
        for key in ("model", "prompt_version", "evaluator_version")
    }
    metadata = {
        key: values[0]
        if len(values) == 1
        else ", ".join(values)
        if values
        else None
        for key, values in metadata_values.items()
    }
    missing = [
        case_id for case_id in all_cases if case_id not in records
    ]
    return {
        "source": source,
        "path": path,
        "present_count": len(records),
        "missing_cases": missing,
        "statuses": {
            case_id: overrides.get(case_id, "missing")
            for case_id in missing
        },
        "metadata": metadata,
    }


def _case_disagreement_row(case: Mapping[str, Any]) -> dict[str, Any]:
    core_fields = [
        field
        for run in case["runs"]
        for field in run["disagreement_fields"]
        if field != "assessment_evidence"
    ]
    evidence_fields = [
        field
        for run in case["runs"]
        for field in run["disagreement_fields"]
        if field == "assessment_evidence"
    ]
    core_disagreement = (
        case["direction_agreement"] is False or bool(core_fields)
    )
    return {
        "case_id": case["case_id"],
        "directions": {
            source: data["direction"]
            for source, data in case["sources"].items()
            if data["direction"] is not None
        },
        "runs": [
            {
                "run_id": run["run_id"],
                "disagreement_fields": run["disagreement_fields"],
            }
            for run in case["runs"]
        ],
        "core_disagreement": core_disagreement,
        "evidence_only": bool(evidence_fields) and not core_disagreement,
    }


def _root_signature(root_causes: list[dict[str, Any]]) -> tuple:
    return tuple(
        sorted(
            root.get("label")
            for root in root_causes
        )
    )


def _first_fault_signature(root_causes: list[dict[str, Any]]) -> tuple:
    return tuple(
        sorted(
            root.get("first_fault_event_id")
            for root in root_causes
            if root.get("first_fault_event_id") is not None
        )
    )


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _ratio(agree: int, total: int) -> dict[str, Any]:
    return {
        "agree": agree,
        "total": total,
        "rate": round(agree / total, 4) if total else None,
    }


def _ratio_text(value: Mapping[str, Any]) -> str:
    if not value["total"]:
        return "-"
    return f"{value['agree']}/{value['total']} ({value['rate']:.1%})"


def _direction_text(value: str | None) -> str:
    if value is None:
        return "-"
    return f"`{value}`"
