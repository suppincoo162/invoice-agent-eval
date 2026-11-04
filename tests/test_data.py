import json
import tempfile
import unittest
from pathlib import Path

from invoice_eval import DatasetFormatError, load_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAINING_CASES = (
    PROJECT_ROOT
    / "docs"
    / "00-brief"
    / "data"
    / "02_公开训练轨迹.jsonl"
)
VALIDATION_CASES = (
    PROJECT_ROOT
    / "docs"
    / "00-brief"
    / "data"
    / "04_无标注验证轨迹.jsonl"
)


class OfficialDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.training = load_dataset(TRAINING_CASES)
        cls.validation = load_dataset(VALIDATION_CASES)

    def test_loads_all_cases_and_two_runs_per_case(self) -> None:
        self.assertEqual(len(self.training.cases), 14)
        self.assertEqual(len(self.validation.cases), 8)
        self.assertTrue(
            all(len(case.runs) == 2 for case in self.training.cases)
        )
        self.assertTrue(
            all(len(case.runs) == 2 for case in self.validation.cases)
        )

    def test_indexes_case_run_and_event(self) -> None:
        case = self.training.get_case("INV-T01")
        run = case.get_run("INV-T01-B")
        event = run.get_event("INV-T01-B-05")

        self.assertEqual(set(case.run_by_id), {"INV-T01-A", "INV-T01-B"})
        self.assertEqual(event.seq, 5)
        self.assertEqual(event.step_id, "COLLECT_INVOICE_DATA")
        self.assertEqual(event.step_status, "SUCCEEDED")

    def test_preserves_unmodelled_raw_fields(self) -> None:
        event = (
            self.training.get_case("INV-T01")
            .get_run("INV-T01-B")
            .get_event("INV-T01-B-05")
        )

        self.assertEqual(
            event.raw["observed_output"]["amount_basis"],
            "tax_inclusive",
        )
        self.assertIn("tool_calls", event.raw)

    def test_lookup_misses_raise_key_error(self) -> None:
        case = self.training.get_case("INV-T01")
        run = case.get_run("INV-T01-A")

        with self.assertRaises(KeyError):
            self.training.get_case("NOT-A-CASE")
        with self.assertRaises(KeyError):
            case.get_run("NOT-A-RUN")
        with self.assertRaises(KeyError):
            run.get_event("NOT-AN-EVENT")


class DatasetValidationTests(unittest.TestCase):
    def test_rejects_duplicate_case_id(self) -> None:
        case = _minimal_case("CASE-1")
        error = self._load_rejects([case, case])
        self.assertIn("duplicate case_id", error)

    def test_rejects_duplicate_run_id(self) -> None:
        case = _minimal_case("CASE-1", run_ids=("RUN-A", "RUN-A"))
        error = self._load_rejects([case])
        self.assertIn("duplicate run_id", error)

    def test_rejects_duplicate_event_id(self) -> None:
        case = _minimal_case(
            "CASE-1",
            event_ids=(
                ("EVENT-A", "EVENT-A"),
                ("EVENT-B", "EVENT-B"),
            ),
        )
        error = self._load_rejects([case])
        self.assertIn("duplicate event_id", error)

    def test_rejects_wrong_run_count(self) -> None:
        case = _minimal_case("CASE-1", run_ids=("RUN-A",))
        error = self._load_rejects([case])
        self.assertIn("exactly 2 runs", error)

    def test_reports_invalid_json_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "broken.jsonl"
            path.write_text('{"case_id":\n', encoding="utf-8")

            with self.assertRaisesRegex(
                DatasetFormatError, r"broken\.jsonl:1: invalid JSON"
            ):
                load_dataset(path)

    def _load_rejects(self, cases: list[dict]) -> str:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "cases.jsonl"
            path.write_text(
                "".join(
                    json.dumps(case, ensure_ascii=False) + "\n"
                    for case in cases
                ),
                encoding="utf-8",
            )
            with self.assertRaises(DatasetFormatError) as caught:
                load_dataset(path)
        return str(caught.exception)


def _minimal_case(
    case_id: str,
    run_ids: tuple[str, ...] = ("RUN-A", "RUN-B"),
    event_ids: tuple[tuple[str, ...], ...] | None = None,
) -> dict:
    if event_ids is None:
        event_ids = tuple((f"EVENT-{index}",) for index in range(len(run_ids)))

    runs = []
    for run_id, run_event_ids in zip(run_ids, event_ids):
        events = [
            {
                "event_id": event_id,
                "seq": seq,
                "step_id": "RECEIVE_REQUEST",
                "step_status": "SUCCEEDED",
            }
            for seq, event_id in enumerate(run_event_ids, start=1)
        ]
        runs.append({"run_id": run_id, "events": events})

    return {"case_id": case_id, "runs": runs}


if __name__ == "__main__":
    unittest.main()
