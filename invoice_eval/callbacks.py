from __future__ import annotations

from typing import Any

from invoice_eval.models import Event, RootCause, Run


def find_callback_root_causes(run: Run) -> tuple[RootCause, ...]:
    callback = _first_event(run, "WAIT_INVOICE_CALLBACK")
    if callback is None:
        return ()

    output = _as_object(callback.raw.get("observed_output")) or {}
    callback_status = output.get("callback_status")
    if callback_status != "failed":
        return ()

    completion = _first_event_after(run, callback, "COMPLETE_TASK")
    if completion is None and run.raw.get("final_state") != "SUCCEEDED":
        return ()

    evidence = (
        (callback.event_id, completion.event_id)
        if completion is not None
        else (callback.event_id,)
    )
    return (
        RootCause(
            label="CALLBACK_MISINTERPRETATION",
            first_fault_event_id=callback.event_id,
            evidence_event_ids=evidence,
            explanation="明确失败的回调被 Agent 解释为开票成功。",
        ),
    )


def _first_event(run: Run, step_id: str) -> Event | None:
    return next(
        (event for event in run.events if event.step_id == step_id),
        None,
    )


def _first_event_after(
    run: Run, current: Event, step_id: str
) -> Event | None:
    return next(
        (
            event
            for event in run.events
            if event.seq > current.seq and event.step_id == step_id
        ),
        None,
    )


def _as_object(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None
