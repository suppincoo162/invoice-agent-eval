from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from invoice_eval.audit_compare import compare_audits
from invoice_eval.data import load_dataset
from invoice_eval.evaluator import evaluate_case
from invoice_eval.four_way import (
    build_four_way_report,
    load_local_manifest_statuses,
    load_review_jsonl,
    write_four_way_report,
)
from invoice_eval.four_way_analysis import (
    analyze_four_way_report,
    write_analysis,
)
from invoice_eval.llm_audit import (
    LLMConfig,
    LLMConfigError,
    LLMRequestError,
    LLMReviewValidationError,
    OpenAICompatibleClient,
    audit_case,
)
from invoice_eval.workflow import load_workflow
from invoice_eval.version import __version__
from invoice_eval.version_report import (
    build_version_report,
    load_jsonl_cases,
    write_version_report,
)


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
DEFAULT_TRAIN_CASES_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "00-brief"
    / "data"
    / "02_公开训练轨迹.jsonl"
)
DEFAULT_TRAIN_REFERENCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "00-brief"
    / "data"
    / "03_公开训练参考标注.jsonl"
)
DEFAULT_VALIDATION_CASES_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "00-brief"
    / "data"
    / "04_无标注验证轨迹.jsonl"
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
    if args.command == "four-way-report":
        return _four_way_report(
            deterministic_path=args.deterministic,
            human_path=args.human,
            local_llm_path=args.local_llm,
            cloud_llm_path=args.cloud_llm,
            local_manifest_path=args.local_manifest,
            json_output_path=args.output_json,
            markdown_output_path=args.output_md,
        )
    if args.command == "four-way-analysis":
        return _four_way_analysis(
            report_path=args.report_json,
            deterministic_path=args.deterministic,
            human_path=args.human,
            local_llm_path=args.local_llm,
            cloud_llm_path=args.cloud_llm,
            json_output_path=args.output_json,
            markdown_output_path=args.output_md,
            model=args.model,
            base_url=args.base_url,
            timeout_seconds=args.timeout,
        )
    if args.command == "version-report":
        return _version_report(
            validation_cases_path=args.cases,
            training_cases_path=args.training_cases,
            training_reference_path=args.training_reference,
            submission_path=args.submission,
            workflow_path=args.workflow,
            four_way_report_path=args.four_way_report,
            markdown_output_path=args.output_md,
            json_output_path=args.output_json,
        )

    parser.error(f"Unknown command: {args.command}")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="invoice-eval",
        description="Evaluate pre-recorded invoice-agent trajectories.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
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

    four_way = commands.add_parser(
        "four-way-report",
        help=(
            "Generate a deterministic multi-source comparison report "
            "without calling an LLM."
        ),
    )
    four_way.add_argument("--deterministic", type=Path, required=True)
    four_way.add_argument("--human", type=Path, required=True)
    four_way.add_argument("--local-llm", type=Path, required=True)
    four_way.add_argument("--cloud-llm", type=Path, required=True)
    four_way.add_argument("--local-manifest", type=Path)
    four_way.add_argument("--output-json", type=Path, required=True)
    four_way.add_argument("--output-md", type=Path, required=True)

    analysis = commands.add_parser(
        "four-way-analysis",
        help=(
            "Create a model-assisted fact/inference/unknown appendix "
            "from a deterministic four-way report."
        ),
    )
    analysis.add_argument("--report-json", type=Path, required=True)
    analysis.add_argument("--deterministic", type=Path, required=True)
    analysis.add_argument("--human", type=Path, required=True)
    analysis.add_argument("--local-llm", type=Path, required=True)
    analysis.add_argument("--cloud-llm", type=Path, required=True)
    analysis.add_argument("--output-json", type=Path, required=True)
    analysis.add_argument("--output-md", type=Path, required=True)
    analysis.add_argument("--model")
    analysis.add_argument("--base-url")
    analysis.add_argument("--timeout", type=float)

    report = commands.add_parser(
        "version-report",
        help=(
            "Render the official A/B version report deterministically "
            "from evaluation artifacts."
        ),
    )
    report.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_VALIDATION_CASES_PATH,
    )
    report.add_argument(
        "--training-cases",
        type=Path,
        default=DEFAULT_TRAIN_CASES_PATH,
    )
    report.add_argument(
        "--training-reference",
        type=Path,
        default=DEFAULT_TRAIN_REFERENCE_PATH,
    )
    report.add_argument("--submission", type=Path, required=True)
    report.add_argument(
        "--workflow",
        type=Path,
        default=DEFAULT_WORKFLOW_PATH,
    )
    report.add_argument("--four-way-report", type=Path)
    report.add_argument("--output-md", type=Path, required=True)
    report.add_argument("--output-json", type=Path)
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


