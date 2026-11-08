from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Protocol

from invoice_eval.version import __version__


FOUR_WAY_ANALYSIS_PROMPT_VERSION = "four-way-analysis-v1"
SOURCE_KEYS = ("deterministic", "human", "local_llm", "cloud_llm")
CONFIDENCE_LEVELS = {"low", "medium", "high"}


class AnalysisClient(Protocol):
    @property
    def model(self) -> str: ...

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]: ...


def build_analysis_prompts(
    *,
    report: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, dict[str, Any]]],
) -> tuple[str, str]:
    system_prompt = """
You are an independent analyst of a deterministic four-source evaluation report.
Use only the supplied fact_pack. Do not calculate, estimate, or replace any metric.
Do not use majority voting, external knowledge, or assumptions from another dataset.

Return exactly one JSON object with:
{
  "factual_findings": [
    {
      "statement": "<direct observation grounded in fact_pack>",
      "case_ids": ["<case id>"],
      "event_ids": ["<provided event id>"]
    }
  ],
  "inferences": [
    {
      "statement": "<interpretation clearly beyond direct observation>",
      "case_ids": ["<case id>"],
      "event_ids": ["<provided event id>"],
      "basis": ["<specific report or source fact>"],
      "confidence": "low|medium|high"
    }
  ],
  "unknowns": [
    {
      "statement": "<what cannot be determined>",
      "case_ids": ["<case id>"],
      "missing_evidence": "<missing event, field, or provenance>"
    }
  ]
}

Rules:
- factual_findings contain only direct copies or combinations of supplied facts.
- inferences must state their basis and must not be presented as facts.
- unknowns must explain what evidence is missing.
- Use only case IDs and event IDs present in source_records.
- Do not invent event IDs, scores, rates, model behavior, or hidden reasoning.
- The formal deterministic submission remains authoritative; this analysis is advisory.
- Do not call a local or cloud model correct merely because multiple sources agree.
""".strip()
    source_records = {
        source: {
            case_id: _compact_review(record)
            for case_id, record in sources.get(source, {}).items()
        }
        for source in SOURCE_KEYS
    }
    fact_pack = {
        "deterministic_report": report,
        "source_records": source_records,
    }
    return system_prompt, json.dumps(fact_pack, ensure_ascii=False)


def analyze_four_way_report(
    *,
    report: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, dict[str, Any]]],
    client: AnalysisClient,
) -> dict[str, Any]:
    system_prompt, user_prompt = build_analysis_prompts(
        report=report,
        sources=sources,
    )
    candidate = client.complete_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    validated = validate_analysis(report, sources, candidate)
    return {
        "artifact_type": "four_way_llm_analysis_v1",
        "evaluator_version": __version__,
        "provider": "openai-compatible",
        "model": client.model,
        "prompt_version": FOUR_WAY_ANALYSIS_PROMPT_VERSION,
        **validated,
    }


def validate_analysis(
    report: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, dict[str, Any]]],
    analysis: Any,
) -> dict[str, Any]:
    if not isinstance(analysis, dict):
        raise ValueError("LLM analysis must be an object.")
    case_ids = {
        item.get("case_id")
        for item in report.get("cases", [])
        if isinstance(item, dict)
    }
    event_ids_by_case = {
        case_id: _provided_event_ids(record)
        for source in SOURCE_KEYS
        for case_id, record in sources.get(source, {}).items()
    }
    factual = _validate_statements(
        analysis.get("factual_findings"),
        case_ids=case_ids,
        event_ids_by_case=event_ids_by_case,
        kind="factual",
    )
    inferences = _validate_statements(
        analysis.get("inferences"),
        case_ids=case_ids,
        event_ids_by_case=event_ids_by_case,
        kind="inference",
    )
    unknowns = _validate_statements(
        analysis.get("unknowns"),
        case_ids=case_ids,
        event_ids_by_case=event_ids_by_case,
        kind="unknown",
    )
    return {
        "factual_findings": factual,
        "inferences": inferences,
        "unknowns": unknowns,
    }


def write_analysis(
    analysis: Mapping[str, Any],
    *,
    json_path: Path,
    markdown_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_analysis_markdown(analysis),
        encoding="utf-8",
    )


