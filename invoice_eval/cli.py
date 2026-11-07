from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from invoice_eval.audit_compare import compare_audits
from invoice_eval.data import load_dataset
from invoice_eval.evaluator import evaluate_case
from invoice_eval.llm_audit import (
    LLMConfig,
    LLMConfigError,
    LLMRequestError,
    LLMReviewValidationError,
    OpenAICompatibleClient,
    audit_case,
)
from invoice_eval.workflow import load_workflow


DEFAULT_WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "00-brief"
    / "data"
    / "01_竞赛版流程字典.json"
)
DEFAULT_RULES_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "00-brief"
    / "data"
    / "07_数据字典与业务规则.md"
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "evaluate":
        return _evaluate(
            cases_path=args.cases,
            output_path=args.output,
            workflow_path=args.workflow,
            case_id=args.case_id,
        )
    if args.command == "audit":
        return _audit(
            cases_path=args.cases,
            output_path=args.output,
            workflow_path=args.workflow,
            rules_path=args.rules,
            case_id=args.case_id,
            model=args.model,
            base_url=args.base_url,
            timeout_seconds=args.timeout,
            cache_dir=args.cache_dir,
        )
    if args.command == "compare-audit":
        return _compare_audit(
            submission_path=args.submission,
            llm_review_path=args.llm_review,
            output_path=args.output,
            case_id=args.case_id,
        )

    parser.error(f"Unknown command: {args.command}")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="invoice-eval",
        description="Evaluate pre-recorded invoice-agent trajectories.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate = commands.add_parser(
        "evaluate",
        help="Evaluate a Case JSONL file and write submission JSONL.",
    )
    evaluate.add_argument("--cases", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument(
        "--workflow",
        type=Path,
        default=DEFAULT_WORKFLOW_PATH,
    )
    evaluate.add_argument("--case-id")

    audit = commands.add_parser(
        "audit",
        help="Run an optional independent LLM review.",
    )
    audit.add_argument("--cases", type=Path, required=True)
    audit.add_argument("--output", type=Path, required=True)
    audit.add_argument(
        "--workflow",
        type=Path,
        default=DEFAULT_WORKFLOW_PATH,
    )
    audit.add_argument(
        "--rules",
        type=Path,
        default=DEFAULT_RULES_PATH,
    )
    audit.add_argument("--case-id")
    audit.add_argument("--model")
    audit.add_argument("--base-url")
    audit.add_argument("--timeout", type=float)
    audit.add_argument("--cache-dir", type=Path)

    compare = commands.add_parser(
        "compare-audit",
        help="Compare deterministic assessments with independent LLM reviews.",
    )
    compare.add_argument("--submission", type=Path, required=True)
    compare.add_argument("--llm-review", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
    compare.add_argument("--case-id")
    return parser


def _evaluate(
    cases_path: Path,
    output_path: Path,
    workflow_path: Path,
    case_id: str | None,
) -> int:
    dataset = load_dataset(cases_path)
    workflow = load_workflow(workflow_path)

    cases = (
        (dataset.get_case(case_id),)
        if case_id is not None
        else dataset.cases
    )
    assessments = [evaluate_case(case, workflow) for case in cases]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False) + "\n"
            for item in assessments
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(assessments)} case(s) to {output_path}")
    return 0


def _audit(
    cases_path: Path,
    output_path: Path,
    workflow_path: Path,
    rules_path: Path,
    case_id: str | None,
    model: str | None,
    base_url: str | None,
    timeout_seconds: float | None,
    cache_dir: Path | None,
) -> int:
    try:
        config = LLMConfig.from_env(
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
        dataset = load_dataset(cases_path)
        workflow = load_workflow(workflow_path)
        rules_text = rules_path.read_text(encoding="utf-8")
        client = OpenAICompatibleClient(config)
        cases = (
            (dataset.get_case(case_id),)
            if case_id is not None
            else dataset.cases
        )
        reviews = [
            audit_case(
                case,
                workflow.raw,
                rules_text,
                client,
                cache_dir=cache_dir,
            )
            for case in cases
        ]
    except (
        OSError,
        LLMConfigError,
        LLMRequestError,
        LLMReviewValidationError,
    ) as exc:
        print(f"LLM audit failed: {exc}")
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(
            json.dumps(review, ensure_ascii=False) + "\n"
            for review in reviews
        ),
        encoding="utf-8",
    )
    print(
        f"Wrote {len(reviews)} LLM review(s) to {output_path} "
        f"using {config.model}"
    )
    return 0


def _compare_audit(
    submission_path: Path,
    llm_review_path: Path,
    output_path: Path,
    case_id: str | None,
) -> int:
    try:
        deterministic = _load_jsonl_by_case(submission_path)
        llm = _load_jsonl_by_case(llm_review_path)
        shared = (
            {case_id}
            if case_id is not None
            else set(deterministic) & set(llm)
        )
        if not shared:
            raise ValueError("No matching cases to compare.")
        missing = (shared - set(deterministic)) | (shared - set(llm))
        if missing:
            raise ValueError(
                f"Missing comparison records for {sorted(missing)!r}."
            )
        comparisons = [
            compare_audits(deterministic[key], llm[key])
            for key in sorted(shared)
        ]
    except (OSError, ValueError, KeyError) as exc:
        print(f"Audit comparison failed: {exc}")
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False) + "\n"
            for item in comparisons
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(comparisons)} comparison(s) to {output_path}")
    return 0


def _load_jsonl_by_case(path: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        record = json.loads(line)
        case_id = record.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{path}:{line_number}: missing case_id")
        records[case_id] = record
    return records
