from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Any

from invoice_eval.models import Case, Event, RootCause, Run


TASK_TYPE_LABELS = {
    "RED": "红票",
    "BATCH": "批量开票",
}


def find_task_type_root_causes(
    case: Case, run: Run
) -> tuple[RootCause, ...]:
    reference = _as_object(case.raw.get("reference_result")) or {}
    expected_type = reference.get("invoice_task_type")
    if expected_type not in TASK_TYPE_LABELS:
        return ()

    parse_event = _first_event(run, "PARSE_INTENT")
    if parse_event is None:
        return ()
    parsed = _as_object(parse_event.raw.get("observed_output")) or {}
    if parsed.get("invoice_task_type") != expected_type:
        downstream = _first_event_after(
            run,
            parse_event,
            {"CONFIRM_INVOICE", "SUBMIT_INVOICE", "FAIL_TASK", "CANCEL_TASK"},
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
                explanation=(
                    f"任务应为{TASK_TYPE_LABELS[expected_type]}，"
                    f"实际识别为 {parsed.get('invoice_task_type')!r}。"
                ),
            ),
        )

    confirmation = _first_event(run, "CONFIRM_INVOICE")
    if confirmation is not None:
        output = _as_object(confirmation.raw.get("observed_output")) or {}
        preview = _as_object(output, "preview") or {}
        if preview.get("invoice_task_type") != expected_type:
            return (
                RootCause(
                    label="INTENT_CLASSIFICATION",
                    first_fault_event_id=confirmation.event_id,
                    evidence_event_ids=(confirmation.event_id,),
                    explanation=(
                        "意图识别正确，但预览中的 invoice_task_type "
                        "发生漂移。"
                    ),
                ),
            )
    return ()


def find_red_invoice_root_causes(
    case: Case, run: Run
) -> tuple[RootCause, ...]:
    reference = _as_object(case.raw.get("reference_result")) or {}
    if reference.get("invoice_task_type") != "RED":
        return ()

    context = _as_object(case.raw.get("context")) or {}
    expected_original = context.get("original_invoice_id")
    collection = _first_event(run, "COLLECT_INVOICE_DATA")
    if collection is None:
        return ()
    observed = _as_object(collection.raw.get("observed_output")) or {}
    observed_original = observed.get("original_invoice_id")

    if isinstance(expected_original, str) and expected_original:
        if observed_original != expected_original:
            propagation = _first_event_after(
                run,
                collection,
                {"CONFIRM_INVOICE", "SUBMIT_INVOICE"},
            )
            return (
                RootCause(
                    label="FIELD_FABRICATION",
                    first_fault_event_id=collection.event_id,
                    evidence_event_ids=(
                        (collection.event_id, propagation.event_id)
                        if propagation is not None
                        else (collection.event_id,)
                    ),
                    explanation=(
                        "红票原票引用缺失或被替换，未保持用户提供的"
                        "原票编号。"
                    ),
                ),
            )

        confirmation = _first_event(run, "CONFIRM_INVOICE")
        if confirmation is not None:
            output = _as_object(confirmation.raw.get("observed_output")) or {}
            preview = _as_object(output, "preview") or {}
            if preview.get("original_invoice_id") != expected_original:
                return (
                    RootCause(
                        label="FIELD_FABRICATION",
                        first_fault_event_id=confirmation.event_id,
                        evidence_event_ids=(confirmation.event_id,),
                        explanation=(
                            "采集阶段原票引用正确，但预览中的原票编号"
                            "发生漂移。"
                        ),
                    ),
                )
        return ()

    missing_required = _string_set(
        context.get("required_missing_fields")
    )
    if "original_invoice_id" not in missing_required:
        return ()

    requested = _as_object(
        collection.raw.get("observed_output")
    ) or {}
    missing_fields = _string_set(requested.get("missing_fields"))
    supplement = _first_event(run, "WAIT_USER_SUPPLEMENT")
    if supplement is not None:
        supplement_output = (
            _as_object(supplement.raw.get("observed_output")) or {}
        )
        requested_fields = _string_set(
            supplement_output.get("requested_fields")
        )
        if (
            "original_invoice_id" in missing_fields
            and "original_invoice_id" in requested_fields
        ):
            return ()

    downstream = _first_event_after(
        run,
        collection,
        {"WAIT_USER_SUPPLEMENT", "CONFIRM_INVOICE", "SUBMIT_INVOICE"},
    )
    evidence = (
        (collection.event_id, downstream.event_id)
        if downstream is not None
        else (collection.event_id,)
    )
    return (
        RootCause(
            label="FIELD_FABRICATION",
            first_fault_event_id=collection.event_id,
            evidence_event_ids=evidence,
            explanation=(
                "红票所需原票编号缺失，Agent 未请求补充而继续生成"
                "开票内容。"
            ),
        ),
    )


def find_batch_root_causes(
    case: Case, run: Run
) -> tuple[RootCause, ...]:
    reference = _as_object(case.raw.get("reference_result")) or {}
    if reference.get("invoice_task_type") != "BATCH":
        return ()

    expected_items = _line_items(reference.get("expected_line_items"))
    if expected_items is None:
        return ()
    expected_count = reference.get("expected_line_count")

    for event in run.events:
        if event.step_id == "COLLECT_INVOICE_DATA":
            container = _as_object(event.raw.get("observed_output"))
        elif event.step_id == "CONFIRM_INVOICE":
            output = _as_object(event.raw.get("observed_output"))
            container = _as_object(output, "preview")
        else:
            continue
        if container is None:
            continue

        observed_items = _line_items(container.get("line_items"))
        observed_count = container.get("line_count")
        if (
            observed_items == expected_items
            and observed_count == expected_count
        ):
            continue

        downstream = _first_event_after(
            run, event, {"CONFIRM_INVOICE", "SUBMIT_INVOICE"}
        )
        evidence = (
            (event.event_id, downstream.event_id)
            if downstream is not None
            else (event.event_id,)
        )
        return (
            RootCause(
                label="MULTI_ITEM_OMISSION",
                first_fault_event_id=event.event_id,
                evidence_event_ids=evidence,
                explanation=(
                    "批量任务的 line_items 或 line_count 与题内要求不一致。"
                ),
            ),
        )
    return ()


def _line_items(value: Any) -> tuple[tuple[str, Decimal], ...] | None:
    if not isinstance(value, list):
        return None
    items: list[tuple[str, Decimal]] = []
    try:
        for raw_item in value:
            if not isinstance(raw_item, dict):
                return None
            item_id = raw_item.get("item_id")
            amount = raw_item.get("exclusive_amount")
            if not isinstance(item_id, str) or amount is None:
                return None
            items.append((item_id, Decimal(str(amount))))
    except (TypeError, ValueError):
        return None
    return tuple(sorted(items))


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


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


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
