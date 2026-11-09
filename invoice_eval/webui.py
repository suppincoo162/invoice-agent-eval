from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from invoice_eval.models import Case, Dataset
from invoice_eval.rubric import validate_rubric_report
from invoice_eval.version import __version__


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEBUI_SOURCE = PROJECT_ROOT / "webui"


def build_webui_data(
    *,
    dataset: Dataset,
    submission: Mapping[str, dict[str, Any]],
    four_way_report: Mapping[str, Any],
    rubric_report: Mapping[str, dict[str, Any]] | None = None,
    llm_analysis: Mapping[str, Any] | None = None,
    submission_path: Path | None = None,
    source_paths: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    expected_cases = {case.case_id for case in dataset.cases}
    if set(submission) != expected_cases:
        raise ValueError("submission cases do not match dataset")
    if rubric_report is not None:
        validate_rubric_report(
            dataset,
            submission,
            rubric_report,
            source_submission_sha256=(
                _sha256(submission_path)
                if submission_path is not None
                else None
            ),
        )

    four_cases = {
        item.get("case_id"): item
        for item in four_way_report.get("cases", [])
        if isinstance(item, dict)
    }
    rubric_cases = rubric_report or {}
    analysis_by_case = _analysis_by_case(llm_analysis)
    commit, dirty = _git_provenance()
    cases = [
        _build_case(
            case,
            submission[case.case_id],
            four_cases.get(case.case_id),
            rubric_cases.get(case.case_id),
            analysis_by_case.get(case.case_id),
        )
        for case in dataset.cases
    ]
    directions = {
        "baseline_better": sum(
            item["version_direction"] == "baseline_better"
            for item in cases
        ),
        "candidate_better": sum(
            item["version_direction"] == "candidate_better"
            for item in cases
        ),
        "equal": sum(
            item["version_direction"] == "equal" for item in cases
        ),
        "insufficient_evidence": sum(
            item["version_direction"] == "insufficient_evidence"
            for item in cases
        ),
    }
    recommendation = _release_recommendation(cases, directions)
    return {
        "metadata": {
            "evaluator_version": __version__,
            "code_commit": commit,
            "working_tree_dirty": dirty,
            "generated_at": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
            "dataset_version": "student-1.0",
            "case_count": len(cases),
            "run_count": sum(len(item["runs"]) for item in cases),
            "submission_sha256": (
                _sha256(submission_path)
                if submission_path is not None
                else None
            ),
            "source_paths": dict(source_paths or {}),
        },
        "directions": directions,
        "release_recommendation": recommendation,
        "source_coverage": four_way_report.get("sources", {}),
        "pairwise": four_way_report.get("pairwise", []),
        "cases": cases,
        "appendices": _appendices(llm_analysis),
    }


def write_webui(
    data: Mapping[str, Any],
    output_dir: Path,
    *,
    template_dir: Path = WEBUI_SOURCE,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "styles.css", "app.js"):
        source = template_dir / name
        if not source.is_file():
            raise ValueError(f"missing WebUI asset: {source}")
        shutil.copyfile(source, output_dir / name)
    # 🔴 2026-11-09 修：把附录文件复制进 output_dir/appendices/，
    # 使站内相对链接（appendices/xxx）在静态服务下可达。
    project_root = Path(__file__).resolve().parents[1]
    appendix_dir = output_dir / "appendices"
    appendix_dir.mkdir(parents=True, exist_ok=True)
    for rel in APPENDIX_FILES.values():
        src = project_root / rel
        if src.is_file():
            shutil.copyfile(src, appendix_dir / src.name)

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    (output_dir / "data.js").write_text(
        "window.INVOICE_EVAL_DATA=" + payload + ";\n",
        encoding="utf-8",
    )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_case(
    case: Case,
    assessment: Mapping[str, Any],
    four_way: Mapping[str, Any] | None,
    rubric: Mapping[str, Any] | None,
    analysis: Mapping[str, Any] | None,
) -> dict[str, Any]:
    runs = assessment.get("run_assessments")
    if not isinstance(runs, list) or len(runs) != 2:
        raise ValueError(f"{case.case_id}: expected exactly two runs")
    assessments = {run.get("run_id"): run for run in runs}
    if set(assessments) != {run.run_id for run in case.runs}:
        raise ValueError(f"{case.case_id}: run IDs do not match")
    rubric_runs = {
        run.get("run_id"): run
        for run in (rubric or {}).get("run_assessments", [])
    }
    first_faults = {
        root.get("first_fault_event_id")
        for run in runs
        for root in run.get("root_causes", [])
        if root.get("first_fault_event_id")
    }
    evidence = {
        event_id
        for run in runs
        for event_id in run.get("evidence_event_ids", [])
    }
    return {
        "case_id": case.case_id,
        "scenario": case.raw.get("scenario"),
        "user_request": case.raw.get("user_request"),
        "reference_result": case.raw.get("reference_result"),
        "version_direction": assessment.get("version_comparison", {}).get(
            "direction"
        ),
        "version_reason": assessment.get("version_comparison", {}).get(
            "reason"
        ),
        "runs": [
            {
                "run_id": run.run_id,
                "agent_version": run.raw.get("agent_version"),
                "final_state": run.raw.get("final_state"),
                "invoice_created": run.raw.get("invoice_created"),
                "resource_usage": run.raw.get("resource_usage", {}),
                "assessment": assessments[run.run_id],
                "rubric": rubric_runs.get(run.run_id),
                "events": [
                    {
                        "event_id": event.event_id,
                        "seq": event.seq,
                        "step_id": event.step_id,
                        "module": event.raw.get("module"),
                        "action": event.raw.get("action"),
                        "step_status": event.step_status,
                        "result_code": event.raw.get("result_code"),
                        "observed_input": event.raw.get("observed_input", {}),
                        "observed_output": event.raw.get(
                            "observed_output", {}
                        ),
                        "tool_calls": event.raw.get("tool_calls", []),
                        "is_evidence": event.event_id in evidence,
                        "is_first_fault": event.event_id in first_faults,
                    }
                    for event in run.events
                ],
            }
            for run in case.runs
        ],
        "four_way": four_way,
        "analysis": analysis,
    }


def _analysis_by_case(
    analysis: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if analysis is None:
        return {}
    result: dict[str, dict[str, Any]] = {}
    for category in ("factual_findings", "inferences", "unknowns"):
        for item in analysis.get(category, []):
            for case_id in item.get("case_ids", []):
                bucket = result.setdefault(
                    case_id,
                    {
                        "factual_findings": [],
                        "inferences": [],
                        "unknowns": [],
                    },
                )
                bucket[category].append(item)
    return result


APPENDIX_FILES = {
    "version_report": "docs/50-deliverables/version-report.md",
    "four_way_report": "docs/50-deliverables/four-way-report.md",
    "llm_analysis": "docs/50-deliverables/four-way-llm-analysis.md",
    "validation_jsonl": "outputs/validation-v0.3.0-dev.jsonl",
    "rubric_jsonl": "outputs/rubric-report.jsonl",
}


def _appendices(
    llm_analysis: Mapping[str, Any] | None,
    *,
    project_root: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, str]:
    """返回附录链接。

    🔴 2026-11-09 修（经霖实测：页面所有附录链接 404）：
        原实现写死 `root = "../../"`，假定 output_dir 在项目根下两层。
        但静态服务通常以 output_dir 为根（`python -m http.server --directory outputs/webui`），
        任何 `../` 都会越出服务根 ⇒ 浏览器一律 404。
        现改为：**把附录文件复制进 output_dir/appendices/**，链接用站内相对路径。
    """
    links: dict[str, str] = {}
    for key, rel in APPENDIX_FILES.items():
        if key == "llm_analysis" and llm_analysis is None:
            links[key] = ""
            continue
        # 默认：站内相对路径（文件由 write_webui 复制到 appendices/ 下）
        links[key] = "appendices/" + Path(rel).name
    return links


def _release_recommendation(
    cases: list[dict[str, Any]],
    directions: Mapping[str, int],
) -> dict[str, Any]:
    capped = [
        {
            "case_id": case["case_id"],
            "run_id": run["run_id"],
            "impact_cap": run["rubric"]["impact_cap"],
        }
        for case in cases
        for run in case["runs"]
        if run.get("rubric")
        and run["rubric"].get("impact_cap") is not None
    ]
    if (
        directions["baseline_better"] > directions["candidate_better"]
        or directions["insufficient_evidence"]
    ):
        action = "investigate"
        reason = "候选退化多于提升，或存在证据不足，应先修复再复测。"
    elif directions["candidate_better"] > directions["baseline_better"]:
        action = "gray"
        reason = "候选提升多于退化，但仍需扩大验证集。"
    else:
        action = "gray"
        reason = "两版表现接近，应扩大验证集后决定。"
    return {
        "action": action,
        "reason": reason,
        "capped_runs": capped,
    }


def _git_provenance() -> tuple[str, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip() or "unknown"
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
        )
    except OSError:
        return "unknown", True
    return commit, dirty


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
