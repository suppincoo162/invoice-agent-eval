from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from invoice_eval.models import Case, Event, Run


MONEY_QUANTUM = Decimal("0.01")
AMOUNT_KEYS = (
    "exclusive_amount",
    "tax_amount",
    "inclusive_amount",
)


@dataclass(frozen=True)
class AmountFinding:
    rule_id: str
    actor: str
    root_cause_label: str
    first_fault_event_id: str
    evidence_event_ids: tuple[str, ...]
    explanation: str


def calculate_amounts(
    amount_value: Decimal | int | float | str,
    amount_basis: str,
    configured_rate: Decimal | int | float | str,
) -> dict[str, Decimal]:
    amount = _money(amount_value)
    rate = Decimal(str(configured_rate))

    if amount_basis == "tax_exclusive":
        exclusive = amount
        tax = (exclusive * rate).quantize(
            MONEY_QUANTUM, rounding=ROUND_HALF_UP
        )
        inclusive = (exclusive + tax).quantize(
            MONEY_QUANTUM, rounding=ROUND_HALF_UP
        )
    elif amount_basis == "tax_inclusive":
        inclusive = amount
        exclusive = (inclusive / (Decimal("1") + rate)).quantize(
            MONEY_QUANTUM, rounding=ROUND_HALF_UP
        )
        tax = (inclusive - exclusive).quantize(
            MONEY_QUANTUM, rounding=ROUND_HALF_UP
        )
    else:
        raise ValueError(f"Unsupported amount_basis: {amount_basis!r}")

    return {
        "exclusive_amount": exclusive,
        "tax_amount": tax,
        "inclusive_amount": inclusive,
    }


def find_amount_findings(case: Case, run: Run) -> tuple[AmountFinding, ...]:
    """Find amount-basis and amount-calculation errors in one run.

    Missing reference or observed amount fields are intentionally not reported
    as amount violations. T-014's evidence layer decides whether those gaps make
    the run unscorable.
    """

    reference = _as_object(case.raw.get("reference_result"))
    collection = _first_event(run, "COLLECT_INVOICE_DATA")
    if reference is None or collection is None:
        return ()

    expected_basis = reference.get("amount_basis")
    reference_amount = reference.get("amount_value")

    observed = _as_object(collection.raw.get("observed_output"))
    if observed is None:
        return ()

    # 题内没有给出金额（reference_result.amount_value 为 null），Agent 却填入了
    # 具体数值 ⇒ 编造。官方规则：缺少必要信息必须追问，不得猜测。
    if reference_amount is None and observed.get("amount_value") is not None:
        propagation = _first_event(
            run, "CONFIRM_INVOICE"
        ) or _first_event(run, "SUBMIT_INVOICE")
        fabricated = _decimal_text(_money(observed["amount_value"]))
        return (
            AmountFinding(
                rule_id="AMOUNT_FABRICATION_CHECK",
                actor="AGENT",
                root_cause_label="FIELD_FABRICATION",
                first_fault_event_id=collection.event_id,
                evidence_event_ids=(
                    (collection.event_id, propagation.event_id)
                    if propagation is not None
                    else (collection.event_id,)
                ),
                explanation=(
                    f"题内未提供金额，Agent 自行填入 {fabricated}，"
                    f"属编造而非追问。"
                ),
            ),
        )

    # 题内未指定含税/不含税口径（reference amount_basis=null），Agent 却自行
    # 选定口径并推进 ⇒ 猜测口径。官方规则：语义不明必须追问。
    if not isinstance(expected_basis, str):
        observed_basis = observed.get("amount_basis")
        asked = _first_event(run, "WAIT_USER_SUPPLEMENT")
        if isinstance(observed_basis, str) and asked is None:
            propagation = _first_event(
                run, "CONFIRM_INVOICE"
            ) or _first_event(run, "SUBMIT_INVOICE")
            return (
                AmountFinding(
                    rule_id="AMOUNT_BASIS_ASSUMED",
                    actor="AGENT",
                    root_cause_label="AMOUNT_BASIS",
                    first_fault_event_id=collection.event_id,
                    evidence_event_ids=(
                        (collection.event_id, propagation.event_id)
                        if propagation is not None
                        else (collection.event_id,)
                    ),
                    explanation=(
                        "题内未指定含税/不含税口径，Agent 自行判定为 "
                        f"{observed_basis!r} 并继续推进，未请求用户补充。"
                    ),
                ),
            )
        return ()

    if reference_amount is None:
        return ()

    observed_basis = observed.get("amount_basis")
    observed_amounts = _decimal_mapping(observed.get("computed_amounts"))
    if not isinstance(observed_basis, str) or observed_amounts is None:
        return ()

    propagation = _propagation_event(run, observed_amounts)
    evidence = (
        (collection.event_id, propagation.event_id)
        if propagation is not None
        else (collection.event_id,)
    )

    if observed_basis != expected_basis:
        return (
            AmountFinding(
                rule_id="AMOUNT_BASIS_CHECK",
                actor="AGENT",
                root_cause_label="AMOUNT_BASIS",
                first_fault_event_id=collection.event_id,
                evidence_event_ids=evidence,
                explanation=(
                    f"题内目标金额口径为 {expected_basis!r}，"
                    f"实际输出为 {observed_basis!r}。"
                ),
            ),
        )

    observed_amount = observed.get("amount_value")
    if observed_amount is None:
        return ()
    try:
        if _money(observed_amount) != _money(reference_amount):
            # A different source amount is an input/update attribution problem
            # (for example CONTEXT_UPDATE), not an arithmetic error.
            return ()
    except (TypeError, ValueError):
        return ()

    expected_amounts = _expected_amounts(
        case,
        reference,
        expected_basis,
    )
    if expected_amounts is None or observed_amounts == expected_amounts:
        return ()

    changed = ", ".join(
        (
            f"{key} 应为 {_decimal_text(expected_amounts[key])}，"
            f"实际为 {_decimal_text(observed_amounts[key])}"
        )
        for key in AMOUNT_KEYS
        if observed_amounts[key] != expected_amounts[key]
    )
    return (
        AmountFinding(
            rule_id="AMOUNT_CALCULATION_CHECK",
            actor="AGENT",
            root_cause_label="AMOUNT_CALCULATION",
            first_fault_event_id=collection.event_id,
            evidence_event_ids=evidence,
            explanation=f"金额计算不一致：{changed}。",
        ),
    )


