from __future__ import annotations

from typing import Any


def compare_audits(
    deterministic: dict[str, Any],
    llm_review: dict[str, Any],
) -> dict[str, Any]:
    """Compare one deterministic assessment with one LLM blind review."""

    case_id = deterministic.get("case_id")
    if not isinstance(case_id, str) or llm_review.get("case_id") != case_id:
        raise ValueError("Both audit records must have the same case_id.")

    deterministic_runs = {
        assessment["run_id"]: assessment
        for assessment in deterministic.get("run_assessments", [])
    }
    llm_runs = {
        assessment["run_id"]: assessment
        for assessment in llm_review.get("run_assessments", [])
    }
    if set(deterministic_runs) != set(llm_runs):
        raise ValueError("Both audit records must cover the same runs.")

    run_comparisons: list[dict[str, Any]] = []
    for run_id in deterministic_runs:
        left = deterministic_runs[run_id]
        right = llm_runs[run_id]
        left_roots = _core_root_signature(left.get("root_causes", []))
        right_roots = _core_root_signature(right.get("root_causes", []))
        left_root_evidence = _root_evidence(
            left.get("root_causes", [])
        )
        right_root_evidence = _root_evidence(
            right.get("root_causes", [])
        )
        left_evidence = set(left.get("evidence_event_ids", []))
        right_evidence = set(right.get("evidence_event_ids", []))
        run_comparisons.append(
            {
                "run_id": run_id,
                "agent_task_success": _compare_value(
                    left.get("agent_task_success"),
                    right.get("agent_task_success"),
                ),
                "business_invoice_created": _compare_value(
                    left.get("business_invoice_created"),
                    right.get("business_invoice_created"),
                ),
                "root_causes": _compare_value(left_roots, right_roots),
                "root_evidence": _compare_value(
                    left_root_evidence,
                    right_root_evidence,
                ),
                "first_faults": {
                    "deterministic": _first_fault_map(
                        left.get("root_causes", [])
                    ),
                    "llm": _first_fault_map(
                        right.get("root_causes", [])
                    ),
                },
                "evidence_overlap": sorted(
                    left_evidence & right_evidence
                ),
                "evidence_only_deterministic": sorted(
                    left_evidence - right_evidence
                ),
                "evidence_only_llm": sorted(
                    right_evidence - left_evidence
                ),
            }
        )

    deterministic_direction = deterministic.get("version_comparison", {}).get(
        "direction"
    )
    llm_direction = llm_review.get("version_comparison", {}).get(
        "direction"
    )
    direction_comparison = _compare_value(
        deterministic_direction,
        llm_direction,
    )
    core_diagnosis_agree = (
        direction_comparison["agree"]
        and all(
            item["agent_task_success"]["agree"]
            and item["business_invoice_created"]["agree"]
            and item["root_causes"]["agree"]
            for item in run_comparisons
        )
    )
    root_evidence_agree = all(
        item["root_evidence"]["agree"] for item in run_comparisons
    )
    assessment_evidence_agree = all(
        not item["evidence_only_deterministic"]
        and not item["evidence_only_llm"]
        for item in run_comparisons
    )
    return {
        "case_id": case_id,
        "direction": direction_comparison,
        "runs": run_comparisons,
        "summary": {
            "core_diagnosis_agree": core_diagnosis_agree,
            "root_evidence_agree": root_evidence_agree,
            "assessment_evidence_agree": assessment_evidence_agree,
            "fully_agree": (
                core_diagnosis_agree
                and root_evidence_agree
                and assessment_evidence_agree
            ),
        },
    }


def _core_root_signature(root_causes: list[dict[str, Any]]) -> tuple:
    return tuple(
        sorted(
            (
                root.get("label"),
                root.get("first_fault_event_id"),
            )
            for root in root_causes
        )
    )


def _root_evidence(root_causes: list[dict[str, Any]]) -> tuple:
    return tuple(
        sorted(
            (
                root.get("label"),
                tuple(root.get("evidence_event_ids", [])),
            )
            for root in root_causes
        )
    )


def _first_fault_map(root_causes: list[dict[str, Any]]) -> list[dict]:
    return [
        {
            "label": root.get("label"),
            "first_fault_event_id": root.get("first_fault_event_id"),
        }
        for root in root_causes
    ]


def _compare_value(deterministic: Any, llm: Any) -> dict[str, Any]:
    return {
        "deterministic": deterministic,
        "llm": llm,
        "agree": deterministic == llm,
    }
