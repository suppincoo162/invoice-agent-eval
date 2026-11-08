import json
import tempfile
import unittest
from pathlib import Path

from invoice_eval import evaluate_case, load_dataset, load_workflow
from invoice_eval.four_way import load_review_jsonl
from invoice_eval.rubric import build_rubric_report
from invoice_eval.version_report import (
    build_version_report,
    render_version_report,
    write_version_report,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "docs" / "00-brief" / "data"


class VersionReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.training = load_dataset(DATA_DIR / "02_公开训练轨迹.jsonl")
        cls.validation = load_dataset(
            DATA_DIR / "04_无标注验证轨迹.jsonl"
        )
        cls.workflow = load_workflow(
            DATA_DIR / "01_竞赛版流程字典.json"
        )
        cls.training_reference = load_review_jsonl(
            DATA_DIR / "03_公开训练参考标注.jsonl"
        )
        cls.submission = {
            case.case_id: evaluate_case(case, cls.workflow)
            for case in cls.validation.cases
        }

    def test_builds_official_sections_and_computed_metrics(self) -> None:
        report = build_version_report(
            validation_dataset=self.validation,
            validation_submission=self.submission,
            training_dataset=self.training,
            training_reference=self.training_reference,
            workflow=self.workflow,
        )
        markdown = render_version_report(report)

        self.assertEqual(report["case_count"], 8)
        self.assertEqual(report["run_count"], 16)
        self.assertEqual(report["metrics"]["baseline"]["success_count"], 5)
        self.assertEqual(report["metrics"]["candidate"]["success_count"], 4)
        self.assertEqual(report["metrics"]["baseline"]["invoice_count"], 3)
        self.assertEqual(report["metrics"]["candidate"]["invoice_count"], 3)
        self.assertTrue(report["training_regression"]["consistent"])
        self.assertEqual(
            report["training_regression"]["run_count"],
            28,
        )
        self.assertIn("## 1. 报告信息", markdown)
        self.assertIn("## 7. 改进和回归 Case", markdown)
        self.assertIn("## 附录 A：四方独立验证", markdown)
        self.assertIn("INV-V07-B", markdown)
        self.assertNotIn("[ ]", markdown)

    def test_training_mismatch_blocks_release(self) -> None:
        reference = {
            case_id: json.loads(json.dumps(value))
            for case_id, value in self.training_reference.items()
        }
        reference["INV-T01"]["version_direction_on_this_case"] = (
            "candidate_better"
        )
        report = build_version_report(
            validation_dataset=self.validation,
            validation_submission=self.submission,
            training_dataset=self.training,
            training_reference=reference,
            workflow=self.workflow,
        )

        self.assertFalse(report["training_regression"]["consistent"])
        self.assertEqual(
            report["release_recommendation"]["action"],
            "investigate",
        )

    def test_writes_markdown_and_machine_summary(self) -> None:
        report = build_version_report(
            validation_dataset=self.validation,
            validation_submission=self.submission,
            training_dataset=self.training,
            training_reference=self.training_reference,
            workflow=self.workflow,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            markdown_path = root / "report.md"
            json_path = root / "report.json"
            write_version_report(
                report,
                markdown_path=markdown_path,
                json_path=json_path,
            )
            markdown = markdown_path.read_text(encoding="utf-8")
            summary = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("AI 开票 Agent A/B 版本评测报告", markdown)
        self.assertEqual(
            summary["artifact_type"],
            "version_report_data_v1",
        )

    def test_rubric_is_opt_in_appendix_only(self) -> None:
        base = build_version_report(
            validation_dataset=self.validation,
            validation_submission=self.submission,
            training_dataset=self.training,
            training_reference=self.training_reference,
            workflow=self.workflow,
        )
        rubric_rows = build_rubric_report(
            self.validation,
            self.submission,
        )
        rubric_map = {row["case_id"]: row for row in rubric_rows}
        with_rubric = build_version_report(
            validation_dataset=self.validation,
            validation_submission=self.submission,
            training_dataset=self.training,
            training_reference=self.training_reference,
            workflow=self.workflow,
            rubric_report=rubric_map,
        )

        self.assertNotIn("rubric", base)
        self.assertNotIn(
            "## 附录 E：Rubric 双轨对照",
            render_version_report(base),
        )
        self.assertIn("rubric", with_rubric)
        self.assertEqual(with_rubric["rubric"]["changed_run_count"], 2)
        self.assertEqual(with_rubric["rubric"]["capped_run_count"], 2)
        self.assertIn(
            "## 附录 E：Rubric 双轨对照",
            render_version_report(with_rubric),
        )


if __name__ == "__main__":
    unittest.main()
