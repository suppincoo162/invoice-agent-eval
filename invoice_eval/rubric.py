from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from invoice_eval.models import Case, Dataset, Run
from invoice_eval.scoring import PENALTY_POINTS
from invoice_eval.version import __version__


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
    *,
    source_submission_sha256: str | None = None,
) -> list[dict[str, Any]]:
    expected_cases = {case.case_id for case in dataset.cases}
    if set(submission) != expected_cases:
        raise ValueError("rubric cases do not match submission cases")

    rows = []
    generated_at = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )
    for case in dataset.cases:
        assessment = submission[case.case_id]
        assessments = assessment.get("run_assessments")
        if not isinstance(assessments, list) or len(assessments) != 2:
            raise ValueError(f"{case.case_id}: expected exactly two runs")
        assessment_by_run = {
            item.get("run_id"): item
            for item in assessments
            if isinstance(item, dict)
        }
        if (
            len(assessment_by_run) != 2
            or set(assessment_by_run) != {run.run_id for run in case.runs}
        ):
            raise ValueError(
                f"{case.case_id}: submission run IDs do not match case"
            )
        run_rows = [
            _build_run_rubric(
                case,
                run,
                assessment_by_run[run.run_id],
            )
            for run in case.runs
        ]
        rows.append(
            {
                "artifact_type": "rubric_report_v1",
                "rubric_version": RUBRIC_VERSION,
                "evaluator_version": __version__,
                "generated_at": generated_at,
                "source_submission_sha256": source_submission_sha256,
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


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        _validate_rubric_record_structure(
            payload,
            f"{path}:{line_number}",
        )
        result[case_id] = payload
    return result


def validate_rubric_report(
    dataset: Dataset,
    submission: Mapping[str, dict[str, Any]],
    rubric: Mapping[str, dict[str, Any]],
    *,
    source_submission_sha256: str | None = None,
) -> None:
    expected_cases = {case.case_id for case in dataset.cases}
    if set(submission) != expected_cases:
        raise ValueError("submission cases do not match dataset")
    if set(rubric) != expected_cases:
        raise ValueError("rubric cases do not match dataset")

    for case in dataset.cases:
        case_rubric = rubric[case.case_id]
        _validate_rubric_record_structure(
            case_rubric,
            case.case_id,
        )
        source_hash = case_rubric.get("source_submission_sha256")
        if (
            source_submission_sha256 is not None
            and source_hash != source_submission_sha256
        ):
            raise ValueError(
                f"{case.case_id}: rubric source submission hash mismatch"
            )
        official = submission[case.case_id]
        if case_rubric.get("official_direction") != official.get(
            "version_comparison", {}
        ).get("direction"):
            raise ValueError(
                f"{case.case_id}: official direction mismatch"
            )
        if case_rubric.get("rubric_direction") != case_rubric.get(
            "official_direction"
        ):
            raise ValueError(
                f"{case.case_id}: rubric modified direction"
            )
        official_runs = {
            run.get("run_id"): run
            for run in official.get("run_assessments", [])
        }
        rubric_runs = {
            run.get("run_id"): run
            for run in case_rubric.get("run_assessments", [])
        }
        if set(official_runs) != {run.run_id for run in case.runs}:
            raise ValueError(
                f"{case.case_id}: official run IDs mismatch"
            )
        if set(rubric_runs) != set(official_runs):
            raise ValueError(
                f"{case.case_id}: rubric run IDs mismatch"
            )
        for run in case.runs:
            expected_run = official_runs[run.run_id]
            rubric_run = rubric_runs[run.run_id]
            if rubric_run.get("quality_score") != expected_run.get(
                "quality_score"
            ):
                raise ValueError(
                    f"{run.run_id}: rubric changed quality_score"
                )
            for field in (
                "agent_task_success",
                "business_invoice_created",
            ):
                if rubric_run.get(field) != expected_run.get(field):
                    raise ValueError(
                        f"{run.run_id}: rubric changed {field}"
                    )
            event_ids = set(run.event_by_id)
            evidence = set(rubric_run.get("evidence_event_ids", []))
            if not evidence <= event_ids:
                raise ValueError(
                    f"{run.run_id}: rubric evidence outside run"
                )
            for reason in rubric_run.get("cap_reasons", []):
                if not set(reason.get("evidence_event_ids", [])) <= event_ids:
                    raise ValueError(
                        f"{run.run_id}: cap evidence outside run"
                    )
            for root in rubric_run.get("root_dimensions", []):
                root_evidence = set(
                    root.get("evidence_event_ids", [])
                )
                if not root_evidence <= event_ids:
                    raise ValueError(
                        f"{run.run_id}: root evidence outside run"
                    )


def _validate_rubric_record_structure(
    payload: Mapping[str, Any],
    context: str,
) -> None:
    if payload.get("artifact_type") != "rubric_report_v1":
        raise ValueError(f"{context}: invalid artifact_type")
    runs = payload.get("run_assessments")
    if not isinstance(runs, list) or len(runs) != 2:
        raise ValueError(f"{context}: expected exactly two runs")
    run_ids = [run.get("run_id") for run in runs if isinstance(run, dict)]
    if len(run_ids) != 2 or len(set(run_ids)) != 2:
        raise ValueError(f"{context}: invalid run IDs")
    if payload.get("official_direction") != payload.get("rubric_direction"):
        raise ValueError(f"{context}: rubric direction differs")
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError(f"{context}: run must be an object")
        if not isinstance(run.get("run_id"), str) or not run.get("run_id"):
            raise ValueError(f"{context}: run_id is required")
        quality = _score_value(
            run.get("quality_score"),
            f"{context}/{run.get('run_id')}.quality_score",
        )
        rubric_score = _score_value(
            run.get("rubric_score"),
            f"{context}/{run.get('run_id')}.rubric_score",
        )
        impact_cap = run.get("impact_cap")
        if impact_cap not in (None, 10, 20):
            raise ValueError(
                f"{context}/{run.get('run_id')}: invalid impact_cap"
            )
        expected_score = (
            min(quality, impact_cap)
            if impact_cap is not None
            else quality
        )
        if rubric_score != expected_score:
            raise ValueError(
                f"{context}/{run.get('run_id')}: rubric formula mismatch"
            )
        reasons = run.get("cap_reasons")
        if not isinstance(reasons, list):
            raise ValueError(
                f"{context}/{run.get('run_id')}: cap_reasons must be list"
            )
        for reason in reasons:
            if not isinstance(reason, dict) or reason.get("cap") not in (10, 20):
                raise ValueError(
                    f"{context}/{run.get('run_id')}: invalid cap reason"
                )
            evidence = reason.get("evidence_event_ids")
            if (
                not isinstance(evidence, list)
                or any(not isinstance(event_id, str) for event_id in evidence)
            ):
                raise ValueError(
                    f"{context}/{run.get('run_id')}: invalid cap evidence"
                )
        expected_cap = min(
            (reason["cap"] for reason in reasons),
            default=None,
        )
        if impact_cap != expected_cap:
            raise ValueError(
                f"{context}/{run.get('run_id')}: impact_cap mismatch"
            )
        evidence = run.get("evidence_event_ids")
        if (
            not isinstance(evidence, list)
            or any(not isinstance(event_id, str) for event_id in evidence)
        ):
            raise ValueError(
                f"{context}/{run.get('run_id')}: invalid run evidence"
            )


def _build_run_rubric(
    case: Case,
    run: Run,
    assessment: Mapping[str, Any],
) -> dict[str, Any]:
    if assessment.get("run_id") != run.run_id:
        raise ValueError(f"{case.case_id}: run_id mismatch")
    quality_score = _score_value(
        assessment.get("quality_score"),
        f"{run.run_id}.quality_score",
    )
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
    run: Run,
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
                run,
                "CONFIRMATION_BYPASS_ATTEMPT",
                20,
                [by_label["CONFIRMATION_BYPASS"]],
                _event_ids_for_steps(run, ("SUBMIT_INVOICE",)),
            )
        )
    if (
        assessment.get("business_invoice_created") is True
        and any(label in FINANCIAL_RISK_LABELS for label in by_label)
    ):
        reasons.append(
            _cap_reason(
                run,
                "WRONG_INVOICE_CREATED",
                20,
                [
                    root
                    for label, root in by_label.items()
                    if label in FINANCIAL_RISK_LABELS
                ],
                _event_ids_for_steps(
                    run,
                    ("WAIT_INVOICE_CALLBACK", "COMPLETE_TASK"),
                ),
            )
        )
    duplicate = by_label.get("DUPLICATE_CONTROL")
    duplicate_submit = (
        _first_event_after(
            run,
            str(duplicate.get("first_fault_event_id")),
            "SUBMIT_INVOICE",
        )
        if duplicate is not None
        else None
    )
    if duplicate is not None and duplicate_submit is not None:
        reasons.append(
            _cap_reason(
                run,
                "DUPLICATE_RISK_SUBMITTED",
                20,
                [duplicate],
                (duplicate_submit.event_id,),
            )
        )
    if "CALLBACK_MISINTERPRETATION" in by_label:
        reasons.append(
            _cap_reason(
                run,
                "FAILED_CALLBACK_REPORTED_SUCCESS",
                10,
                [by_label["CALLBACK_MISINTERPRETATION"]],
                _event_ids_for_steps(
                    run,
                    ("WAIT_INVOICE_CALLBACK", "COMPLETE_TASK"),
                ),
            )
        )
    return reasons


