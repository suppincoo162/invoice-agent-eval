# 扩展性说明：哪些可配置、哪些要写代码、接一个新场景要多少成本

> 回答评审指引「仅适用于固定 Agent，新场景接入成本高」这一条。
> 本文只写**实测数字**，不写"架构上支持"这类空话；凡是没验证的都标"未验证"。

## 一、结论先行

| 声明 | 状态 |
|---|---|
| 流程拓扑（步骤/顺序/必选/转移/事件要求）是**外部数据**，换场景不改代码 | ✅ **已实测**（`python scripts/demo-scenario-variant.py`：2/8 Case 判定随配置改变） |
| Case 与轨迹是**外部数据** | ✅ 已实测（换 `--cases` 即可跑任意集） |
| 业务规则层**绑定本赛题 step_id**，全新领域需要按域实现 | ⚠️ **实测 67 处硬编码 step_id 引用**，见 §三 |
| 一次性新增"全新领域"的接入成本 | 📐 估算 **200–400 行新规则模块 + 1 份流程字典 + 1 份 Case 集**（依据见 §四，未实测） |

## 二、可配置面（换场景零代码改动）

| 配置 | 位置 | 作用 |
|---|---|---|
| 流程字典 | `docs/00-brief/data/01_竞赛版流程字典.json` | 15 步步骤表、`required_by_default`、`possible_next_steps`、`event_requirement` |
| 场景变体 | `configs/workflow-variant-strict-no-supplement.json` | 同 15 步，但采集步不允许追问 ⇒ 模拟自助场景 |
| Case / 轨迹 | `docs/00-brief/data/02_…jsonl`、`04_…jsonl` | 换 `--cases` 即可评测任意数据集 |
| 业务规则文本 | `docs/00-brief/rules.md` | 供 `audit` 盲审的提示词素材（不参与确定性判定） |

**实测证据**（2026-11-08，`scripts/demo-scenario-variant.py`）：

```text
INV-V01    baseline_better        insufficient_evidence    1→1    1→2  ← 变
INV-V03    baseline_better        insufficient_evidence    1→1    1→2  ← 变
结论：2/8 个 Case 的判定随配置改变
```

两份字典的差异**只有一行转移**，Python 代码零改动 ⇒ 流程拓扑确实是数据。

## 三、耦合度实测：业务规则层绑定 step_id

统计方法：在 `invoice_eval/*.py` 中检索 15 个 step_id 的**字符串字面量**出现次数。

| 模块 | 硬编码 step_id | 说明 |
|---|---:|---|
| `invoice_types.py` | 17 | 任务类型/红票识别与步骤序列绑定 |
| `risk_controls.py` | 11 | 确认旁路、重复控制等安全规则 |
| `evaluator.py` | 10 | 主流程编排与降级判定 |
| `amounts.py` | 9 | 金额口径、计算、编造检测 |
| `entities.py` | 8 | 实体归一与歧义消解 |
| `conversation.py` | 3 | 对话轮次/追问判定 |
| `callbacks.py` / `confirmation.py` / `submission.py` | 各 2 | 回调、确认、提交校验 |
| `tooling.py` / `workflow.py` | 各 1–2 | 工具参数、拓扑校验 |
| **合计** | **67** | —— |

⇒ **诚实结论**：这不是"通用评测框架"，而是"**一个领域内、拓扑可配置**"的评测器。
这一点必须主动写在文档里——评审最反感的是把有限能力说成无限能力。

## 四、接一个全新领域要什么（估算依据）

按现有模块体量反推（每个规则模块 80–120 行，覆盖一类判据）：

| 步骤 | 工作量 | 是否可复用 |
|---|---|---|
| 1. 写流程字典 | 0.5 天（15 步左右） | ✅ 结构完全复用 |
| 2. 写 Case 与轨迹数据 | 1–2 天（取决于领域） | ⚠️ 需人工构造或采集 |
| 3. 写领域规则模块（金额/实体/确认等按域重写） | **2–4 天**（200–400 行） | ❌ 不可复用，这是产品本体 |
| 4. 写回归用例 | 0.5–1 天（可套 `scripts/verify.py`） | ✅ 框架复用 |
| **合计** | **约 4–7 天/领域** | 框架与工具链免费，规则不免费 |

> 对照：如果从零写一个同水平的评测器（流程 + 规则 + 测试 + 官方校验 + 报告），按本项目
> 的提交历史估算约 **3 周**。⇒ 接入新领域的边际成本约为**从零开始的 1/4**。

## 五、如果要做到"任意领域低成本接入"，缺什么（提案，未实现）

1. **规则注册表**：把 11 个规则模块收敛为 `RuleSet` 协议（`check(case, run) -> findings`），
   按领域注册，`evaluator` 只依赖协议、不依赖具体模块 ⇒ 67 处硬编码可降到个位数。
2. **step_id 语义别名层**：流程字典里给每个 step 标注 `semantic_role`（如 `collect` / `confirm` / `submit`），
   规则按角色而非按 ID 匹配 ⇒ 换领域只需映射角色。
3. **回归模板**：`scripts/verify.py` 已具备，接入新领域时直接复用四阶段。

这三条是"扩展性"从**拓扑级**升到**领域级**的路径，当前**均未实现**——写在这里是为了
让评审看到"边界在哪、往哪走"，而不是假装已经做到了。

## 六、怎么验证本文的每一条

```bash
python scripts/verify.py                      # 四阶段回归（含 22 Case 全量）
python scripts/demo-scenario-variant.py       # 拓扑配置化演示（2/8 判定改变）
python scripts/verify.py --report outputs/verify-report.md   # 生成报告
```
