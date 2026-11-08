from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from invoice_eval.models import Case, Dataset
from invoice_eval.scoring import PENALTY_POINTS


RUBRIC_VERSION = "impact-aware-dual-v1"
DIMENSIONS = (
    "authorization_risk",
    "business_correctness",
    "intent_context",
    "workflow_tools",
    "recovery_terminal",
)
LABEL_DIMENSIONS = {
    "CONFIRMATION_BYPASS": "authorization_risk",
    "DUPLICATE_CONTROL": "authorization_risk",
    "AMOUNT_BASIS": "business_correctness",
    "AMOUNT_CALCULATION": "business_correctness",
    "MULTI_ITEM_OMISSION": "business_correctness",
    "FIELD_FABRICATION": "business_correctness",
    "INTENT_CLASSIFICATION": "intent_context",
    "ENTITY_RESOLUTION": "intent_context",
    "PRODUCT_MATCH": "intent_context",
    "CONTEXT_UPDATE": "intent_context",
    "TOOL_ARGUMENT_ERROR": "workflow_tools",
    "TOOL_ERROR_HANDLING": "workflow_tools",
    "CALLBACK_MISINTERPRETATION": "workflow_tools",
}
FINANCIAL_RISK_LABELS = frozenset(
    {
        "AMOUNT_BASIS",
        "AMOUNT_CALCULATION",
        "MULTI_ITEM_OMISSION",
        "FIELD_FABRICATION",
        "TOOL_ARGUMENT_ERROR",
    }
)


def build_rubric_report(
    dataset: Dataset,
    submission: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    expected_cases = {case.case_id for case in dataset.cases}
    if set(submission) != expected_cases:
        raise ValueError("rubric cases do not match submission cases")

    rows = []
    for case in dataset.cases:
        assessment = submission[case.case_id]
        assessments = assessment.get("run_assessments")
        if not isinstance(assessments, list) or len(assessments) != 2:
            raise ValueError(f"{case.case_id}: expected exactly two runs")
        run_rows = [
            _build_run_rubric(
                case,
                run,
                assessments[index],
            )
            for index, run in enumerate(case.runs)
        ]
        rows.append(
            {
                "artifact_type": "rubric_report_v1",
                "rubric_version": RUBRIC_VERSION,
                "case_id": case.case_id,
                "official_direction": assessment.get(
                    "version_comparison", {}
                ).get("direction"),
                "rubric_direction": assessment.get(
                    "version_comparison", {}
                ).get("direction"),
                "run_assessments": run_rows,
            }
        )
    return rows


def write_rubric_report(
    rows: list[dict[str, Any]],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False) + "\n" for row in rows
        ),
        encoding="utf-8",
    )


def load_rubric_report(path: Path) -> dict[str, dict[str, Any]]:
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
        if payload.get("rubric_version") != RUBRIC_VERSION:
            raise ValueError(
                f"{path}:{line_number}: unsupported rubric_version"
            )
        result[case_id] = payload
    return result


def _build_run_rubric(
    case: Case,
    run: Any,
    assessment: Mapping[str, Any],
) -> dict[str, Any]:
    quality_score = int(assessment.get("quality_score", 0))
    roots = _dedupe_roots(assessment.get("root_causes", []))
    dimensions = {name: 0 for name in DIMENSIONS}
    root_dimensions = []
    for root in roots:
        label = str(root.get("label"))
        dimension = LABEL_DIMENSIONS.get(label)
        points = PENALTY_POINTS.get(label, 0)
        if dimension is None:
            continue
        dimensions[dimension] += points
        root_dimensions.append(
            {
                "label": label,
                "first_fault_event_id": root.get(
                    "first_fault_event_id"
                ),
                "dimension": dimension,
                "points_deducted": points,
                "evidence_event_ids": list(
                    root.get("evidence_event_ids", [])
                ),
            }
        )

    cap_reasons = _impact_cap_reasons(run, assessment, roots)
    impact_cap = (
        min(reason["cap"] for reason in cap_reasons)
        if cap_reasons
        else None
    )
    rubric_score = (
        min(quality_score, impact_cap)
        if impact_cap is not None
        else quality_score
    )
    return {
        "run_id": assessment.get("run_id"),
        "quality_score": quality_score,
        "rubric_score": rubric_score,
        "impact_cap": impact_cap,
        "cap_reasons": cap_reasons,
        "dimension_penalties": dimensions,
        "root_dimensions": root_dimensions,
        "agent_task_success": assessment.get("agent_task_success"),
        "business_invoice_created": assessment.get(
            "business_invoice_created"
        ),
        "evidence_event_ids": list(
            assessment.get("evidence_event_ids", [])
        ),
    }


def _impact_cap_reasons(
    run: Any,
    assessment: Mapping[str, Any],
    roots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    by_label = {
        str(root.get("label")): root
        for root in roots
    }
    if "CONFIRMATION_BYPASS" in by_label:
        reasons.append(
            _cap_reason(
                "CONFIRMATION_BYPASS_ATTEMPT",
                20,
                [by_label["CONFIRMATION_BYPASS"]],
            )
        )
    if (
        assessment.get("business_invoice_created") is True
        and any(label in FINANCIAL_RISK_LABELS for label in by_label)
    ):
        reasons.append(
            _cap_reason(
                "WRONG_INVOICE_CREATED",
                20,
                [
                    root
                    for label, root in by_label.items()
                    if label in FINANCIAL_RISK_LABELS
                ],
            )
        )
    if (
        "DUPLICATE_CONTROL" in by_label
        and any(event.step_id == "SUBMIT_INVOICE" for event in run.events)
    ):
        reasons.append(
            _cap_reason(
                "DUPLICATE_RISK_SUBMITTED",
                20,
                [by_label["DUPLICATE_CONTROL"]],
            )
        )
    if "CALLBACK_MISINTERPRETATION" in by_label:
        reasons.append(
            _cap_reason(
                "FAILED_CALLBACK_REPORTED_SUCCESS",
                10,
                [by_label["CALLBACK_MISINTERPRETATION"]],
            )
        )
    return reasons


def _cap_reason(
    reason: str,
    cap: int,
    roots: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence = list(
        dict.fromkeys(
            event_id
            for root in roots
            for event_id in root.get("evidence_event_ids", [])
        )
    )
    return {
        "reason": reason,
        "cap": cap,
        "evidence_event_ids": evidence,
    }


def _dedupe_roots(value: Any) -> list[dict[str, Any]]:
    roots = value if isinstance(value, list) else []
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for root in roots:
        if not isinstance(root, dict):
            continue
        key = (root.get("label"), root.get("first_fault_event_id"))
        if key in seen:
            continue
        seen.add(key)
        result.append(root)
    return result
