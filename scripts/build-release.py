# -*- coding: utf-8 -*-
"""Build a reproducible competition release package from a clean Git commit."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from invoice_eval.version import __version__


def _run(
    args: list[str],
    *,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=capture_output,
        text=True,
        encoding="utf-8",
    )


def _git_status() -> str:
    proc = _run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        capture_output=True,
    )
    return proc.stdout.strip()


def _git_commit() -> str:
    return _run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
    ).stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonl_counts(path: Path) -> tuple[int, int]:
    cases = 0
    runs = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        cases += 1
        runs += len(payload.get("run_assessments") or [])
    return cases, runs


def _render_notes(
    *,
    version: str,
    base_commit: str,
    case_count: int,
    run_count: int,
) -> str:
    return f"""# invoice-agent-eval v{version}

- 发布目标：AI 开票 Agent 离线轨迹评测
- 基线提交：`{base_commit}`
- 数据包版本：`student-1.0`
- 运行环境：Python 3.10+，正式评测仅使用标准库
- 提交结果：{case_count} Case / {run_count} run
- 回归入口：`python3 scripts/verify.py --with-rubric`

## 主要内容

- 分开输出 `agent_task_success` 与 `business_invoice_created`；
- 确定性流程、金额、确认、风控、红票、批量和工具异常校验；
- 根因、首错、传播证据和 A/B 版本方向；
- 可选 LLM 独立审计、四源对照和事实/推断/未知分析；
- `impact-aware-dual-v1` Rubric 双轨旁路；
- 官方七节版本报告和离线只读 WebUI；
- 训练/验证回归、官方格式校验和确定性复跑。

## 验证

详见 `VERIFY-REPORT.md`。发布包要求来自 clean commit；提交结果已通过官方
`08_提交格式校验.py`。

## 边界

- 验证集没有官方逐 run 标签，版本方向是评测程序预测。
- 训练集全部一致不代表隐藏测试集准确率。
- LLM 输出不进入正式评分主链路。
- 全部客户、商品、发票和工具响应均为合成沙箱数据。
"""


def build_release(
    *,
    output_dir: Path,
    validation_path: Path,
    verify_report: Path,
    version: str,
    ref: str,
    allow_dirty: bool,
) -> dict:
    if version.endswith("-dev"):
        raise ValueError("release version must not use a -dev suffix")
    if not validation_path.is_file():
        raise ValueError(f"missing validation submission: {validation_path}")
    if not verify_report.is_file():
        raise ValueError(f"missing verification report: {verify_report}")
    dirty = _git_status()
    if dirty and not allow_dirty:
        raise ValueError(
            "tracked worktree is dirty; commit changes or pass --allow-dirty"
        )
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"invoice-agent-eval-v{version}"
    archive_names = {
        "zip": f"{prefix}-source.zip",
        "tar.gz": f"{prefix}-source.tar.gz",
    }
    for archive_format, filename in archive_names.items():
        _run(
            [
                "git",
                "archive",
                f"--format={archive_format}",
                f"--prefix={prefix}/",
                f"--output={output_dir / filename}",
                ref,
            ]
        )

    shutil.copyfile(validation_path, output_dir / "validation-submission.jsonl")
    shutil.copyfile(verify_report, output_dir / "VERIFY-REPORT.md")
    case_count, run_count = _jsonl_counts(validation_path)
    base_commit = _run(
        ["git", "rev-parse", ref],
        capture_output=True,
    ).stdout.strip()
    notes = _render_notes(
        version=version,
        base_commit=base_commit,
        case_count=case_count,
        run_count=run_count,
    )
    (output_dir / "RELEASE-NOTES.md").write_text(notes, encoding="utf-8")

    manifest = {
        "artifact_type": "competition_release_manifest_v1",
        "version": version,
        "base_commit": base_commit,
        "working_tree_dirty": bool(dirty),
        "generated_on": date.today().isoformat(),
        "dataset_version": "student-1.0",
        "case_count": case_count,
        "run_count": run_count,
        "validation_submission_sha256": _sha256(validation_path),
        "source_zip": archive_names["zip"],
        "source_tar_gz": archive_names["tar.gz"],
    }
    (output_dir / "SUBMISSION-MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    checksum_path = output_dir / "SHA256SUMS"
    checksum_lines = [
        f"{_sha256(path)}  {path.name}"
        for path in sorted(output_dir.iterdir(), key=lambda item: item.name)
        if path.is_file() and path != checksum_path
    ]
    checksum_path.write_text(
        "\n".join(checksum_lines) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a reproducible release package."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--validation",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "validation-v0.3.0.jsonl",
    )
    parser.add_argument(
        "--verify-report",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "verify-report.md",
    )
    parser.add_argument("--version", default=__version__)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="development smoke only; final packages must use a clean commit",
    )
    args = parser.parse_args(argv)
    try:
        manifest = build_release(
            output_dir=args.output_dir.resolve(),
            validation_path=args.validation.resolve(),
            verify_report=args.verify_report.resolve(),
            version=args.version,
            ref=args.ref,
            allow_dirty=args.allow_dirty,
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Release build failed: {exc}")
        return 1
    print(
        f"Built v{manifest['version']} release in {args.output_dir} "
        f"from {manifest['base_commit'][:7]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
