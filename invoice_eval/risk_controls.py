from __future__ import annotations

from typing import Any

from invoice_eval.models import Case, Event, RootCause, Run


def find_duplicate_control_root_causes(
    case: Case, run: Run
) -> tuple[RootCause, ...]:
    validate = _first_event(run, "VALIDATE_DATA")
    if validate is None:
        return ()

    context = _as_object(case.raw.get("context")) or {}
    expected_risks = _string_set(context.get("risk_flags"))
    for call in _tool_calls(validate):
        result = _as_object(call.get("result"))
        if result is not None:
            expected_risks.update(_string_set(result.get("risk_flags")))
    if "DUPLICATE_INVOICE" not in expected_risks:
        return ()

    observed = _as_object(validate.raw.get("observed_output")) or {}
    observed_risks = _string_set(observed.get("risk_flags"))
    violation_at: Event | None = None
    if "DUPLICATE_INVOICE" not in observed_risks:
        violation_at = validate
    elif observed.get("validation_passed") is True:
        violation_at = validate
    elif observed.get("create_allowed") is True:
        violation_at = validate
    else:
        violation_at = _first_event_after(
            run, validate, {"SUBMIT_INVOICE"}
        )

    if violation_at is None:
        return ()

    propagation = _first_event_after(run, violation_at, {"CONFIRM_INVOICE"})
    evidence = (
        (violation_at.event_id, propagation.event_id)
        if propagation is not None
        else (violation_at.event_id,)
    )
    return (
        RootCause(
            label="DUPLICATE_CONTROL",
            first_fault_event_id=violation_at.event_id,
            evidence_event_ids=evidence,
            explanation=(
                "规则工具已返回 DUPLICATE_INVOICE，但 Agent 未保留"
                "阻断结果或仍继续开票流程。"
            ),
        ),
    )


def find_cancellation_root_causes(
    case: Case, run: Run
) -> tuple[RootCause, ...]:
    reference = _as_object(case.raw.get("reference_result")) or {}
    if reference.get("required_action") != "CANCEL":
        return ()

    parse_event = _first_event(run, "PARSE_INTENT")
    if parse_event is None:
        return ()
    parsed = _as_object(parse_event.raw.get("observed_output")) or {}
    if parsed.get("intent") == "CANCEL":
        cancel_event = _first_event(run, "CANCEL_TASK")
        submit_after_cancel = (
            _first_event_after(run, cancel_event, {"SUBMIT_INVOICE"})
            if cancel_event is not None
            else None
        )
        if submit_after_cancel is None:
            return ()
        return (
            RootCause(
                label="CONFIRMATION_BYPASS",
                first_fault_event_id=submit_after_cancel.event_id,
                evidence_event_ids=(
                    cancel_event.event_id,
                    submit_after_cancel.event_id,
                ),
                explanation="用户取消任务后，Agent 仍继续提交开票。",
            ),
        )

    downstream = _first_event_after(
        run,
        parse_event,
        {"SUBMIT_INVOICE", "CANCEL_TASK", "FAIL_TASK"},
    )
    evidence = (
        (parse_event.event_id, downstream.event_id)
        if downstream is not None
        else (parse_event.event_id,)
    )
    return (
        RootCause(
            label="INTENT_CLASSIFICATION",
            first_fault_event_id=parse_event.event_id,
            evidence_event_ids=evidence,
            explanation="用户明确要求取消，但 Agent 将任务意图识别为开票。",
        ),
    )


def find_submit_timeout_root_causes(
    run: Run,
) -> tuple[RootCause, ...]:
    for event in run.events:
        if event.step_id != "SUBMIT_INVOICE":
            continue
        output = _as_object(event.raw.get("observed_output")) or {}
        is_unknown = (
            event.step_status == "TIMED_OUT"
            or output.get("submit_status") == "unknown"
        )
        if not is_unknown:
            continue

        calls = [
            call
            for call in _tool_calls(event)
            if call.get("name") == "invoice.submit"
        ]
        retries = event.raw.get("retry_count")
        retried = (
            len(calls) > 1
            or (isinstance(retries, int) and retries > 0)
        )
        if not retried:
            continue

        downstream = _first_event_after(
            run,
            event,
            {"FAIL_TASK", "TRANSFER_TO_HUMAN", "TIMEOUT_TASK"},
        )
        evidence = (
            (event.event_id, downstream.event_id)
            if downstream is not None
            else (event.event_id,)
        )
        return (
            RootCause(
                label="TOOL_ERROR_HANDLING",
                first_fault_event_id=event.event_id,
                evidence_event_ids=evidence,
                explanation=(
                    "提交结果未知且没有稳定幂等键时重复发起提交，"
                    "存在重复开票风险。"
                ),
            ),
        )
    return ()


def _first_event(run: Run, step_id: str) -> Event | None:
    return next(
        (event for event in run.events if event.step_id == step_id),
        None,
    )


def _first_event_after(
    run: Run, current: Event, step_ids: set[str]
) -> Event | None:
    return next(
        (
            event
            for event in run.events
            if event.seq > current.seq and event.step_id in step_ids
        ),
        None,
    )


def _tool_calls(event: Event) -> list[dict[str, Any]]:
    raw_calls = event.raw.get("tool_calls")
    if not isinstance(raw_calls, list):
        return []
    return [call for call in raw_calls if isinstance(call, dict)]


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def _as_object(
    value: Any, nested_key: str | None = None
) -> Any:
    if value is None:
        return None
    if nested_key is not None:
        if not isinstance(value, dict):
            return None
        return value.get(nested_key)
    return value if isinstance(value, dict) else None
