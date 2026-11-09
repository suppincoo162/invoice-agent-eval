import tempfile
import unittest
from pathlib import Path

from invoice_eval.four_way import build_four_way_report
from invoice_eval.four_way_analysis import (
    analyze_four_way_report,
    build_analysis_prompts,
    validate_analysis,
    write_analysis,
)
from invoice_eval.version import __version__


class StaticAnalysisClient:
    model = "analysis-model"

    def __init__(self, response):
        self.response = response

    def complete_json(self, *, system_prompt, user_prompt):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.response


class SequencedAnalysisClient(StaticAnalysisClient):
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.model = "analysis-model"

    def complete_json(self, *, system_prompt, user_prompt):
        self.calls += 1
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.responses.pop(0)


class FourWayAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sources = {
            "deterministic": {
                "INV-V01": _review("INV-V01", "baseline_better"),
            },
            "human": {
                "INV-V01": _review("INV-V01", "baseline_better"),
            },
            "local_llm": {
                "INV-V01": _review(
                    "INV-V01",
                    "equal",
                    artifact_type="llm_review_v1",
                    model="local-model",
                ),
            },
            "cloud_llm": {
                "INV-V01": _review(
                    "INV-V01",
                    "baseline_better",
                    artifact_type="llm_review_v1",
                    model="cloud-model",
                ),
            },
        }
        self.report = build_four_way_report(sources=self.sources)

    def test_prompt_is_fact_pack_and_requires_three_layers(self) -> None:
        system_prompt, user_prompt = build_analysis_prompts(
            report=self.report,
            sources=self.sources,
        )

        self.assertIn("factual_findings", system_prompt)
        self.assertIn("inferences", system_prompt)
        self.assertIn("unknowns", system_prompt)
        self.assertIn("Do not use majority voting", system_prompt)
        self.assertIn("Simplified Chinese", system_prompt)
        self.assertIn("source_records", user_prompt)
        self.assertNotIn("training label", user_prompt)

    def test_valid_analysis_is_grounded_and_written(self) -> None:
        client = StaticAnalysisClient(_valid_analysis())
        analysis = analyze_four_way_report(
            report=self.report,
            sources=self.sources,
            client=client,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            json_path = root / "analysis.json"
            markdown_path = root / "analysis.md"
            write_analysis(
                analysis,
                json_path=json_path,
                markdown_path=markdown_path,
            )
            markdown = markdown_path.read_text(encoding="utf-8")

        self.assertEqual(
            analysis["prompt_version"],
            "four-way-analysis-v1",
        )
        self.assertEqual(analysis["evaluator_version"], __version__)
        self.assertEqual(analysis["model"], "analysis-model")
        self.assertIn("## 事实", markdown)
        self.assertIn("## 推断", markdown)
        self.assertIn("## 未知", markdown)

    def test_rejects_unknown_event_id(self) -> None:
        analysis = _valid_analysis()
        analysis["factual_findings"][0]["event_ids"] = [
            "INV-V01-A-99"
        ]

        with self.assertRaisesRegex(ValueError, "unknown event_id"):
            validate_analysis(self.report, self.sources, analysis)

    def test_invalid_analysis_gets_one_repair_attempt(self) -> None:
        invalid = _valid_analysis()
        invalid["factual_findings"][0]["event_ids"] = [
            "INV-V01-A-99"
        ]
        client = SequencedAnalysisClient([invalid, _valid_analysis()])

        analysis = analyze_four_way_report(
            report=self.report,
            sources=self.sources,
            client=client,
        )

        self.assertEqual(client.calls, 2)
        self.assertIn("上一轮输出未通过程序校验", client.user_prompt)
        self.assertEqual(analysis["model"], "analysis-model")

    def test_rejects_inference_without_basis(self) -> None:
        analysis = _valid_analysis()
        analysis["inferences"][0]["basis"] = []

        with self.assertRaisesRegex(ValueError, "basis is required"):
            validate_analysis(self.report, self.sources, analysis)


def _valid_analysis() -> dict:
    return {
        "factual_findings": [
            {
                "statement": "确定性、人工和云端在 V01 均判基线更好。",
                "case_ids": ["INV-V01"],
                "event_ids": ["INV-V01-B-05"],
            }
        ],
        "inferences": [
            {
                "statement": "本地模型可能弱化了金额口径追问的重要性。",
                "case_ids": ["INV-V01"],
                "event_ids": ["INV-V01-B-05"],
                "basis": ["本地模型方向为 equal，其他来源为 baseline_better"],
                "confidence": "low",
            }
        ],
        "unknowns": [
            {
                "statement": "无法确定本地模型作出该判断的内部原因。",
                "case_ids": ["INV-V01"],
                "missing_evidence": "没有模型隐藏推理过程",
            }
        ],
    }


def _review(
    case_id: str,
    direction: str,
    *,
    artifact_type: str = "human_review_v1",
    model: str | None = None,
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
                "explanation": "baseline correct",
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
                        "explanation": "amount basis assumed",
                    }
                ],
                "evidence_event_ids": [
                    f"{case_id}-B-05",
                    f"{case_id}-B-07",
                ],
                "explanation": "candidate failed",
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
    return record


if __name__ == "__main__":
    unittest.main()
