import copy
import dataclasses
import unittest
from decimal import Decimal
from pathlib import Path

from invoice_eval import (
    calculate_amounts,
    find_amount_findings,
    load_dataset,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "docs" / "00-brief" / "data"


class AmountFabricationTests(unittest.TestCase):
    """题内未给出金额时，Agent 不得自行填入数值（官方规则：缺信息必须追问）。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = load_dataset(DATA_DIR / "02_公开训练轨迹.jsonl")

    def test_unprovided_amount_filled_by_agent_is_flagged(self) -> None:
        case = self.dataset.get_case("INV-T01")
        raw = copy.deepcopy(case.raw)
        raw["reference_result"]["amount_value"] = None
        raw["reference_result"]["expected_amounts"] = None
        case = dataclasses.replace(case, raw=raw)

        findings = find_amount_findings(case, case.runs[0])

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "AMOUNT_FABRICATION_CHECK")
        self.assertEqual(findings[0].root_cause_label, "FIELD_FABRICATION")
        self.assertEqual(findings[0].actor, "AGENT")

    def test_provided_amount_is_not_flagged(self) -> None:
        case = self.dataset.get_case("INV-T01")
        rule_ids = [
            finding.rule_id
            for finding in find_amount_findings(case, case.runs[0])
        ]
        self.assertNotIn("AMOUNT_FABRICATION_CHECK", rule_ids)


class AmountCalculationTests(unittest.TestCase):
    def test_calculates_tax_exclusive_amounts(self) -> None:
        self.assertEqual(
            calculate_amounts("100000", "tax_exclusive", "0.06"),
            {
                "exclusive_amount": Decimal("100000.00"),
                "tax_amount": Decimal("6000.00"),
                "inclusive_amount": Decimal("106000.00"),
            },
        )

    def test_calculates_tax_inclusive_amounts(self) -> None:
        self.assertEqual(
            calculate_amounts("1060", "tax_inclusive", "0.06"),
            {
                "exclusive_amount": Decimal("1000.00"),
                "tax_amount": Decimal("60.00"),
                "inclusive_amount": Decimal("1060.00"),
            },
        )

    def test_rounds_half_up_to_two_decimal_places(self) -> None:
        self.assertEqual(
            calculate_amounts("100000", "tax_inclusive", "0.06"),
            {
                "exclusive_amount": Decimal("94339.62"),
                "tax_amount": Decimal("5660.38"),
                "inclusive_amount": Decimal("100000.00"),
            },
        )

    def test_rejects_unknown_basis(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported amount_basis"):
            calculate_amounts("100", "unknown", "0.06")


class AmountFindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = load_dataset(DATA_DIR / "02_公开训练轨迹.jsonl")
        cls.validation = load_dataset(DATA_DIR / "04_无标注验证轨迹.jsonl")

    def test_detects_amount_basis_error_without_duplicate_calculation_error(
        self,
    ) -> None:
        case = self.dataset.get_case("INV-T01")
        findings = find_amount_findings(
            case, case.get_run("INV-T01-B")
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].root_cause_label, "AMOUNT_BASIS")
        self.assertEqual(
            findings[0].first_fault_event_id,
            "INV-T01-B-05",
        )
        self.assertEqual(
            findings[0].evidence_event_ids,
            ("INV-T01-B-05", "INV-T01-B-08"),
        )

    def test_detects_tax_inclusive_basis_error(self) -> None:
        case = self.dataset.get_case("INV-T02")
        findings = find_amount_findings(
            case, case.get_run("INV-T02-A")
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].root_cause_label, "AMOUNT_BASIS")
        self.assertEqual(
            findings[0].first_fault_event_id,
            "INV-T02-A-05",
        )

    def test_detects_calculation_error(self) -> None:
        case = self.dataset.get_case("INV-T13")
        findings = find_amount_findings(
            case, case.get_run("INV-T13-A")
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(
            findings[0].root_cause_label,
            "AMOUNT_CALCULATION",
        )
        self.assertEqual(
            findings[0].first_fault_event_id,
            "INV-T13-A-05",
        )

    def test_correct_amounts_have_no_finding(self) -> None:
        case = self.dataset.get_case("INV-T13")
        self.assertEqual(
            find_amount_findings(case, case.get_run("INV-T13-B")),
            (),
        )

    def test_submit_argument_drift_is_not_a_collection_error(self) -> None:
        case = self.dataset.get_case("INV-T14")
        self.assertEqual(
            find_amount_findings(case, case.get_run("INV-T14-B")),
            (),
        )

    def test_superseded_input_amount_is_not_an_arithmetic_error(self) -> None:
        case = self.validation.get_case("INV-V04")
        self.assertEqual(
            find_amount_findings(case, case.get_run("INV-V04-A")),
            (),
        )

    def test_validation_inclusive_calculation_error(self) -> None:
        case = self.validation.get_case("INV-V07")
        findings = find_amount_findings(
            case, case.get_run("INV-V07-B")
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(
            findings[0].root_cause_label,
            "AMOUNT_CALCULATION",
        )
        self.assertEqual(
            findings[0].first_fault_event_id,
            "INV-V07-B-05",
        )

    def test_all_public_amount_findings_are_specific(self) -> None:
        findings = {
            (case.case_id, run.run_id, finding.root_cause_label)
            for dataset in (self.dataset, self.validation)
            for case in dataset.cases
            for run in case.runs
            for finding in find_amount_findings(case, run)
        }

        self.assertEqual(
            findings,
            {
                ("INV-T01", "INV-T01-B", "AMOUNT_BASIS"),
                ("INV-T02", "INV-T02-A", "AMOUNT_BASIS"),
                ("INV-T13", "INV-T13-A", "AMOUNT_CALCULATION"),
                ("INV-V01", "INV-V01-B", "AMOUNT_BASIS"),
                ("INV-V03", "INV-V03-B", "FIELD_FABRICATION"),
                ("INV-V07", "INV-V07-B", "AMOUNT_CALCULATION"),
            },
        )


if __name__ == "__main__":
    unittest.main()