def render_analysis_markdown(analysis: Mapping[str, Any]) -> str:
    lines = [
        "# 四源报告 LLM 分析附录",
        "",
        f"> 模型：`{analysis['model']}`",
        f"> Prompt：`{analysis['prompt_version']}`",
        f"> 评测器：`{analysis.get('evaluator_version', 'unknown')}`",
        "> 定位：仅基于确定性事实包提供解释；正式结论仍以确定性评测器为准。",
        "",
        "## 事实",
        "",
    ]
    for item in analysis["factual_findings"]:
        lines.append(
            f"- {item['statement']} "
            f"（Case：{', '.join(item['case_ids'])}；"
            f"事件：{', '.join(item['event_ids']) or '无'}）"
        )
    lines.extend(["", "## 推断", ""])
    for item in analysis["inferences"]:
        lines.append(
            f"- [{item['confidence']}] {item['statement']} "
            f"依据：{'；'.join(item['basis'])}。"
        )
    lines.extend(["", "## 未知", ""])
    for item in analysis["unknowns"]:
        missing = item["missing_evidence"].rstrip("。；;")
        lines.append(
            f"- {item['statement']} "
            f"缺少证据：{missing}。"
        )
    lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "- 本附录不是官方标签，也不改变正式 `quality_score` 或版本方向。",
            "- 推断项不是事实；“多源一致”同样不能证明官方正确。",
            "- 需要回到原始轨迹和同一 run 的 `event_id` 复核。",
            "",
        ]
    )
    return "\n".join(lines)


def _compact_review(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": record.get("artifact_type"),
        "model": record.get("model"),
        "prompt_version": record.get("prompt_version"),
        "evaluator_version": record.get("evaluator_version"),
        "direction": record.get("version_comparison", {}).get("direction"),
        "direction_reason": record.get("version_comparison", {}).get(
            "reason"
        ),
        "runs": [
            {
                "run_id": run.get("run_id"),
                "agent_task_success": run.get("agent_task_success"),
                "business_invoice_created": run.get(
                    "business_invoice_created"
                ),
                "root_causes": run.get("root_causes", []),
                "evidence_event_ids": run.get("evidence_event_ids", []),
                "explanation": run.get("explanation"),
                "unknowns": run.get("unknowns", []),
            }
            for run in record.get("run_assessments", [])
            if isinstance(run, dict)
        ],
    }


def _provided_event_ids(record: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    for run in record.get("run_assessments", []):
        if not isinstance(run, dict):
            continue
        result.update(
            event_id
            for event_id in run.get("evidence_event_ids", [])
            if isinstance(event_id, str)
        )
        for root in run.get("root_causes", []):
            if not isinstance(root, dict):
                continue
            result.update(
                event_id
                for event_id in root.get("evidence_event_ids", [])
                if isinstance(event_id, str)
            )
            first = root.get("first_fault_event_id")
            if isinstance(first, str):
                result.add(first)
    return result


def _validate_statements(
    value: Any,
    *,
    case_ids: set[str],
    event_ids_by_case: Mapping[str, set[str]],
    kind: str,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{kind} findings must be a list.")
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"{kind} finding must be an object.")
        statement = item.get("statement")
        if not isinstance(statement, str) or not statement.strip():
            raise ValueError(f"{kind} statement is required.")
        item_cases = item.get("case_ids")
        if (
            not isinstance(item_cases, list)
            or not item_cases
            or any(case_id not in case_ids for case_id in item_cases)
        ):
            raise ValueError(f"{kind} contains an invalid case_id.")
        item_events = item.get("event_ids", [])
        if not isinstance(item_events, list):
            raise ValueError(f"{kind} event_ids must be a list.")
        available_events = {
            event_id
            for case_id in item_cases
            for event_id in event_ids_by_case.get(case_id, set())
        }
        if any(event_id not in available_events for event_id in item_events):
            raise ValueError(f"{kind} contains an unknown event_id.")
        normalized_item = {
            "statement": statement.strip(),
            "case_ids": item_cases,
            "event_ids": item_events,
        }
        if kind == "inference":
            basis = item.get("basis")
            confidence = item.get("confidence")
            if (
                not isinstance(basis, list)
                or not basis
                or any(not isinstance(part, str) or not part for part in basis)
            ):
                raise ValueError("inference basis is required.")
            if confidence not in CONFIDENCE_LEVELS:
                raise ValueError("inference confidence is invalid.")
            normalized_item["basis"] = basis
            normalized_item["confidence"] = confidence
        if kind == "unknown":
            missing = item.get("missing_evidence")
            if not isinstance(missing, str) or not missing.strip():
                raise ValueError("unknown missing_evidence is required.")
            normalized_item["missing_evidence"] = missing.strip()
        normalized.append(normalized_item)
    return normalized
