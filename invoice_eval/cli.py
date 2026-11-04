from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from invoice_eval.data import load_dataset
from invoice_eval.evaluator import evaluate_case
from invoice_eval.workflow import load_workflow


DEFAULT_WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "00-brief"
    / "data"
    / "01_竞赛版流程字典.json"
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
