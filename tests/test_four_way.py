import json
import tempfile
import unittest
from pathlib import Path

from invoice_eval.four_way import (
    build_four_way_report,
    load_local_manifest_statuses,
    load_review_jsonl,
    render_four_way_markdown,
    write_four_way_report,
)


class FourWayReportTests(unittest.TestCase):
    def test_builds_coverage_pairwise_metrics_and_rejections(self) -> None:
        sources = {
            "deterministic": {
                "INV-V01": _review("INV-V01", "baseline_better"),
                "INV-V02": _review("INV-V02", "candidate_better"),
            },
            "human": {
                "INV-V01": _review("INV-V01", "baseline_better"),
                "INV-V02": _review("INV-V02", "candidate_better"),
            },
            "local_llm": {
                "INV-V01": _review(
                    "INV-V01",
                    "baseline_better",
                    artifact_type="llm_review_v1",
                    model="local-model",
                    prompt_version="llm-audit-v5",
                ),
            },
            "cloud_llm": {
                "INV-V01": _review(
                    "INV-V01",
                    "baseline_better",
                    artifact_type="llm_review_v1",
                    model="cloud-model",
                    prompt_version="llm-audit-v5",
                ),
                "INV-V02": _review(
                    "INV-V02",
                    "baseline_better",
                    artifact_type="llm_review_v1",
                    model="cloud-model",
                    prompt_version="llm-audit-v5",
                ),
            },
        }
        report = build_four_way_report(
            sources=sources,
            status_overrides={
                "local_llm": {
                    "INV-V02": "contract_rejected: conflicting root"
                }
            },
        )

        self.assertEqual(report["case_count"], 2)
        local = report["sources"]["local_llm"]
        self.assertEqual(local["present_count"], 1)
        self.assertEqual(local["missing_cases"], ["INV-V02"])
        self.assertIn(
            "contract_rejected",
            local["statuses"]["INV-V02"],
        )
        dis=report["disagreements"]
        self.assertEqual([item["case_id"] for item in dis], ["INV-V02"])
        self.assertFalse(report["cases"][1]["direction_agreement"])

    def test_pairwise_run_metrics_detect_root_and_evidence_differences(
        self,
    ) -> None:
        left = _review("INV-V09", "baseline_better")
        right = _review("INV-V09", "baseline_better")
        right["run_assessments"][1]["root_causes"][0]["label"] = (
            "AMOUNT_CALCULATION"
        )
        right["run_assessments"][1]["evidence_event_ids"] = [
            "INV-V09-B-05"
        ]
        report = build_four_way_report(
            sources={
                "deterministic": {"INV-V09": left},
                "human": {"INV-V09": right},
            }
        )
        pair = report["pairwise"][0]

        self.assertEqual(pair["direction_agreement"]["agree"], 1)
        self.assertEqual(
            pair["run_metrics"]["root_causes"]["agree"],
            1,
        )
        self.assertEqual(
            pair["run_metrics"]["first_faults"]["agree"],
            2,
        )
        self.assertEqual(
            pair["run_metrics"]["assessment_evidence"]["agree"],
            1,
        )

    def test_writes_json_and_markdown_with_unknown_boundary(self) -> None:
        review = _review("INV-V03", "baseline_better")
        review["run_assessments"][1]["unknowns"] = [
            "无法判断被丢弃还是错误合并"
        ]
        report = build_four_way_report(
            sources={
                "deterministic": {"INV-V03": review},
                "human": {"INV-V03": review},
                "local_llm": {"INV-V03": review},
                "cloud_llm": {"INV-V03": review},
            },
            source_paths={
                "deterministic": "deterministic.jsonl",
                "human": "human.jsonl",
                "local_llm": "local.jsonl",
                "cloud_llm": "cloud.jsonl",
            },
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            json_path = root / "report.json"
            markdown_path = root / "report.md"
            write_four_way_report(
                report,
                json_path=json_path,
                markdown_path=markdown_path,
            )
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")

        self.assertEqual(payload["artifact_type"], "four_way_report_v1")
        self.assertIn("不采用多数投票", markdown)
        self.assertIn("无法判断被丢弃还是错误合并", markdown)

    def test_loads_jsonl_and_manifest_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reviews_path = root / "reviews.jsonl"
            reviews_path.write_text(
                json.dumps(_review("INV-V01", "baseline_better")) + "\n",
                encoding="utf-8",
            )
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "rejected_cases": [
                            {
                                "case_id": "INV-V04",
                                "status": "contract_rejected",
                                "reason": "conflicting output",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            reviews = load_review_jsonl(reviews_path)
            statuses = load_local_manifest_statuses(manifest_path)

        self.assertEqual(list(reviews), ["INV-V01"])
        self.assertIn("conflicting output", statuses["INV-V04"])


def _review(
    case_id: str,
    direction: str,
    *,
    artifact_type: str = "human_review_v1",
    model: str | None = None,
    prompt_version: str | None = None,
) -> dict:
    record = {
        "artifact_type": artifact_type,
        "case_id": case_id,
        "run_assessments": [
            {
                "run_id": f"{case_id}-A",
                "agent_task_success": True,
                "business_invoice_created": False,
                "root_causes": [],
                "evidence_event_ids": [f"{case_id}-A-05"],
                "unknowns": [],
            },
            {
                "run_id": f"{case_id}-B",
                "agent_task_success": False,
                "business_invoice_created": False,
                "root_causes": [
                    {
                        "label": "AMOUNT_BASIS",
                        "first_fault_event_id": f"{case_id}-B-05",
                        "evidence_event_ids": [
                            f"{case_id}-B-05",
                            f"{case_id}-B-07",
                        ],
                    }
                ],
                "evidence_event_ids": [
                    f"{case_id}-B-05",
                    f"{case_id}-B-07",
                ],
                "unknowns": [],
            },
        ],
        "version_comparison": {
            "direction": direction,
            "reason": "test",
        },
    }
    if model is not None:
        record["model"] = model
    if prompt_version is not None:
        record["prompt_version"] = prompt_version
    return record


if __name__ == "__main__":
    unittest.main()
