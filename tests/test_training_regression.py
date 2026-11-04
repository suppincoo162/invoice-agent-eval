import json
import unittest
from pathlib import Path

from invoice_eval import evaluate_case, load_dataset, load_workflow


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "docs" / "00-brief" / "data"


class TrainingRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = load_dataset(DATA_DIR / "02_公开训练轨迹.jsonl")
        cls.workflow = load_workflow(
            DATA_DIR / "01_竞赛版流程字典.json"
        )
        cls.reference = {
            item["case_id"]: item
            for item in _read_jsonl(DATA_DIR / "03_公开训练参考标注.jsonl")
        }

    def test_all_training_runs_match_reference_attribution(self) -> None:
        for case in self.dataset.cases:
            with self.subTest(case_id=case.case_id):
                actual = evaluate_case(case, self.workflow)
                expected = self.reference[case.case_id]
                self.assertEqual(
                    actual["version_comparison"]["direction"],
                    expected["version_direction_on_this_case"],
                )

                for actual_run, expected_run in zip(
                    actual["run_assessments"],
                    expected["run_assessments"],
                ):
                    self.assertEqual(
                        actual_run["run_id"],
                        expected_run["run_id"],
                    )
                    self.assertEqual(
                        actual_run["agent_task_success"],
                        expected_run["agent_task_success"],
                    )
                    self.assertEqual(
                        actual_run["business_invoice_created"],
                        expected_run["business_invoice_created"],
                    )
                    self.assertEqual(
                        _root_map(actual_run["root_causes"]),
                        _root_map(expected_run["root_causes"]),
                    )


def _root_map(root_causes: list[dict]) -> dict[str, tuple]:
    return {
        root["label"]: (
            root["first_fault_event_id"],
            tuple(root["evidence_event_ids"]),
        )
        for root in root_causes
    }


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


if __name__ == "__main__":
    unittest.main()
