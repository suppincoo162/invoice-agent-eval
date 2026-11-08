# configs/ — 场景配置面（可替换层）

本目录存放**可替换的场景配置**，用于证明评测器的流程拓扑层是数据、不是代码。

## 目录内容

| 文件 | 作用 |
|---|---|
| `workflow-variant-strict-no-supplement.json` | 场景变体：**不允许向用户追问补充信息**的自助开票流程。与竞赛版 15 步完全相同，唯一差异是 `COLLECT_INVOICE_DATA` 的合法转移少了 `WAIT_USER_SUPPLEMENT` 一条。 |

## 怎么验证它是真的配置驱动

```bash
# 基线 vs 变体，同一批轨迹，零代码改动
python scripts/demo-scenario-variant.py
```

预期输出（**2026-11-08 实测**，格式可能随演示脚本演进而变化）：

```text
INV-V01    baseline_better        insufficient_evidence  100/70  0/70 ← 变
    └ A 成功 是→否 · B 成功 否→否 · 根因 ['AMOUNT_BASIS'] →['INSUFFICIENT_EVIDENCE', 'AMOUNT_BASIS']
INV-V03    baseline_better        insufficient_evidence  100/50  0/50 ← 变
...
结论：2/8 个 Case 的判定随配置改变
```

> [!NOTE]
> 变体下 A 被判「证据不足」而非「流程违规」：官方根因标签白名单没有"流程违规"标签，
> 按既有映射归入 `INSUFFICIENT_EVIDENCE`；这不是本次新增逻辑，详见
> `docs/50-deliverables/extensibility.md` §二。

## 哪些东西在这里换，哪些不能（诚实边界）

| 层 | 载体 | 换场景是否要改代码 |
|---|---|---|
| **流程拓扑**（步骤表 / 顺序 / 必选 / 合法转移 / 事件要求） | `docs/00-brief/data/01_竞赛版流程字典.json` 或本目录的变体 | ❌ **不用** |
| **Case 与轨迹** | `docs/00-brief/data/*.jsonl` | ❌ 不用 |
| **业务规则**（金额口径、实体归一、确认、回调、重复控制、商品匹配等） | `invoice_eval/*.py` | ✅ **要**——这些规则按本赛题 15 个 step_id 实现，全包实测 70 处 step_id 字符串引用 |

详见 `docs/50-deliverables/extensibility.md`（含逐模块耦合度与接入新领域的成本估算）。

> [!NOTE]
> 本目录的变体是**演示与回归用配置**，不参与正式 `submission` 生成——正式提交始终使用 `01_竞赛版流程字典.json`。
