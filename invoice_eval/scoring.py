from __future__ import annotations

from invoice_eval.models import PenaltyItem, RootCause


PENALTY_POINTS = {
    "CONFIRMATION_BYPASS": 50,
    "DUPLICATE_CONTROL": 50,
    "CALLBACK_MISINTERPRETATION": 50,
    "TOOL_ERROR_HANDLING": 50,
    "AMOUNT_BASIS": 30,
    "AMOUNT_CALCULATION": 30,
    "INTENT_CLASSIFICATION": 30,
    "ENTITY_RESOLUTION": 30,
    "FIELD_FABRICATION": 30,
    "PRODUCT_MATCH": 30,
    "MULTI_ITEM_OMISSION": 30,
    "CONTEXT_UPDATE": 30,
    "TOOL_ARGUMENT_ERROR": 30,
}

PENALTY_DIMENSIONS = {
    "AMOUNT_BASIS": "BUSINESS_RESULT",
    "AMOUNT_CALCULATION": "BUSINESS_RESULT",
    "MULTI_ITEM_OMISSION": "BUSINESS_RESULT",
    "CALLBACK_MISINTERPRETATION": "BUSINESS_RESULT",
    "INTENT_CLASSIFICATION": "PROCESS",
    "ENTITY_RESOLUTION": "PROCESS",
    "FIELD_FABRICATION": "PROCESS",
    "PRODUCT_MATCH": "PROCESS",
    "CONTEXT_UPDATE": "PROCESS",
    "TOOL_ARGUMENT_ERROR": "TOOL_CALL",
    "TOOL_ERROR_HANDLING": "TOOL_CALL",
    "CONFIRMATION_BYPASS": "RISK_CONTROL",
    "DUPLICATE_CONTROL": "RISK_CONTROL",
}


def build_penalties(
    root_causes: tuple[RootCause, ...],
) -> tuple[PenaltyItem, ...]:
    seen: set[tuple[str, str | None]] = set()
    penalties: list[PenaltyItem] = []
    for root in root_causes:
        key = (root.label, root.first_fault_event_id)
        if key in seen or root.label == "INSUFFICIENT_EVIDENCE":
            continue
        seen.add(key)
        points = PENALTY_POINTS.get(root.label)
        dimension = PENALTY_DIMENSIONS.get(root.label)
        if points is None or dimension is None:
            continue
        penalties.append(
            PenaltyItem(
                dimension=dimension,
                points_deducted=points,
                evidence_event_ids=root.evidence_event_ids,
                explanation=root.explanation,
            )
        )
    return tuple(penalties)


def calculate_quality_score(
    penalties: tuple[PenaltyItem, ...],
) -> int:
    return max(0, 100 - sum(penalty.points_deducted for penalty in penalties))
