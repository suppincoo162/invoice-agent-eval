from __future__ import annotations

from decimal import Decimal
from typing import Any

from invoice_eval.models import Event, RootCause, Run


COMPARED_SUBMIT_FIELDS = (
    "buyer_id",
    "item_id",
    "invoice_task_type",
    "amounts",
    "line_count",
    "line_items",
    "original_invoice_id",
)


def find_submit_argument_root_causes(
    run: Run,
) -> tuple[RootCause, ...]:
    confirmation = _first_event(run, "CONFIRM_INVOICE")
    submit = _first_event(run, "SUBMIT_INVOICE")
    if confirmation is None or submit is None:
        return ()

    confirmation_output = (
        _as_object(confirmation.raw.get("observed_output")) or {}
    )
    if confirmation_output.get("invoice_confirmed") is not True:
        return ()
    preview = _as_object(confirmation_output, "preview")
    submitted = _as_object(submit.raw.get("observed_input"))
    if preview is None or submitted is None:
        return ()

    changed = [
        field
        for field in COMPARED_SUBMIT_FIELDS
        if _canonical(preview.get(field)) != _canonical(submitted.get(field))
    ]
    if not changed:
        return ()
    return (
        RootCause(
            label="TOOL_ARGUMENT_ERROR",
            first_fault_event_id=submit.event_id,
            evidence_event_ids=(confirmation.event_id, submit.event_id),
            explanation=(
                "正式提交参数与已确认预览不一致："
                + "、".join(changed)
                + "。"
            ),
        ),
    )


def _canonical(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return tuple(sorted((_canonical(item) for item in value), key=repr))
    if isinstance(value, dict):
        return tuple(
            sorted(
                (key, _canonical(item))
                for key, item in value.items()
            )
        )
    return repr(value)


def _first_event(run: Run, step_id: str) -> Event | None:
    return next(
        (event for event in run.events if event.step_id == step_id),
        None,
    )


def _as_object(
    value: Any, nested_key: str | None = None
) -> dict[str, Any] | None:
    if value is None:
        return None
    if nested_key is not None:
        if not isinstance(value, dict):
            return None
        value = value.get(nested_key)
    return value if isinstance(value, dict) else None