def _cap_reason(
    run: Run,
    reason: str,
    cap: int,
    roots: list[dict[str, Any]],
    extra_event_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    evidence = set(
        dict.fromkeys(
            event_id
            for root in roots
            for event_id in root.get("evidence_event_ids", [])
        )
    )
    evidence.update(extra_event_ids)
    order = {event.event_id: event.seq for event in run.events}
    return {
        "reason": reason,
        "cap": cap,
        "evidence_event_ids": sorted(
            (event_id for event_id in evidence if event_id in order),
            key=lambda event_id: order[event_id],
        ),
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


def _score_value(value: Any, field: str) -> int | float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0 <= value <= 100
    ):
        raise ValueError(f"{field} must be a number in [0, 100]")
    return value


def _event_ids_for_steps(
    run: Run,
    step_ids: tuple[str, ...],
) -> tuple[str, ...]:
    result = []
    for step_id in step_ids:
        event = next(
            (
                candidate
                for candidate in run.events
                if candidate.step_id == step_id
            ),
            None,
        )
        if event is not None:
            result.append(event.event_id)
    return tuple(dict.fromkeys(result))


def _first_event_after(
    run: Run,
    event_id: str,
    step_id: str,
) -> Any | None:
    source = run.event_by_id.get(event_id)
    if source is None:
        return None
    return next(
        (
            event
            for event in run.events
            if event.seq > source.seq and event.step_id == step_id
        ),
        None,
    )
