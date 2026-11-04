from __future__ import annotations

from typing import Any

from invoice_eval.models import Case, Event, RootCause, Run


def find_buyer_root_causes(
    case: Case, run: Run
) -> tuple[RootCause, ...]:
    reference = _as_object(case.raw.get("reference_result")) or {}
    action = reference.get("required_action")
    if action not in {"ASK_BUYER", "ASK_BUYER_DISAMBIGUATION"}:
        return ()

    collection = _first_event(run, "COLLECT_INVOICE_DATA")
    if collection is None:
        return ()
    observed = _as_object(collection.raw.get("observed_output")) or {}
    observed_buyer = observed.get("buyer_id")
    if observed_buyer is None:
        return ()

    context = _as_object(case.raw.get("context")) or {}
    candidates = context.get("buyer_candidates")
    candidate_ids = {
        candidate.get("buyer_id")
        for candidate in candidates
        if isinstance(candidate, dict)
        and isinstance(candidate.get("buyer_id"), str)
    } if isinstance(candidates, list) else set()

    if action == "ASK_BUYER_DISAMBIGUATION":
        label = "ENTITY_RESOLUTION"
        explanation = "存在多个购方候选，Agent 未等待用户消歧而直接选择。"
    else:
        label = "FIELD_FABRICATION"
        explanation = "用户未提供必需购方，Agent 自行填入不存在的购方。"

    if action == "ASK_BUYER" and observed_buyer in candidate_ids:
        # A single known candidate still cannot substitute for a user-selected
        # required field when the task explicitly asks for buyer input.
        label = "FIELD_FABRICATION"

    downstream = _first_event_after(
        run,
        collection,
        {"CONFIRM_INVOICE", "WAIT_USER_SUPPLEMENT", "SUBMIT_INVOICE"},
    )
    evidence = (
        (collection.event_id, downstream.event_id)
        if downstream is not None
        else (collection.event_id,)
    )
    return (
        RootCause(
            label=label,
            first_fault_event_id=collection.event_id,
            evidence_event_ids=evidence,
            explanation=explanation,
        ),
    )


def find_product_root_causes(
    case: Case, run: Run
) -> tuple[RootCause, ...]:
    reference = _as_object(case.raw.get("reference_result")) or {}
    expected_item = reference.get("item_id")
    if not isinstance(expected_item, str):
        return ()

    collection = _first_event(run, "COLLECT_INVOICE_DATA")
    if collection is not None:
        observed = _as_object(collection.raw.get("observed_output")) or {}
        if observed.get("item_id") != expected_item:
            downstream = _first_event_after(
                run, collection, {"CONFIRM_INVOICE", "SUBMIT_INVOICE"}
            )
            evidence = (
                (collection.event_id, downstream.event_id)
                if downstream is not None
                else (collection.event_id,)
            )
            return (
                RootCause(
                    label="PRODUCT_MATCH",
                    first_fault_event_id=collection.event_id,
                    evidence_event_ids=evidence,
                    explanation=(
                        f"题内商品应为 {expected_item!r}，"
                        f"实际为 {observed.get('item_id')!r}。"
                    ),
                ),
            )

    confirmation = _first_event(run, "CONFIRM_INVOICE")
    if confirmation is not None:
        output = _as_object(confirmation.raw.get("observed_output")) or {}
        preview = _as_object(output, "preview") or {}
        if preview.get("item_id") != expected_item:
            return (
                RootCause(
                    label="PRODUCT_MATCH",
                    first_fault_event_id=confirmation.event_id,
                    evidence_event_ids=(confirmation.event_id,),
                    explanation="采集商品正确，但预览中的商品发生漂移。",
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
