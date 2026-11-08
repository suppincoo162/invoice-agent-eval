# -*- coding: utf-8 -*-
"""场景变体演示：只改配置、不改一行代码，评测行为随之改变。

它证明什么（面向评审的「扩展性」论点）：
    本评测器的**流程拓扑层是数据**——步骤表、必选步、合法转移、事件要求全部来自
    外部 JSON（`docs/00-brief/data/01_竞赛版流程字典.json`）。
    ⇒ 换一个业务场景（例：不允许向用户追问的自助开票流程）只需换一份流程字典，
       **不需要改 Python**。

它不证明什么（诚实边界，别过度宣称）：
    业务规则层（金额、实体、确认、回调、重复控制等）是按**本赛题的 15 个 step_id**
    实现的代码，共约 67 处硬编码 step_id 引用。换一个**全新领域**仍需按域实现规则。
    详见 `configs/README.md` 与 `docs/50-deliverables/extensibility.md`。

用法：
    python scripts/demo-scenario-variant.py
    python scripts/demo-scenario-variant.py --cases docs/00-brief/data/02_公开训练轨迹.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

from invoice_eval import evaluate_case, load_dataset, load_workflow  # noqa: E402

DATA_DIR = PROJECT_ROOT / "docs" / "00-brief" / "data"
BASELINE_WORKFLOW = DATA_DIR / "01_竞赛版流程字典.json"
VARIANT_WORKFLOW = PROJECT_ROOT / "configs" / "workflow-variant-strict-no-supplement.json"
DEFAULT_CASES = DATA_DIR / "04_无标注验证轨迹.jsonl"


def _run_counts(result: dict) -> tuple[int, int]:
    """返回 (扣分项总数, 根因总数)，用于对比两个场景下的判定强度。"""
    penalties = sum(len(r.get("penalty_items") or []) for r in result["run_assessments"])
    roots = sum(len(r.get("root_causes") or []) for r in result["run_assessments"])
    return penalties, roots


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="流程拓扑配置化的最小演示。")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    args = parser.parse_args(argv)

    workflow_base = load_workflow(BASELINE_WORKFLOW)
    workflow_variant = load_workflow(VARIANT_WORKFLOW)
    dataset = load_dataset(args.cases)

    print("=" * 78)
    print("场景变体演示：同一批轨迹 × 两份流程字典（零代码改动）")
    print("=" * 78)
    print(f"  Case 集：{args.cases.name}（{len(dataset.cases)} 个 Case）")
    print(f"  基线：{workflow_base.workflow_id}（{len(workflow_base.steps)} 步）")
    print(f"  变体：{workflow_variant.workflow_id}（{len(workflow_variant.steps)} 步）")
    print("-" * 78)
    print(f"  {'Case':10s} {'基线方向':22s} {'变体方向':22s} {'扣分项':>7s} {'根因':>5s}")
    print("-" * 78)

    changed = 0
    for case in dataset.cases:
        base = evaluate_case(case, workflow_base)
        var = evaluate_case(case, workflow_variant)
        base_dir = base["version_comparison"]["direction"]
        var_dir = var["version_comparison"]["direction"]
        base_pen, base_root = _run_counts(base)
        var_pen, var_root = _run_counts(var)
        mark = " ← 变" if (base_dir != var_dir or base_pen != var_pen) else ""
        if mark:
            changed += 1
        print(
            f"  {case.case_id:10s} {base_dir:22s} {var_dir:22s} "
            f"{base_pen:>3d}→{var_pen:<3d} {base_root:>2d}→{var_root:<2d}{mark}"
        )

    print("-" * 78)
    print(f"  结论：{changed}/{len(dataset.cases)} 个 Case 的判定随配置改变")
    print("  证据：两份流程字典的差异仅在 COLLECT_INVOICE_DATA 的合法转移上（少了"
          " WAIT_USER_SUPPLEMENT 一条），Python 代码零改动。")
    print("  边界：业务规则层仍绑定本赛题 15 个 step_id；全新领域需按域实现规则，"
          "详见 configs/README.md。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
