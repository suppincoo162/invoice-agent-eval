from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol

from invoice_eval.models import Case
from invoice_eval.scoring import PENALTY_POINTS


PROMPT_VERSION = "llm-audit-v5"
ROOT_CAUSE_LABELS = frozenset(PENALTY_POINTS) | {"INSUFFICIENT_EVIDENCE"}
VERSION_DIRECTIONS = frozenset(
    {"baseline_better", "candidate_better", "equal", "insufficient_evidence"}
)
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"


class LLMConfigError(ValueError):
    """Raised when LLM audit configuration is incomplete or invalid."""


class LLMRequestError(RuntimeError):
    """Raised when the configured LLM endpoint cannot return a review."""


class LLMReviewValidationError(ValueError):
    """Raised when a model review violates the audit contract."""


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    model: str
    timeout_seconds: float = 60.0
    api_key: str | None = field(default=None, repr=False)

    @classmethod
    def from_env(
        cls,
        *,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> "LLMConfig":
        resolved_model = model or os.getenv("INVOICE_EVAL_LLM_MODEL")
        if not resolved_model:
            raise LLMConfigError(
                "Set INVOICE_EVAL_LLM_MODEL or pass --model."
            )
        resolved_base_url = (
            base_url
            or os.getenv("INVOICE_EVAL_LLM_BASE_URL")
            or DEFAULT_OLLAMA_BASE_URL
        )
        raw_timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else os.getenv("INVOICE_EVAL_LLM_TIMEOUT")
        )
        try:
            resolved_timeout = float(raw_timeout or 60)
        except (TypeError, ValueError) as exc:
            raise LLMConfigError(
                "INVOICE_EVAL_LLM_TIMEOUT must be a number."
            ) from exc
        if resolved_timeout <= 0:
            raise LLMConfigError("LLM timeout must be greater than zero.")
        return cls(
            base_url=resolved_base_url.rstrip("/"),
            model=resolved_model,
            timeout_seconds=resolved_timeout,
            api_key=os.getenv("INVOICE_EVAL_LLM_API_KEY"),
        )