def _four_way_report(
    deterministic_path: Path,
    human_path: Path,
    local_llm_path: Path,
    cloud_llm_path: Path,
    local_manifest_path: Path | None,
    json_output_path: Path,
    markdown_output_path: Path,
) -> int:
    paths = {
        "deterministic": deterministic_path,
        "human": human_path,
        "local_llm": local_llm_path,
        "cloud_llm": cloud_llm_path,
    }
    sources = {
        source: load_review_jsonl(path)
        for source, path in paths.items()
    }
    status_overrides = {}
    if local_manifest_path is not None:
        status_overrides["local_llm"] = load_local_manifest_statuses(
            local_manifest_path
        )
    report = build_four_way_report(
        sources=sources,
        source_paths={
            source: str(path) for source, path in paths.items()
        },
        status_overrides=status_overrides,
    )
    write_four_way_report(
        report,
        json_path=json_output_path,
        markdown_path=markdown_output_path,
    )
    print(
        f"Wrote four-way report for {report['case_count']} case(s) "
        f"to {json_output_path} and {markdown_output_path}"
    )
    return 0


def _four_way_analysis(
    report_path: Path,
    deterministic_path: Path,
    human_path: Path,
    local_llm_path: Path,
    cloud_llm_path: Path,
    json_output_path: Path,
    markdown_output_path: Path,
    model: str | None,
    base_url: str | None,
    timeout_seconds: float | None,
) -> int:
    paths = {
        "deterministic": deterministic_path,
        "human": human_path,
        "local_llm": local_llm_path,
        "cloud_llm": cloud_llm_path,
    }
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        sources = {
            source: load_review_jsonl(path)
            for source, path in paths.items()
        }
        config = LLMConfig.from_env(
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
        analysis = analyze_four_way_report(
            report=report,
            sources=sources,
            client=OpenAICompatibleClient(config),
        )
    except (
        OSError,
        ValueError,
        KeyError,
        LLMConfigError,
        LLMRequestError,
        LLMReviewValidationError,
    ) as exc:
        print(f"Four-way LLM analysis failed: {exc}")
        return 1
    write_analysis(
        analysis,
        json_path=json_output_path,
        markdown_path=markdown_output_path,
    )
    print(
        f"Wrote four-way LLM analysis to {json_output_path} "
        f"and {markdown_output_path} using {config.model}"
    )
    return 0


def _version_report(
    validation_cases_path: Path,
    training_cases_path: Path,
    training_reference_path: Path,
    submission_path: Path,
    workflow_path: Path,
    four_way_report_path: Path | None,
    markdown_output_path: Path,
    json_output_path: Path | None,
) -> int:
    try:
        validation_dataset = load_dataset(validation_cases_path)
        training_dataset = load_dataset(training_cases_path)
        training_reference = load_review_jsonl(
            training_reference_path
        )
        submission = load_jsonl_cases(submission_path)
        workflow = load_workflow(workflow_path)
        four_way = (
            json.loads(
                four_way_report_path.read_text(encoding="utf-8")
            )
            if four_way_report_path is not None
            else None
        )
        report = build_version_report(
            validation_dataset=validation_dataset,
            validation_submission=submission,
            training_dataset=training_dataset,
            training_reference=training_reference,
            workflow=workflow,
            four_way_report=four_way,
            submission_path=str(submission_path),
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Version report failed: {exc}")
        return 1
    write_version_report(
        report,
        markdown_path=markdown_output_path,
        json_path=json_output_path,
    )
    print(
        f"Wrote version report for {report['case_count']} case(s) "
        f"to {markdown_output_path}"
    )
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
