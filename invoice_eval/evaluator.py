from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from invoice_eval.amounts import find_amount_findings
from invoice_eval.callbacks import find_callback_root_causes
from invoice_eval.confirmation import find_confirmation_root_causes
from invoice_eval.conversation import find_context_update_root_causes
from invoice_eval.entities import (
    find_buyer_root_causes,
    find_product_root_causes,
)
from invoice_eval.invoice_types import (
    find_batch_root_causes,
    find_red_invoice_root_causes,
    find_task_type_root_causes,
)
from invoice_eval.models import Case, Event, RootCause, Run
from invoice_eval.risk_controls import (
    find_cancellation_root_causes,
    find_duplicate_control_root_causes,
    find_submit_timeout_root_causes,
)
from invoice_eval.scoring import build_penalties, calculate_quality_score
from invoice_eval.submission import find_submit_argument_root_causes
from invoice_eval.tooling import find_protective_rejections
from invoice_eval.workflow import (
    Workflow,
    WorkflowFinding,
    find_workflow_transition_findings,
)


IMPROVEMENT_BY_LABEL = {
    "AMOUNT_BASIS": "在采集阶段固定用户指定的含税/不含税口径，并增加口径回归用例。",
    "AMOUNT_CALCULATION": "使用 Decimal 复算金额三元组，并在预览前校验舍入结果。",
    "CONFIRMATION_BYPASS": "在调用 invoice.submit 前强制校验本次任务确认记录。",
    "DUPLICATE_CONTROL": "保留规则工具的重复风险结果，并在任何提交前阻断。",
    "CALLBACK_MISINTERPRETATION": "仅依据明确回调更新开票结果，失败回调不得改写为成功。",
    "TOOL_ERROR_HANDLING": "状态不明时停止自动重试并转人工核查。",
    "TOOL_ARGUMENT_ERROR": "提交参数必须直接复制已确认预览并做逐字段比较。",
    "INTENT_CLASSIFICATION": "保留取消、开票和红票等任务意图的任务级回归样例。",
    "FIELD_FABRICATION": "缺少必要字段时必须请求用户补充，不得产生猜测值。",
    "ENTITY_RESOLUTION": "存在多个候选时必须等待用户消歧，不得擅自选择。",
    "PRODUCT_MATCH": "商品匹配必须保留用户所指项目，并增加相似名称回归样例。",
    "CONTEXT_UPDATE": "多轮修改后必须使用最新值，并为已被覆盖的旧值增加回归样例。",
}


@dataclass(frozen=True)
class AssessedRun:
    payload: dict[str, Any]
    unscorable: bool


def evaluate_case(case: Case, workflow: Workflow) -> dict[str, Any]:
    assessed_runs = tuple(_assess_run(case, run, workflow) for run in case.runs)
    if len(assessed_runs) != 2:
        raise ValueError(
            f"Case {case.case_id!r} must contain exactly 2 runs"
        )

    baseline, candidate = assessed_runs
    direction, recommendation, reason = _compare_runs(
        baseline, candidate
    )
    return {
        "case_id": case.case_id,
        "run_assessments": [
            result.payload for result in assessed_runs
        ],
        "version_comparison": {
            "direction": direction,
            "release_recommendation": recommendation,
            "reason": reason,
        },
    }