class ReviewClient(Protocol):
    @property
    def model(self) -> str: ...

    @property
    def cache_identity(self) -> str: ...

    def review_case(
        self,
        *,
        case_raw: Mapping[str, Any],
        workflow_raw: Mapping[str, Any],
        rules_text: str,
        previous_review: Mapping[str, Any] | None = None,
        validation_error: str | None = None,
    ) -> dict[str, Any]: ...


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible client for cloud APIs and Ollama."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @property
    def model(self) -> str:
        return self.config.model

    @property
    def cache_identity(self) -> str:
        return f"{self.config.base_url}|{self.config.model}"

    def review_case(
        self,
        *,
        case_raw: Mapping[str, Any],
        workflow_raw: Mapping[str, Any],
        rules_text: str,
        previous_review: Mapping[str, Any] | None = None,
        validation_error: str | None = None,
    ) -> dict[str, Any]:
        system_prompt, user_prompt = build_prompts(
            case_raw=case_raw,
            workflow_raw=workflow_raw,
            rules_text=rules_text,
            previous_review=previous_review,
            validation_error=validation_error,
        )
        body = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "stream": False,
        }
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        request = urllib.request.Request(
            f"{self.config.base_url}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.config.timeout_seconds
            ) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise LLMRequestError(
                f"LLM endpoint returned HTTP {exc.code}."
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise LLMRequestError(
                "LLM endpoint is unavailable or timed out."
            ) from exc

        try:
            payload = json.loads(response_body)
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMRequestError(
                "LLM endpoint returned an unexpected response shape."
            ) from exc
        return parse_json_content(content)


def build_prompts(
    *,
    case_raw: Mapping[str, Any],
    workflow_raw: Mapping[str, Any],
    rules_text: str,
    previous_review: Mapping[str, Any] | None = None,
    validation_error: str | None = None,
) -> tuple[str, str]:
    system_prompt = f"""
You are an independent auditor of invoice-agent execution traces.
Use only the supplied case, workflow, business rules, and event evidence.
Do not assume access to code, prompts, training labels, or another evaluator.

Return exactly one JSON object and no Markdown fences or extra text.
It must have:
{{
  "case_id": "<case id>",
  "run_assessments": [
    {{
      "run_id": "<run id>",
      "agent_task_success": true,
      "business_invoice_created": true,
      "root_causes": [
        {{
          "label": "<official label>",
          "first_fault_event_id": "<event id or null>",
          "evidence_event_ids": ["<same-run event ids>"],
          "explanation": "<evidence-grounded explanation>",
          "confidence": 0.0
        }}
      ],
      "evidence_event_ids": ["<same-run event ids>"],
      "explanation": "<overall assessment>",
      "unknowns": ["<missing or conflicting evidence>"]
    }}
  ],
  "version_comparison": {{
    "direction": "baseline_better|candidate_better|equal|insufficient_evidence",
    "reason": "<case-level reason; never generalize to the whole version>"
  }}
}}

Rules:
- Return exactly two run assessments matching the supplied run IDs.
- Copy each run's raw `invoice_created` exactly into
  `business_invoice_created`; a failed callback and a successful Agent message
  do not override this field.
- `evidence_event_ids` is required and non-empty for both successful and failed
  runs. For a successful run, include the decisive checks and outcome events.
- Use only these root-cause labels: {", ".join(sorted(ROOT_CAUSE_LABELS))}.
- `step_status`, terminal states, `WAITING_USER`, `E100`, tool names and
  free-form descriptions are NOT root-cause labels.
- If a run is correctly handled, set `agent_task_success=true` and
  `root_causes=[]`; do not attach a waiting state as a root cause.
- If `root_causes` is non-empty, set `agent_task_success=false`.
- Every evidence event must exist in the same run.
- A concrete non-insufficient root cause must include a valid first-fault event.
- Use INSUFFICIENT_EVIDENCE when evidence is missing or contradictory.
- Waiting, cancellation, protective tool rejection and honest external failure
  are not automatically failures.
- Do not invent event IDs, tool results, user confirmations or root causes.
- The version direction describes this case only.
""".strip()
    if previous_review is not None and validation_error:
        system_prompt += (
            "\n\nThe previous response failed deterministic validation: "
            f"{validation_error}\n"
            "Return a complete corrected JSON object. Correct the contract "
            "violation without changing valid evidence from the source data."
        )
    user_payload = {
        "case": case_raw,
        "workflow": workflow_raw,
        "business_rules": rules_text,
    }
    if previous_review is not None:
        user_payload["previous_review"] = previous_review
    return system_prompt, json.dumps(user_payload, ensure_ascii=False)


def audit_case(
    case: Case,
    workflow_raw: Mapping[str, Any],
    rules_text: str,
    client: ReviewClient,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    cache_path = _cache_path(
        case,
        workflow_raw,
        rules_text,
        client,
        cache_dir,
    )
    validated: dict[str, Any] | None = None
    if cache_path is not None and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            validated = validate_review(case, cached)
        except (json.JSONDecodeError, LLMReviewValidationError):
            validated = None
    if validated is None:
        review = client.review_case(
            case_raw=case.raw,
            workflow_raw=workflow_raw,
            rules_text=rules_text,
        )
        try:
            validated = validate_review(case, review)
        except LLMReviewValidationError as exc:
            repaired = client.review_case(
                case_raw=case.raw,
                workflow_raw=workflow_raw,
                rules_text=rules_text,
                previous_review=review,
                validation_error=str(exc),
            )
            validated = validate_review(case, repaired)
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(
                    {"case_id": case.case_id, **validated},
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

    return {
        "artifact_type": "llm_review_v1",
        "case_id": case.case_id,
        "provider": "openai-compatible",
        "model": client.model,
        "prompt_version": PROMPT_VERSION,
        **validated,
    }


def validate_review(case: Case, review: Any) -> dict[str, Any]:
    if not isinstance(review, dict):
        raise LLMReviewValidationError("LLM review must be an object.")
    if review.get("case_id") != case.case_id:
        raise LLMReviewValidationError("LLM review case_id mismatch.")

    assessments = review.get("run_assessments")
    if not isinstance(assessments, list) or len(assessments) != 2:
        raise LLMReviewValidationError(
            "LLM review must contain exactly two run assessments."
        )
    source_runs = {run.run_id: run for run in case.runs}
    reviewed_runs = {
        assessment.get("run_id"): assessment
        for assessment in assessments
        if isinstance(assessment, dict)
    }
    if set(reviewed_runs) != set(source_runs) or len(reviewed_runs) != 2:
        raise LLMReviewValidationError("LLM review run IDs do not match.")

    normalized: list[dict[str, Any]] = []
    for assessment in assessments:
        if not isinstance(assessment, dict):
            raise LLMReviewValidationError(
                "Each LLM run assessment must be an object."
            )
        run_id = assessment["run_id"]
        source = source_runs[run_id]
        event_ids = set(source.event_by_id)
        if not isinstance(assessment.get("agent_task_success"), bool):
            raise LLMReviewValidationError(
                f"{run_id}: agent_task_success must be boolean."
            )
        if assessment.get("business_invoice_created") != source.raw.get(
            "invoice_created"
        ):
            raise LLMReviewValidationError(
                f"{run_id}: business_invoice_created contradicts run fact."
            )

        roots = assessment.get("root_causes")
        if not isinstance(roots, list):
            raise LLMReviewValidationError(
                f"{run_id}: root_causes must be a list."
            )
        normalized_roots: list[dict[str, Any]] = []
        for root in roots:
            if not isinstance(root, dict):
                raise LLMReviewValidationError(
                    f"{run_id}: root cause must be an object."
                )
            label = root.get("label")
            if label not in ROOT_CAUSE_LABELS:
                raise LLMReviewValidationError(
                    f"{run_id}: unknown root-cause label {label!r}."
                )
            evidence = root.get("evidence_event_ids")
            if not isinstance(evidence, list) or any(
                event_id not in event_ids for event_id in evidence
            ):
                raise LLMReviewValidationError(
                    f"{run_id}: invalid or cross-run root evidence."
                )
            first = root.get("first_fault_event_id")
            if label != "INSUFFICIENT_EVIDENCE":
                if first not in event_ids or first not in evidence:
                    raise LLMReviewValidationError(
                        f"{run_id}: invalid first-fault event."
                    )
            if first is not None and first not in event_ids:
                raise LLMReviewValidationError(
                    f"{run_id}: invalid first-fault event."
                )
            explanation = root.get("explanation")
            if not isinstance(explanation, str) or not explanation.strip():
                raise LLMReviewValidationError(
                    f"{run_id}: root cause explanation is required."
                )
            confidence = root.get("confidence")
            if confidence is not None and (
                isinstance(confidence, bool)
                or not isinstance(confidence, (int, float))
                or not 0 <= confidence <= 1
            ):
                raise LLMReviewValidationError(
                    f"{run_id}: invalid confidence."
                )
            normalized_roots.append(root)

        if (
            assessment["agent_task_success"] is False
            and not normalized_roots
        ):
            raise LLMReviewValidationError(
                f"{run_id}: failed run must include a root cause."
            )
        if (
            assessment["agent_task_success"] is True
            and normalized_roots
        ):
            raise LLMReviewValidationError(
                f"{run_id}: successful run cannot include a root cause."
            )
        evidence = assessment.get("evidence_event_ids")
        if (
            not isinstance(evidence, list)
            or not evidence
            or any(event_id not in event_ids for event_id in evidence)
        ):
            raise LLMReviewValidationError(
                f"{run_id}: invalid or cross-run assessment evidence."
            )
        explanation = assessment.get("explanation")
        if not isinstance(explanation, str) or not explanation.strip():
            raise LLMReviewValidationError(
                f"{run_id}: overall explanation is required."
            )
        unknowns = assessment.get("unknowns", [])
        if not isinstance(unknowns, list) or any(
            not isinstance(item, str) or not item.strip()
            for item in unknowns
        ):
            raise LLMReviewValidationError(
                f"{run_id}: unknowns must be strings."
            )
        normalized.append(
            {
                "run_id": run_id,
                "agent_task_success": assessment["agent_task_success"],
                "business_invoice_created": source.raw.get(
                    "invoice_created"
                ),
                "root_causes": normalized_roots,
                "evidence_event_ids": evidence,
                "explanation": explanation,
                "unknowns": unknowns,
            }
        )

    comparison = review.get("version_comparison")
    if not isinstance(comparison, dict):
        raise LLMReviewValidationError(
            "LLM version_comparison must be an object."
        )
    if comparison.get("direction") not in VERSION_DIRECTIONS:
        raise LLMReviewValidationError(
            "LLM version direction is invalid."
        )
    reason = comparison.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise LLMReviewValidationError(
            "LLM version comparison reason is required."
        )
    success_by_run = {
        assessment["run_id"]: assessment["agent_task_success"]
        for assessment in assessments
    }
    baseline_success = success_by_run[case.runs[0].run_id]
    candidate_success = success_by_run[case.runs[1].run_id]
    direction = comparison["direction"]
    if baseline_success and not candidate_success and direction != "baseline_better":
        raise LLMReviewValidationError(
            "LLM direction must be baseline_better when A succeeds and B fails."
        )
    if candidate_success and not baseline_success and direction != "candidate_better":
        raise LLMReviewValidationError(
            "LLM direction must be candidate_better when B succeeds and A fails."
        )
    if baseline_success and candidate_success and direction in {
        "baseline_better",
        "candidate_better",
    }:
        raise LLMReviewValidationError(
            "LLM direction cannot favor one version when both succeed."
        )
    return {
        "run_assessments": normalized,
        "version_comparison": {
            "direction": direction,
            "reason": reason,
        },
    }


def parse_json_content(content: Any) -> dict[str, Any]:
    if not isinstance(content, str):
        raise LLMRequestError("LLM response content must be text.")
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise LLMRequestError("LLM response did not contain a JSON object.")
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMRequestError("LLM response JSON is invalid.") from exc
    if not isinstance(parsed, dict):
        raise LLMRequestError("LLM response JSON must be an object.")
    return parsed


def _cache_path(
    case: Case,
    workflow_raw: Mapping[str, Any],
    rules_text: str,
    client: ReviewClient,
    cache_dir: Path | None,
) -> Path | None:
    if cache_dir is None:
        return None
    material = json.dumps(
        {
            "identity": client.cache_identity,
            "model": client.model,
            "prompt_version": PROMPT_VERSION,
            "case": case.raw,
            "workflow": workflow_raw,
            "rules": rules_text,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return cache_dir / f"{case.case_id}-{digest[:16]}.json"