def _expected_amounts(
    case: Case,
    reference: dict[str, Any],
    amount_basis: str,
) -> dict[str, Decimal] | None:
    configured_rate = _configured_rate(case, reference)
    if configured_rate is None:
        return _decimal_mapping(reference.get("expected_amounts"))
    return calculate_amounts(
        reference["amount_value"],
        amount_basis,
        configured_rate,
    )


def _configured_rate(
    case: Case, reference: dict[str, Any]
) -> Decimal | None:
    item_id = reference.get("item_id")
    context = _as_object(case.raw.get("context"))
    if not isinstance(item_id, str) or context is None:
        return None

    candidates = context.get("item_candidates")
    if not isinstance(candidates, list):
        return None

    matching_rates = [
        candidate.get("configured_rate")
        for candidate in candidates
        if isinstance(candidate, dict)
        and candidate.get("item_id") == item_id
        and candidate.get("configured_rate") is not None
    ]
    if len(matching_rates) != 1:
        return None
    return Decimal(str(matching_rates[0]))


def _propagation_event(
    run: Run, observed_amounts: dict[str, Decimal]
) -> Event | None:
    for step_id in ("SUBMIT_INVOICE", "CONFIRM_INVOICE"):
        event = _first_event(run, step_id)
        if event is None:
            continue
        if step_id == "SUBMIT_INVOICE":
            amounts_container = _as_object(
                event.raw.get("observed_input")
            )
        else:
            output = _as_object(event.raw.get("observed_output"))
            amounts_container = _as_object(output, "preview")
        if amounts_container is None:
            continue
        amounts = _decimal_mapping(amounts_container.get("amounts"))
        if amounts == observed_amounts:
            return event
    return None


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


def _decimal_mapping(value: Any) -> dict[str, Decimal] | None:
    if not isinstance(value, dict):
        return None
    try:
        return {key: _money(value[key]) for key in AMOUNT_KEYS}
    except (KeyError, TypeError, ValueError):
        return None


def _money(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("Boolean is not a valid amount")
    amount = Decimal(str(value))
    if not amount.is_finite():
        raise ValueError("Amount must be finite")
    return amount.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _decimal_text(value: Decimal) -> str:
    return f"{value:.2f}"
