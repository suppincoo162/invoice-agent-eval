import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from invoice_eval import (
    LLMConfig,
    __version__,
    audit_case,
    load_dataset,
    load_workflow,
)
from invoice_eval.llm_audit import (
    DEFAULT_OLLAMA_BASE_URL,
    LLMReviewValidationError,
    OpenAICompatibleClient,
    build_prompts,
    parse_json_content,
    validate_review,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "docs" / "00-brief" / "data"


class StaticReviewClient:
    def __init__(self, response: dict) -> None:
        self._response = response
        self.calls = 0

    @property
    def model(self) -> str:
        return "mock-model"

    @property
    def cache_identity(self) -> str:
        return "mock://independent-audit"

    def review_case(self, **_: object) -> dict:
        self.calls += 1
        return copy.deepcopy(self._response)


class SequencedReviewClient(StaticReviewClient):
    def __init__(self, responses: list[dict]) -> None:
        self._responses = responses
        self.calls = 0

    def review_case(self, **_: object) -> dict:
        response = self._responses[self.calls]
        self.calls += 1
        return copy.deepcopy(response)


class LLMAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = load_dataset(DATA_DIR / "04_无标注验证轨迹.jsonl")
        cls.case = cls.dataset.get_case("INV-V03")
        cls.workflow = load_workflow(
            DATA_DIR / "01_竞赛版流程字典.json"
        )
        cls.rules_text = "A red invoice requires an original invoice id and amount."

    def test_config_reads_env_without_exposing_key(self) -> None:
        secret = "do-not-print-this-key"
        with patch.dict(
            os.environ,
            {
                "INVOICE_EVAL_LLM_MODEL": "qwen-test",
                "INVOICE_EVAL_LLM_BASE_URL": DEFAULT_OLLAMA_BASE_URL,
                "INVOICE_EVAL_LLM_API_KEY": secret,
            },
            clear=False,
        ):
            config = LLMConfig.from_env()

        self.assertEqual(config.model, "qwen-test")
        self.assertEqual(config.base_url, DEFAULT_OLLAMA_BASE_URL)
        self.assertNotIn(secret, repr(config))

    def test_prompt_contains_only_raw_inputs_and_rules(self) -> None:
        _, user_prompt = build_prompts(
            case_raw=self.case.raw,
            workflow_raw=self.workflow.raw,
            rules_text=self.rules_text,
        )
        payload = json.loads(user_prompt)

        self.assertEqual(payload["case"]["case_id"], "INV-V03")
        self.assertNotIn("run_assessments", payload["case"])
        self.assertEqual(payload["business_rules"], self.rules_text)

    def test_valid_review_is_normalized(self) -> None:
        review = audit_case(
            self.case,
            self.workflow.raw,
            self.rules_text,
            StaticReviewClient(_valid_review()),
        )

        self.assertEqual(review["artifact_type"], "llm_review_v1")
        self.assertEqual(review["evaluator_version"], __version__)
        self.assertEqual(review["model"], "mock-model")
        self.assertEqual(
            review["version_comparison"]["direction"],
            "baseline_better",
        )
        self.assertEqual(
            [item["run_id"] for item in review["run_assessments"]],
            ["INV-V03-A", "INV-V03-B"],
        )

    def test_cache_avoids_second_model_call(self) -> None:
        client = StaticReviewClient(_valid_review())
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            audit_case(
                self.case,
                self.workflow.raw,
                self.rules_text,
                client,
                cache_dir=cache_dir,
            )
            audit_case(
                self.case,
                self.workflow.raw,
                self.rules_text,
                client,
                cache_dir=cache_dir,
            )

        self.assertEqual(client.calls, 1)

    def test_invalid_review_gets_one_repair_attempt(self) -> None:
        invalid = _valid_review()
        invalid["run_assessments"][1]["root_causes"][0][
            "evidence_event_ids"
        ] = ["INV-V03-A-05"]
        client = SequencedReviewClient([invalid, _valid_review()])

        review = audit_case(
            self.case,
            self.workflow.raw,
            self.rules_text,
            client,
        )

        self.assertEqual(client.calls, 2)
        self.assertEqual(
            review["version_comparison"]["direction"],
            "baseline_better",
        )

    def test_rejects_cross_run_evidence(self) -> None:
        response = _valid_review()
        response["run_assessments"][1]["root_causes"][0][
            "evidence_event_ids"
        ] = ["INV-V03-A-05"]

        with self.assertRaisesRegex(
            LLMReviewValidationError, "root evidence"
        ):
            validate_review(self.case, response)

    def test_rejects_missing_success_assessment_evidence(self) -> None:
        response = _valid_review()
        response["run_assessments"][0]["evidence_event_ids"] = []

        with self.assertRaisesRegex(
            LLMReviewValidationError,
            "assessment evidence",
        ):
            validate_review(self.case, response)

    def test_rejects_successful_run_with_root_cause(self) -> None:
        response = _valid_review()
        response["run_assessments"][1]["agent_task_success"] = True

        with self.assertRaisesRegex(
            LLMReviewValidationError,
            "successful run cannot include",
        ):
            validate_review(self.case, response)

    def test_rejects_unknown_root_label(self) -> None:
        response = _valid_review()
        response["run_assessments"][1]["root_causes"][0][
            "label"
        ] = "MODEL_GUESS"

        with self.assertRaisesRegex(
            LLMReviewValidationError, "unknown root-cause"
        ):
            validate_review(self.case, response)

    def test_rejects_invalid_first_fault(self) -> None:
        response = _valid_review()
        response["run_assessments"][1]["root_causes"][0][
            "first_fault_event_id"
        ] = "INV-V03-B-99"

        with self.assertRaisesRegex(
            LLMReviewValidationError, "first-fault"
        ):
            validate_review(self.case, response)

    def test_rejects_invoice_fact_override(self) -> None:
        response = _valid_review()
        response["run_assessments"][1][
            "business_invoice_created"
        ] = True

        with self.assertRaisesRegex(
            LLMReviewValidationError, "contradicts run fact"
        ):
            validate_review(self.case, response)

    def test_rejects_direction_contradiction(self) -> None:
        response = _valid_review()
        response["run_assessments"][1]["agent_task_success"] = True
        response["run_assessments"][1]["root_causes"] = []

        with self.assertRaisesRegex(
            LLMReviewValidationError, "when both succeed"
        ):
            validate_review(self.case, response)

    def test_parses_fenced_json(self) -> None:
        parsed = parse_json_content(
            '```json\n{"case_id":"INV-V03"}\n```'
        )
        self.assertEqual(parsed["case_id"], "INV-V03")

    def test_openai_compatible_request_and_response(self) -> None:
        config = LLMConfig(
            base_url="https://llm.example/v1",
            model="audit-model",
            api_key="secret-value",
        )
        client = OpenAICompatibleClient(config)
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(_valid_review())
                        }
                    }
                ]
            }
        ).encode("utf-8")

        with patch(
            "invoice_eval.llm_audit.urllib.request.urlopen",
            return_value=response,
        ) as urlopen:
            result = client.review_case(
                case_raw=self.case.raw,
                workflow_raw=self.workflow.raw,
                rules_text=self.rules_text,
            )

        request = urlopen.call_args.args[0]
        request_body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(
            request.full_url,
            "https://llm.example/v1/chat/completions",
        )
        self.assertEqual(request_body["model"], "audit-model")
        self.assertEqual(request_body["temperature"], 0)
        self.assertNotIn("secret-value", json.dumps(request_body))
        self.assertEqual(result["case_id"], "INV-V03")


def _valid_review() -> dict:
    return {
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
                "explanation": "Correctly requested the missing fields.",
                "unknowns": [],
            },
            {
                "run_id": "INV-V03-B",
                "agent_task_success": False,
                "business_invoice_created": False,
                "root_causes": [
                    {
                        "label": "FIELD_FABRICATION",
                        "first_fault_event_id": "INV-V03-B-05",
                        "evidence_event_ids": [
                            "INV-V03-B-05",
                            "INV-V03-B-07",
                        ],
                        "explanation": (
                            "The agent invented an amount and continued "
                            "without the required original invoice."
                        ),
                        "confidence": 0.93,
                    }
                ],
                "evidence_event_ids": [
                    "INV-V03-B-05",
                    "INV-V03-B-07",
                ],
                "explanation": "The candidate failed before preview.",
                "unknowns": [],
            },
        ],
        "version_comparison": {
            "direction": "baseline_better",
            "reason": "Only the baseline requested the missing fields.",
        },
    }


if __name__ == "__main__":
    unittest.main()
