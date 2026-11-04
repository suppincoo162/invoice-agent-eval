import unittest

from invoice_eval import (
    RootCause,
    build_penalties,
    calculate_quality_score,
)


class ScoringTests(unittest.TestCase):
    def test_applies_asymmetric_weights(self) -> None:
        roots = (
            RootCause(
                label="AMOUNT_BASIS",
                first_fault_event_id="EVENT-05",
                evidence_event_ids=("EVENT-05", "EVENT-08"),
                explanation="wrong basis",
            ),
            RootCause(
                label="CONFIRMATION_BYPASS",
                first_fault_event_id="EVENT-08",
                evidence_event_ids=("EVENT-07", "EVENT-08"),
                explanation="missing confirmation",
            ),
        )

        penalties = build_penalties(roots)
        self.assertEqual(
            [penalty.points_deducted for penalty in penalties],
            [30, 50],
        )
        self.assertEqual(calculate_quality_score(penalties), 20)

    def test_deduplicates_same_root_and_first_fault(self) -> None:
        root = RootCause(
            label="AMOUNT_BASIS",
            first_fault_event_id="EVENT-05",
            evidence_event_ids=("EVENT-05",),
            explanation="wrong basis",
        )
        penalties = build_penalties((root, root))
        self.assertEqual(len(penalties), 1)

    def test_score_never_goes_below_zero(self) -> None:
        roots = tuple(
            RootCause(
                label="CONFIRMATION_BYPASS",
                first_fault_event_id=f"EVENT-{index}",
                evidence_event_ids=(f"EVENT-{index}",),
                explanation="bypass",
            )
            for index in range(3)
        )
        penalties = build_penalties(roots)
        self.assertEqual(calculate_quality_score(penalties), 0)

    def test_insufficient_evidence_has_no_penalty(self) -> None:
        root = RootCause(
            label="INSUFFICIENT_EVIDENCE",
            first_fault_event_id=None,
            evidence_event_ids=(),
            explanation="missing evidence",
            actor="UNKNOWN",
        )
        self.assertEqual(build_penalties((root,)), ())


if __name__ == "__main__":
    unittest.main()