def _assess_run(
    case: Case, run: Run, workflow: Workflow
) -> AssessedRun:
    amount_findings = find_amount_findings(case, run)
    root_causes = [
        RootCause(
            label=finding.root_cause_label,
            first_fault_event_id=finding.first_fault_event_id,
            evidence_event_ids=finding.evidence_event_ids,
            explanation=finding.explanation,
            actor=finding.actor,
        )
        for finding in amount_findings
    ]
    root_causes.extend(find_confirmation_root_causes(case, run))
    root_causes.extend(find_duplicate_control_root_causes(case, run))
    root_causes.extend(find_cancellation_root_causes(case, run))
    root_causes.extend(find_submit_timeout_root_causes(run))
    root_causes.extend(find_task_type_root_causes(case, run))
    root_causes.extend(find_red_invoice_root_causes(case, run))
    root_causes.extend(find_batch_root_causes(case, run))
    root_causes.extend(find_buyer_root_causes(case, run))
    root_causes.extend(find_product_root_causes(case, run))
    root_causes.extend(find_callback_root_causes(run))
    root_causes.extend(find_submit_argument_root_causes(run))
    root_causes.extend(find_context_update_root_causes(case, run))

    workflow_findings = find_workflow_transition_findings(run, workflow)
    protective_rejections = find_protective_rejections(run)
    penalties = build_penalties(tuple(root_causes))

    reference = _as_object(case.raw.get("reference_result")) or {}
    invoice_created = run.raw.get("invoice_created")
    invoice_field_valid = isinstance(invoice_created, bool)
    business_invoice_created = invoice_created if invoice_field_valid else False
    reference_complete = (
        reference.get("invoice_should_exist") is not None
        and reference.get("acceptable_snapshot_state") is not None
    )
    invoice_matches = (
        reference_complete
        and business_invoice_created == reference.get("invoice_should_exist")
    )
    state_matches = (
        reference_complete
        and run.raw.get("final_state")
        == reference.get("acceptable_snapshot_state")
    )
    task_success = (
        reference_complete
        and not root_causes
        and not workflow_findings
        and invoice_matches
        and state_matches
        and invoice_field_valid
    )

    unscorable = False
    if not reference_complete and not root_causes and not workflow_findings:
        # 题内目标缺失时不得默认「无所谓」——那是把未知当成功。
        # 按官方口径（缺证据就说不确定）降级为 INSUFFICIENT_EVIDENCE 并标不可评分。
        evidence = _last_event_ids(run)
        root_causes.append(
            RootCause(
                label="INSUFFICIENT_EVIDENCE",
                first_fault_event_id=None,
                evidence_event_ids=evidence,
                explanation=(
                    "Case 的题内目标不完整（reference_result 缺少 "
                    "invoice_should_exist 或 acceptable_snapshot_state），"
                    "无法判定该运行是否达成目标；按证据不足处理。"
                ),
                actor="UNKNOWN",
            )
        )
    elif not task_success and not root_causes:
        evidence = _workflow_evidence(workflow_findings) or _last_event_ids(
            run
        )
        root_causes.append(
            RootCause(
                label="INSUFFICIENT_EVIDENCE",
                first_fault_event_id=None,
                evidence_event_ids=evidence,
                explanation=(
                    "运行结果与题内目标不一致，但现有确定性规则不足以"
                    "归因到更具体的根因。"
                ),
                actor="UNKNOWN",
            )
        )

    if any(
        root.label == "INSUFFICIENT_EVIDENCE" for root in root_causes
    ):
        unscorable = True
        quality_score = 0
    else:
        quality_score = calculate_quality_score(penalties)

    suggestions = _improvement_suggestions(root_causes, workflow_findings)
    evidence_ids = _evidence_ids(run, root_causes, workflow_findings)
    process_parts = [root.explanation for root in root_causes]
    process_parts.extend(finding.message for finding in workflow_findings)
    process_parts.extend(
        rejection.explanation for rejection in protective_rejections
    )
    if not process_parts:
        process_parts.append(
            "未发现确定性流程、金额或确认规则违规。"
        )

    root_payload = [
        {
            "label": root.label,
            "first_fault_event_id": root.first_fault_event_id,
            "evidence_event_ids": list(root.evidence_event_ids),
            "explanation": root.explanation,
        }
        for root in root_causes
    ]
    penalty_payload = [
        {
            "dimension": penalty.dimension,
            "points_deducted": penalty.points_deducted,
            "evidence_event_ids": list(penalty.evidence_event_ids),
            "explanation": penalty.explanation,
        }
        for penalty in penalties
    ]

    invoice_text = "已生成" if business_invoice_created else "未生成"
    if task_success:
        business_result = (
            f"处理结果符合题内目标，发票{invoice_text}。"
        )
        downstream_impact = "无异常传播。"
    else:
        business_result = (
            f"处理结果未完全符合题内目标，发票{invoice_text}。"
        )
        downstream_impact = "；".join(
            part
            for part in (
                *[root.explanation for root in root_causes],
                *[
                    rejection.explanation
                    for rejection in protective_rejections
                ],
            )
        ) or "检测到结果不一致，但无法进一步定位传播。"

    return AssessedRun(
        payload={
            "run_id": run.run_id,
            "agent_task_success": task_success,
            "business_invoice_created": business_invoice_created,
            "quality_score": quality_score,
            "business_result_assessment": business_result,
            "process_assessment": " ".join(process_parts),
            "penalty_items": penalty_payload,
            "root_causes": root_payload,
            "downstream_impact": downstream_impact,
            "improvement_suggestions": suggestions,
            "evidence_event_ids": list(evidence_ids),
            "explanation": _assessment_explanation(
                task_success, root_causes, workflow_findings
            ),
        },
        unscorable=unscorable,
    )


