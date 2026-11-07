import unittest
from pathlib import Path

from invoice_eval import (
    compare_audits,
    evaluate_case,
    load_dataset,
    load_workflow,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "docs" / "00-brief" / "data"


class AuditComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = load_dataset(DATA_DIR / "04_无标注验证轨迹.jsonl")
        cls.workflow = load_workflow(
            DATA_DIR / "01_竞赛版流程字典.json"
        )

    def test_compares_success_direction_and_evidence(self) -> None:
        case = self.dataset.get_case("INV-V03")
        deterministic = evaluate_case(case, self.workflow)
        llm = {
            "case_id": "INV-V03",
            "run_assessments": [
                {
                    "run_id": "INV-V03-A",
                    "agent_task_success": True,
                    "business_invoice_created": False,
                    "root_causes": [],
                    "evidence_event_ids": [
                        "INV-V03-A-05",
                        "INV-V03-A-06",
                    ],
                },
                {
                    "run_id": "INV-V03-B",
                    "agent_task_success": False,
                    "business_invoice_created": False,
                    "root_causes": [
                        {
                            "label": "FIELD_FABRICATION",
                            "first_fault_event_id": "INV-V03-B-05",
                            "evidence_event_ids": ["INV-V03-B-05"],
                        }
                    ],
                    "evidence_event_ids": ["INV-V03-B-05"],
                },
            ],
            "version_comparison": {"direction": "baseline_better"},
        }

        comparison = compare_audits(deterministic, llm)

        self.assertTrue(comparison["direction"]["agree"])
        self.assertTrue(comparison["summary"]["core_diagnosis_agree"])
        self.assertFalse(comparison["summary"]["root_evidence_agree"])
        self.assertFalse(comparison["summary"]["fully_agree"])
        candidate = comparison["runs"][1]
        self.assertTrue(candidate["agent_task_success"]["agree"])
        self.assertTrue(candidate["root_causes"]["agree"])
        self.assertFalse(candidate["root_evidence"]["agree"])
        self.assertEqual(
            candidate["evidence_only_deterministic"],
            ["INV-V03-B-07"],
        )


if __name__ == "__main__":
    unittest.main()
