# -*- coding: utf-8 -*-
"""一条命令跑完确定性评测的完整回归闭环。

为什么有这个脚本（2026-11-08 加）：
    竞赛评审指引里写明"沉淀测试案例，形成评测、优化与持续回归闭环"是加分方向，
    而此前四个环节虽然都存在，却分散在四条互不相干的命令里——
    没有入口、没有统一结论、失败也不知道坏在哪一环。

用法：
    python scripts/verify.py                 # 全量（含 pytest）
    python scripts/verify.py --skip-tests    # 跳过 pytest，只跑评测回归
    python scripts/verify.py --report outputs/verify-report.md

四个阶段（任一失败 ⇒ 整体 exit 1，但**其余阶段仍会跑完**，便于一次看到全部问题）：
    1. 单元/回归测试       pytest -q
    2. 训练集归因回归       14 Case / 28 run  对比 03_公开训练参考标注
    3. 验证集 + 官方校验    8 Case / 16 run   过 08_提交格式校验.py
    4. 确定性复跑          同一输入跑两遍，输出必须逐字节相同

设计取舍：
    - 不引入任何第三方依赖（评审机器未必装 pytest，故第 1 阶段失败只提示不装包）。
    - 报告里的「布尔结论」与「quality_score」**分列**，并显式注明两者口径不同、
      不可互相替代——这是评审最容易混淆、也最容易被认为是"打分不合理"的地方。
    - 不修改正式 submission，产物只写到 --report 指定的位置。
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# Windows 控制台默认 GBK，✅/❌ 会抛 UnicodeEncodeError（实测）。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover - 非 reconfigure 支持的宿主
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "docs" / "00-brief" / "data"

# 以 `python scripts/verify.py` 方式运行时，sys.path[0] 是 scripts/ 而不是项目根
# ⇒ 这里显式补上项目根，保证 `import invoice_eval` 在任意 cwd 下都成立。
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

WORKFLOW_PATH = DATA_DIR / "01_竞赛版流程字典.json"
TRAIN_CASES = DATA_DIR / "02_公开训练轨迹.jsonl"
TRAIN_REFERENCE = DATA_DIR / "03_公开训练参考标注.jsonl"
VALID_CASES = DATA_DIR / "04_无标注验证轨迹.jsonl"
OFFICIAL_VALIDATOR = DATA_DIR / "08_提交格式校验.py"


@dataclass
class StageResult:
    name: str
    ok: bool
    detail: str = ""
    rows: list[dict] = field(default_factory=list)


def _python() -> str:
    return sys.executable or "python"


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_python(), "-m", "invoice_eval", *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


# ── 阶段 1：单元/回归测试 ────────────────────────────────────────────────
def stage_tests() -> StageResult:
    env = os.environ.copy()
    # 评测机的全局 pytest 插件可能启动无关服务（例如 pyvirtualdisplay/Xvfb）。
    # 本仓库测试只依赖 pytest 核心与标准库，禁用第三方插件自动加载以保证可复现。
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    proc = subprocess.run(
        [_python(), "-m", "pytest", "-q", "--no-header"],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode == 0:
        tail = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        return StageResult("单元/回归测试", True, tail[-1] if tail else "pytest 通过")
    # pytest 未安装（ModuleNotFoundError）⇒ 退化为 unittest discover
    if "No module named pytest" in proc.stderr or "No module named 'pytest'" in proc.stderr:
        alt = subprocess.run(
            [_python(), "-m", "unittest", "discover", "-s", "tests", "-q"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        ok = alt.returncode == 0
        return StageResult(
            "单元/回归测试",
            ok,
            "pytest 未安装 ⇒ 已用 unittest discover 代替："
            + ("通过" if ok else alt.stderr.strip()[-300:]),
        )
    return StageResult("单元/回归测试", False, (proc.stdout + proc.stderr).strip()[-600:])


# ── 阶段 2：训练集归因回归（有专家标注，逐 run 对账）─────────────────────
def _root_map(root_causes: list[dict]) -> dict[str, tuple]:
    """根因 → (首错, 证据元组)。

    ⚠️ 证据元组**按序比较**（不放宽）：同一根因的证据顺序变了也算不一致——
    这是有意选择的严格口径，与 `tests/test_training_regression.py` 保持一致。
    """
    return {
        str(root.get("label")): (
            root.get("first_fault_event_id"),
            tuple(root.get("evidence_event_ids") or ()),
        )
        for root in root_causes
    }


def stage_training() -> StageResult:
    from invoice_eval import evaluate_case, load_dataset, load_workflow

    dataset = load_dataset(TRAIN_CASES)
    workflow = load_workflow(WORKFLOW_PATH)
    reference = {item["case_id"]: item for item in _read_jsonl(TRAIN_REFERENCE)}

    mismatches: list[str] = []
    rows: list[dict] = []
    compared_runs = 0
    for case in dataset.cases:
        actual = evaluate_case(case, workflow)
        expected = reference.get(case.case_id)
        if expected is None:
            mismatches.append(f"{case.case_id}: 参考标注缺失")
            continue
        rows.append(_summary_row(case.case_id, actual, labelled=True))

        # 🔴 2026-11-08 复核修（对抗测试实测）：原实现对 run 列表直接 zip，
        # 参考标注少写 run 时会**静默截断并判通过**（假绿）。现显式校验长度。
        actual_runs = actual["run_assessments"]
        expected_runs = expected.get("run_assessments", [])
        if len(actual_runs) != len(expected_runs):
            mismatches.append(
                f"{case.case_id}: run 数 {len(actual_runs)} ≠ 标注 {len(expected_runs)}"
                "（数据/标注不同步，不能判一致）"
            )
            continue
        compared_runs += len(actual_runs)

        if actual["version_comparison"]["direction"] != expected.get(
            "version_direction_on_this_case"
        ):
            mismatches.append(
                f"{case.case_id}: 方向 {actual['version_comparison']['direction']} "
                f"≠ 标注 {expected.get('version_direction_on_this_case')}"
            )
        for actual_run, expected_run in zip(
            actual["run_assessments"], expected.get("run_assessments", [])
        ):
            rid = actual_run["run_id"]
            for key in ("agent_task_success", "business_invoice_created"):
                if actual_run[key] != expected_run.get(key):
                    mismatches.append(
                        f"{rid}: {key} {actual_run[key]} ≠ 标注 {expected_run.get(key)}"
                    )
            if _root_map(actual_run["root_causes"]) != _root_map(
                expected_run.get("root_causes", [])
            ):
                mismatches.append(f"{rid}: 根因/首错/证据 与标注不一致")

    # 反向覆盖：参考标注里存在、数据集里却没有的 Case（同样不能静默放过）
    dataset_ids = {c.case_id for c in dataset.cases}
    uncovered = sorted(set(reference) - dataset_ids)
    if uncovered:
        mismatches.append(f"参考标注存在但数据集缺失的 Case：{uncovered}")

    ok = not mismatches
    detail = (
        f"{len(dataset.cases)} Case / {compared_runs} run 全部一致"
        if ok
        else f"{len(mismatches)} 处不一致：" + "；".join(mismatches[:6])
    )
    return StageResult("训练集归因回归", ok, detail, rows)


# ── 阶段 3：验证集 + 官方格式校验 ────────────────────────────────────────
def stage_validation(workdir: Path) -> StageResult:
    out = workdir / "submission-validation.jsonl"
    proc = _run_cli(["--help"])
    if proc.returncode != 0:
        return StageResult("验证集 + 官方校验", False, f"CLI 不可用：{proc.stderr[-300:]}")

    proc = _run_cli(
        ["evaluate", "--cases", str(VALID_CASES), "--output", str(out)]
    )
    if proc.returncode != 0:
        return StageResult(
            "验证集 + 官方校验", False, f"evaluate 失败：{proc.stderr.strip()[-400:]}"
        )

    validator = subprocess.run(
        [
            _python(),
            str(OFFICIAL_VALIDATOR),
            "--cases",
            str(VALID_CASES),
            "--submission",
            str(out),
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    rows = _summary_rows_from_submission(out)
    # 🔴 2026-11-08 复核加：官方校验器只查格式，不查"是否每个 Case 都出了结果"。
    # 少了 Case 也照样 exit 0 ⇒ 这里必须自己补覆盖校验。
    expected_cases = [item.get("case_id") for item in _read_jsonl(VALID_CASES)]
    produced = _read_jsonl(out)
    produced_ids = [item.get("case_id") for item in produced]
    missing_cases = [cid for cid in expected_cases if cid not in produced_ids]
    bad_runs = [
        f"{item.get('case_id')} (run 数 {len(item.get('run_assessments') or [])})"
        for item in produced
        if len(item.get("run_assessments") or []) != 2
    ]
    coverage_ok = not missing_cases and not bad_runs
    ok = validator.returncode == 0 and coverage_ok
    # 官方校验器在 Windows 上按 GBK 输出；这里不用它的文案（避免乱码），只取退出码结论。
    if ok:
        detail = f"{len(produced_ids)} Case / {len(produced_ids) * 2} run 格式 exit 0，覆盖完整"
    elif not coverage_ok:
        detail = f"覆盖不完整：缺 Case {missing_cases}；run 数异常 {bad_runs}"
    else:
        detail = (
            f"官方校验失败（exit {validator.returncode}）： "
            + _decode_console(validator.stdout)[-300:]
        )
    return StageResult("验证集 + 官方校验", ok, detail, rows)


def _decode_console(text: str) -> str:
    """把按 GBK 输出、被 utf-8 解码成乱码的控制台文本尽量还原。"""
    if not text:
        return ""
    try:
        return text.encode("utf-8", errors="ignore").decode("gbk", errors="ignore")
    except Exception:
        return text


def _summary_rows_from_submission(path: Path) -> list[dict]:
    """从 submission JSONL 按 Case 汇总成一行（A/B 两列）。

    ⚠️ 不能按 run 展平：展平后 A/B 会各占一行，表格看起来像"同一 Case 出现两次"。
    """
    rows = []
    for item in _read_jsonl(path):
        runs = item.get("run_assessments", [])
        a = runs[0] if len(runs) > 0 else {}
        b = runs[1] if len(runs) > 1 else {}
        rows.append(
            {
                "case_id": item.get("case_id"),
                "dataset": "验证",
                "direction": item.get("version_comparison", {}).get("direction"),
                "a_success": a.get("agent_task_success"),
                "b_success": b.get("agent_task_success"),
                "a_score": a.get("quality_score"),
                "b_score": b.get("quality_score"),
            }
        )
    return rows


def _summary_row(case_id: str, result: dict, labelled: bool) -> dict:
    runs = result.get("run_assessments", [])
    a = runs[0] if len(runs) > 0 else {}
    b = runs[1] if len(runs) > 1 else {}
    return {
        "case_id": case_id,
        "dataset": "训练",
        "direction": result.get("version_comparison", {}).get("direction"),
        "a_success": a.get("agent_task_success"),
        "b_success": b.get("agent_task_success"),
        "a_score": a.get("quality_score"),
        "b_score": b.get("quality_score"),
        "labelled": labelled,
    }


# ── 阶段 4：确定性复跑（可复现性证据）───────────────────────────────────
def stage_determinism(workdir: Path) -> StageResult:
    first = workdir / "determinism-1.jsonl"
    second = workdir / "determinism-2.jsonl"
    for target in (first, second):
        proc = _run_cli(
            ["evaluate", "--cases", str(VALID_CASES), "--output", str(target)]
        )
        if proc.returncode != 0:
            return StageResult(
                "确定性复跑", False, f"evaluate 失败：{proc.stderr.strip()[-300:]}"
            )
    same = first.read_bytes() == second.read_bytes()
    return StageResult(
        "确定性复跑",
        same,
        "两次运行输出逐字节相同" if same else "两次运行输出**不同** ⇒ 存在非确定性来源",
    )


# ── 报告渲染 ──────────────────────────────────────────────────────────────
def _git_head() -> str:
    """报告绑定代码版本——没有 HEAD 的报告无法证明"这份结论对应哪份代码"。"""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=10,
        )
        head = proc.stdout.strip() or "unknown"
    except Exception:
        return "unknown"
    # 🔴 2026-11-08 复核修：只报 HEAD 会掩盖"工作树有未提交改动"——
    # 那种情况下报告其实对应「HEAD + 未提交改动」，必须显式标 dirty。
    try:
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        dirty = ""
    return f"{head}-dirty" if dirty else head


def render_report(stages: list[StageResult], report_path: Path) -> None:
    lines: list[str] = []
    lines.append("# 确定性评测回归报告")
    lines.append("")
    lines.append(
        f"> 生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
        f"｜ 代码版本：`{_git_head()}` ｜ 由 `python scripts/verify.py` 自动生成，请勿手改。"
    )
    lines.append("")
    lines.append("## 1. 四阶段结论")
    lines.append("")
    lines.append("| # | 阶段 | 结论 | 说明 |")
    lines.append("|---|---|---|---|")
    for idx, stage in enumerate(stages, 1):
        mark = "✅ 通过" if stage.ok else "❌ 失败"
        lines.append(f"| {idx} | {stage.name} | {mark} | {_cell(stage.detail)} |")
    lines.append("")
    lines.append(
        "> ⚠️ **口径提示**：下表「布尔结论」（是否处理正确 / 是否生成发票）与 "
        "「质量分」是**两套口径**——前者回答「做对没有」，后者是 100 分起扣的惩罚性打分。"
        "两者不可互相替代，也不应合并成单一「成功率」。"
    )
    lines.append("")

    case_rows = [row for stage in stages for row in stage.rows if row.get("case_id")]
    if case_rows:
        lines.append("## 2. 逐 Case 结果（布尔结论 vs 质量分）")
        lines.append("")
        lines.append("| 数据集 | Case | 版本方向 | A 处理正确 | B 处理正确 | A 质量分 | B 质量分 |")
        lines.append("|---|---|---|---|---|---:|---:|")
        for row in case_rows:
            lines.append(
                "| {ds} | {case} | {direction} | {a} | {b} | {as_} | {bs} |".format(
                    ds=row.get("dataset") or "—",
                    case=row.get("case_id"),
                    direction=row.get("direction") or "—",
                    a=_bool(row.get("a_success", row.get("success"))),
                    b=_bool(row.get("b_success")),
                    as_=_score(row.get("a_score", row.get("score"))),
                    bs=_score(row.get("b_score")),
                )
            )
        lines.append("")

    total_ok = all(stage.ok for stage in stages)
    lines.append("## 3. 汇总")
    lines.append("")
    lines.append(f"- 整体：**{'通过' if total_ok else '未通过'}**"
                 f"（{sum(1 for s in stages if s.ok)}/{len(stages)} 阶段）")
    lines.append(f"- 复跑命令：`python scripts/verify.py`")
    lines.append("")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def _cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def _bool(value) -> str:
    if value is True:
        return "✅ 是"
    if value is False:
        return "❌ 否"
    return "—"


def _score(value) -> str:
    return "—" if value is None else str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="跑完确定性评测的完整回归闭环（四阶段）。"
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "verify-report.md",
        help="报告输出路径（默认 outputs/verify-report.md）",
    )
    parser.add_argument("--skip-tests", action="store_true", help="跳过 pytest 阶段")
    parser.add_argument("--json", action="store_true", help="以 JSON 打印阶段结论")
    args = parser.parse_args(argv)

    stages: list[StageResult] = []
    with tempfile.TemporaryDirectory(prefix="invoice-eval-verify-") as tmp:
        workdir = Path(tmp)
        if not args.skip_tests:
            stages.append(stage_tests())
        stages.append(stage_training())
        stages.append(stage_validation(workdir))
        stages.append(stage_determinism(workdir))

    render_report(stages, args.report)

    if args.json:
        print(
            json.dumps(
                [
                    {"stage": s.name, "ok": s.ok, "detail": s.detail}
                    for s in stages
                ],
                ensure_ascii=False,
                indent=1,
            )
        )
    else:
        print("=" * 78)
        print("确定性评测回归闭环")
        print("=" * 78)
        for stage in stages:
            print(f"  {'✅' if stage.ok else '❌'} {stage.name}")
            print(f"      {stage.detail}")
        print("-" * 78)
        passed = sum(1 for s in stages if s.ok)
        print(f"  结论：{'全部通过' if passed == len(stages) else '有失败'} "
              f"（{passed}/{len(stages)} 阶段）")
        print(f"  报告：{args.report}")

    return 0 if all(stage.ok for stage in stages) else 1


if __name__ == "__main__":
    sys.exit(main())