def _compare_runs(
    baseline: AssessedRun, candidate: AssessedRun
) -> tuple[str, str, str]:
    if baseline.unscorable or candidate.unscorable:
        return (
            "insufficient_evidence",
            "investigate",
            "至少一条运行无法可靠评分，当前 Case 不能形成可靠的版本结论。",
        )

    baseline_success = baseline.payload["agent_task_success"]
    candidate_success = candidate.payload["agent_task_success"]
    baseline_score = baseline.payload["quality_score"]
    candidate_score = candidate.payload["quality_score"]

    if baseline_success != candidate_success:
        direction = (
            "baseline_better" if baseline_success else "candidate_better"
        )
        reason = (
            "两个版本的处理正确性不同；该结论仅适用于当前 Case，"
            "不能外推为整体版本结论。"
        )
    elif baseline_score != candidate_score:
        direction = (
            "baseline_better"
            if baseline_score > candidate_score
            else "candidate_better"
        )
        reason = (
            "两个版本的处理正确性相同，但质量分不同；"
            "该结论仅适用于当前 Case。"
        )
    else:
        direction = "equal"
        reason = "两个版本在本 Case 的处理正确性和质量分相同。"

    recommendation = (
        "defer"
        if direction == "baseline_better"
        else "gray"
        if direction in {"candidate_better", "equal"}
        else "investigate"
    )
    return direction, recommendation, reason


def _improvement_suggestions(
    root_causes: list[RootCause],
    workflow_findings: tuple[WorkflowFinding, ...],
) -> list[str]:
    suggestions: list[str] = []
    for root in root_causes:
        suggestion = IMPROVEMENT_BY_LABEL.get(root.label)
        if suggestion and suggestion not in suggestions:
            suggestions.append(suggestion)
    if not suggestions and workflow_findings:
        suggestions.append("检查流程转移并在状态机层阻止非法跳转。")
    if not suggestions and root_causes:
        suggestions.append("补充确定性证据并复核该运行的处理过程。")
    return suggestions


def _evidence_ids(
    run: Run,
    root_causes: list[RootCause],
    workflow_findings: tuple[WorkflowFinding, ...],
) -> tuple[str, ...]:
    evidence = {
        event_id
        for root in root_causes
        for event_id in root.evidence_event_ids
    }
    evidence.update(
        event_id
        for finding in workflow_findings
        for event_id in finding.evidence_event_ids
    )
    if not evidence and not root_causes:
        evidence.update(_key_success_evidence(run))
    order = {event.event_id: event.seq for event in run.events}
    return tuple(sorted(evidence, key=lambda event_id: order[event_id]))


def _key_success_evidence(run: Run) -> tuple[str, ...]:
    priorities = (
        "COLLECT_INVOICE_DATA",
        "CONFIRM_INVOICE",
        "WAIT_INVOICE_CALLBACK",
        "COMPLETE_TASK",
        "FAIL_TASK",
        "CANCEL_TASK",
        "TRANSFER_TO_HUMAN",
    )
    selected: list[Event] = []
    for step_id in priorities:
        event = next(
            (event for event in run.events if event.step_id == step_id),
            None,
        )
        if event is not None:
            selected.append(event)
        if len(selected) == 2:
            break
    if not selected and run.events:
        selected.append(run.events[-1])
    return tuple(event.event_id for event in selected)


def _workflow_evidence(
    findings: tuple[WorkflowFinding, ...],
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            event_id
            for finding in findings
            for event_id in finding.evidence_event_ids
        )
    )


def _last_event_ids(run: Run) -> tuple[str, ...]:
    return (run.events[-1].event_id,) if run.events else ()


def _assessment_explanation(
    task_success: bool,
    root_causes: list[RootCause],
    workflow_findings: tuple[WorkflowFinding, ...],
) -> str:
    if task_success:
        return "未发现违反业务目标或安全流程的确定性证据。"
    labels = [root.label for root in root_causes]
    if labels:
        return "确定性检查发现问题：" + "、".join(labels) + "。"
    if workflow_findings:
        return "检测到非法流程转移，但无法映射到更具体的根因标签。"
    return "运行结果异常，现有证据不足以给出更具体根因。"


def _as_object(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None
