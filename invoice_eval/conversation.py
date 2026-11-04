from __future__ import annotations

from decimal import Decimal
from typing import Any

from invoice_eval.models import Case, Event, RootCause, Run


def find_context_update_root_causes(
    case: Case, run: Run
) -> tuple[RootCause, ...]:
    context = _as_object(case.raw.get("context")) or {}
    rounds = context.get("conversation_rounds")
    if not isinstance(rounds, list) or not rounds:
        return ()

    expected_amount = (
        _as_object(case.raw.get("reference_result")) or {}
    ).get("amount_value")
    collection = _first_event(run, "COLLECT_INVOICE_DATA")
    if expected_amount is None or collection is None:
        return ()
    observed = _as_object(collection.raw.get("observed_output")) or {}
    observed_amount = observed.get("amount_value")
    if observed_amount is None:
        return ()

    try:
        expected = Decimal(str(expected_amount))
        current = Decimal(str(observed_amount))
    except (TypeError, ValueError):
        return ()
    if current == expected:
        return ()

    rounds_by_number = {
        round_data.get("round"): round_data
        for round_data in rounds
        if isinstance(round_data, dict)
        and isinstance(round_data.get("round"), int)
    }
    superseded_amounts: set[Decimal] = set()
    for round_data in rounds_by_number.values():
        superseded_round = rounds_by_number.get(
            round_data.get("supersedes_round")
        )
        if (
            superseded_round is not None
            and superseded_round.get("exclusive_amount") is not None
        ):
            superseded_amounts.add(
                Decimal(str(superseded_round["exclusive_amount"]))
            )
    if current not in superseded_amounts:
        return ()

    downstream = _first_event_after(
        run,
        collection,
        {"CONFIRM_INVOICE", "SUBMIT_INVOICE"},
    )
    evidence = (
        (collection.event_id, downstream.event_id)
        if downstream is not None
        else (collection.event_id,)
    )
    return (
        RootCause(
            label="CONTEXT_UPDATE",
            first_fault_event_id=collection.event_id,
            evidence_event_ids=evidence,
            explanation=(
                "多轮对话中的金额已被后续轮次覆盖，Agent 仍使用旧金额。"
            ),
        ),
    )


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


def _as_object(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None
