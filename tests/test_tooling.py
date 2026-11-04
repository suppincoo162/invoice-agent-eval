import unittest
from pathlib import Path

from invoice_eval import find_protective_rejections, load_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "docs" / "00-brief" / "data"


class ProtectiveRejectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = load_dataset(DATA_DIR / "02_公开训练轨迹.jsonl")

    def test_confirmation_required_rejection_is_protective(self) -> None:
        case = self.dataset.get_case("INV-T01")
        rejections = find_protective_rejections(
            case.get_run("INV-T01-B")
        )

        self.assertEqual(len(rejections), 1)
        self.assertEqual(rejections[0].event_id, "INV-T01-B-08")
        self.assertEqual(rejections[0].tool_name, "invoice.submit")
        self.assertEqual(
            rejections[0].reason_code,
            "CONFIRMATION_REQUIRED",
        )

    def test_correct_waiting_run_has_no_rejection(self) -> None:
        case = self.dataset.get_case("INV-T01")
        self.assertEqual(
            find_protective_rejections(case.get_run("INV-T01-A")),
            (),
        )


if __name__ == "__main__":
    unittest.main()
