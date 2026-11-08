# 方法说明（比赛交付物）

> 版本：deterministic-v0.2.1（2026-11-05）
> 唯一规则真源：[`10-spec/spec.md`](../10-spec/spec.md)
> 实现入口：[`invoice_eval/`](../../invoice_eval/)；数据包版本：`student-1.0`

## 一、任务与输出

本系统评估已经执行完的开票 Agent 轨迹，不重新运行 Agent，也不调用真实开票、报税或记账系统。

输入是官方 Case JSONL。每个 Case 包含同一业务任务的基线版 A 和候选版 B 两条 run。系统逐事件解析：

- Case 的请求、上下文和题内目标；
- run 的终态、实际开票结果和资源使用；
- event 的状态、输入、输出、错误和工具调用。

输出是每行一个 Case 的 JSONL，包含两条 run assessment 和一份版本比较，字段遵循官方 `06_提交格式.schema.json`。

## 二、处理流程

```text
Case JSONL + 流程字典
        ↓
读取、校验与同 run 索引
        ↓
确定性规则检查
        ↓
根因、首因、证据与责任对象
        ↓
penalty ledger + quality_score
        ↓
A/B 版本比较
        ↓
提交 JSONL
```

当前确定性模块覆盖：

- 流程入口、合法转移和终态；
- 含税/不含税口径及金额计算；
- 确认前置；
- 购方缺失、消歧和商品匹配；
- 重复开票风险；
- 取消与提交顺序；
- 未知提交状态、重试与幂等键；
- 红票任务类型和原票引用；
- 批量 `line_items` 完整性；
- 回调结果解释；
- 预览到提交参数漂移；
- 多轮上下文更新。

具体字段和优先级见 [`10-spec/spec.md`](../10-spec/spec.md)。

## 三、两个判断分开输出

### `agent_task_success`

表示 Agent 是否遵守本次任务的业务目标和安全流程。`WAITING_USER`、正确取消、工具保护性拒绝和如实报告外部失败都可能是正确处理。

### `business_invoice_created`

直接表示模拟服务是否实际生成发票，来自 run 的 `invoice_created`。该值不受 `agent_task_success` 影响，也不与后者合并成“成功率”。

## 四、确定性校验与模型边界

### 当前版本

- 所有布尔结论、根因、首因、证据和分数均由 Python 确定性代码产生。
- 正式 `evaluate` 不调用 LLM，不依赖外部模型 API。
- 另提供独立 `audit` 可选命令，用于模型盲审和人工复核；其输出不进入正式
  `submission.jsonl`，也不参与正式评分。

### 后续模型增强

LLM 只在确定性事实已经结构化后，辅助复杂语义和解释起草，不能：

- 计算或修改金额；
- 生成、替换或跨 run 引用 `event_id`；
- 直接决定两个布尔结论或 `quality_score`；
- 绕过确认、重复、取消等强约束；
- 从单个 Case 推导整体版本结论。

模型候选结论必须经过事件存在性、同 run、格式和规则一致性校验。模型不可用时，系统仍能输出确定性结果。

## 五、首因与传播链

系统按同一 run 的 `seq` 查找最早直接违反规则的独立事件。只有存在字段复制、工具结果采用、明确状态依赖或请求链路依赖时，后续事件才视为传播。

原则：

- 一个 run 可以有多个独立根因；
- 同一事件可以同时是旧链路的传播和新根因的首因；
- `first_fault_event_id` 必须属于该根因的证据集合；
- 传播事件不重复扣分；
- 只凭时间先后不能推断因果。

根因证据与 run 级证据分开选择：

- `root_causes[].evidence_event_ids` 保留支持该根因的最小链，例如
  `首错事件 + 首个重大下游后果`；
- 存在根因或流程问题时，run 级 `evidence_event_ids` 在根因证据之外补充
  明确回调（若有）和最终业务终态，以同时支持两个布尔结论；
- 无根因的正确完整开票流程覆盖采集、校验、预览、提交、回调和终态；
- 无根因的正确等待流程覆盖采集、校验、预览或补充请求及等待终态；
- 其他正确终止流程至少保留触发正确终止的关键事件和终态。

## 六、工具正确拦截与 Agent 错误

- 工具返回 `CONFIRMATION_REQUIRED`、重复风险或保护性拒绝时，不归因为接口故障。
- Agent 未确认就尝试提交、忽略重复风险或继续取消后的提交时，仍归责 Agent。
- 用户未提供信息、外部服务明确失败时，不因结果不理想直接扣 Agent 分。
- 内部责任对象限定为 `AGENT`、`TOOL`、`USER`、`EXTERNAL` 或 `UNKNOWN`；官方输出 schema 不增加该字段。

## 七、`quality_score`

评分从 100 分开始：

```text
quality_score = clamp(100 - Σ已证实 Agent 独立违规扣分, 0, 100)
```

| 严重度 | 扣分 | 根因 |
|---|---:|---|
| 严重 | 50 | `CONFIRMATION_BYPASS`、`DUPLICATE_CONTROL`、`CALLBACK_MISINTERPRETATION`、`TOOL_ERROR_HANDLING`、**`FIELD_FABRICATION`**（编造金额/字段值，2026-11-04 由 30 提为 50） |
| 普通错误 | 30 | 其余可扣分根因，包括金额、意图、实体、商品、批量、上下文、提交参数等 |

约束：

- 同一 `(label, first_fault_event_id)` 只扣一次（例：`INV-V03-B` 的「缺原票」与「编造金额」同首因事件 ⇒ 合并为一次 50 分）；
- 不因布尔值为 false 再额外扣分；
- 等待、取消、保护性拒绝和外部失败本身不扣分；
- `INSUFFICIENT_EVIDENCE` 不生成 penalty；
- 不可评分时以 `quality_score=0` 作为 schema 哨兵，并在解释中注明“不代表质量为 0”，批量均值排除该样本。

## 七·补、下游影响与依赖链（定性版，2026-11-04）

按 ADR-004 的定性版约定，本版**不做反事实重跑**，只输出**已知确定性依赖链**：当某根因存在时，`downstream_impact` 追加一句依赖链（如 `金额口径 → 金额三元组 → 预览/提交参数`），说明该首因可能影响到的下游环节。它只陈述业务规则里的字段依赖，**不声称"修复后一定会怎样"，也不计算贡献百分比**（守 ADR-001/ADR-004 的禁止项）。

## 八、证据不足、冲突与新场景

- 先按结论分别检查最低证据，不因一个根因不确定就否定整个 Case。
- 缺关键字段/事件、证据冲突或无法归因时，使用 `INSUFFICIENT_EVIDENCE`。
- 没有可靠首因时 `first_fault_event_id=null`；完全无证据时证据数组为空；存在冲突时必须列出冲突事件。
- 合法的提前结束不算缺证据。
- 未知 step、未知状态或无法规则化的新场景不会被强行解释成已有根因。
- 训练集 `03_` 标签只用于开发、回归和校准，不作为验证集或隐藏集运行时证据。

## 九、版本比较

单 Case 比较顺序：

1. 任一 run 不可评分且无法可靠比较时，方向为 `insufficient_evidence`；
2. Agent 处理正确性不同时，正确的一版更好；
3. 正确性相同时比较 `quality_score`；
4. 相同则为 `equal`。

单 Case 方向不能外推为整体版本结论。整体报告基于批量 Case 汇总。

## 十、复现

依赖：Python 3.10+，仅使用标准库。仓库根目录执行：

```bash
python3 -m invoice_eval evaluate \
  --cases docs/00-brief/data/04_无标注验证轨迹.jsonl \
  --output outputs/validation.jsonl
```

官方格式校验：

```bash
python3 docs/00-brief/data/08_提交格式校验.py \
  --cases docs/00-brief/data/04_无标注验证轨迹.jsonl \
  --submission outputs/validation.jsonl
```

测试：

```bash
python3 -m unittest discover -s tests -v
```

## 十一、已知限制

- 验证集没有专家逐 run 标签，版本报告中的正确率和方向是本文评测器的预测，不是官方准确率。
- 训练集 28 条运行已与参考归因一致，但仍存在过拟合训练场景的风险。
- 流程字典是“对外简化”，公开数据中出现 `VALIDATE_DATA → FAIL_TASK` 的实测例外，实现显式保留并记录。
- 当前不使用 LLM；口语表达、未知语义和新组合场景的覆盖仍受确定性规则边界限制。
- 反事实最小修复仍是候选设计，不进入当前评分链路。

## 十二、可选 LLM 独立盲审

- 盲审只读取原始 Case、A/B 轨迹、流程字典和题内业务规则，不读取确定性评测结果或训练标签。
- 模型输出独立的 `llm-review.jsonl`，包含两个布尔判断、根因、首因、证据、版本方向和不确定点。
- 程序自动校验 run 数量、run ID、官方根因枚举、同 run 事件、首错和布尔事实；校验失败即拒绝输出。
- 成功和失败 run 都必须提供非空 assessment evidence；有根因的运行不得标记为成功。
- `business_invoice_created` 必须与 run 的 `invoice_created` 一致，模型不能覆盖事实。
- 支持 OpenAI-compatible 云端 API 和本地 Ollama；模型与 Prompt 版本写入结果，API Key 不进入输出、缓存或日志。
- 模型失败时 `audit` 命令明确报错；正式确定性评测不受影响。
- 另提供 `compare-audit`，比较确定性结果与模型盲审的方向、两个布尔值、根因、首错和证据差异。
- 首个本地试点使用 `deepseek-r1:8b`、`llm-audit-v4` 对 `INV-V03` 完成；方向、布尔值、根因标签和首错一致，但模型没有把 `B-07` 纳入根因证据，因此不能把“结构一致”混同于“证据完全一致”。
- 当前 Prompt 为 `llm-audit-v5`，显式要求成功 run 也提供非空证据，并禁止“有根因但处理成功”的矛盾输出。

## 十三、回归闭环：一条命令复跑四个阶段

> 2026-11-08 加。此前四个环节各自存在但分散在四条命令里——没有入口、没有统一结论、
> 失败也不知道坏在哪一环。现收敛为一个入口。

```bash
python scripts/verify.py                 # 全量（含 pytest）
python scripts/verify.py --skip-tests    # 跳过 pytest，只跑评测回归
python scripts/verify.py --report outputs/verify-report.md   # 指定报告路径
```

四阶段（任一失败 ⇒ exit 1，但**其余阶段仍跑完**，便于一次看到全部问题）：

| # | 阶段 | 断言 |
|---|---|---|
| 1 | 单元/回归测试 | `pytest -q` 全绿（未装 pytest 时自动退化为 `unittest discover`） |
| 2 | 训练集归因回归 | 14 Case / 28 run 的**方向、两个布尔值、根因、首错、证据**与官方参考标注逐项一致 |
| 3 | 验证集 + 官方校验 | 8 Case / 16 run 过 `08_提交格式校验.py`（exit 0） |
| 4 | 确定性复跑 | 同一输入连跑两遍，输出**逐字节相同**（可复现性证据） |

2026-11-08 实测：`4/4 阶段通过`；运行后自动生成 `outputs/verify-report.md`（22 个 Case 的
「布尔结论 vs 质量分」对照表，含生成时间与代码版本）。⚠️ 该文件是**运行产物**，是否纳入
版本控制取决于 `.gitignore` 中 `outputs/` 的设置——评审机器上跑一次 `scripts/verify.py` 即可复现。

> ⚠️ **口径提示**：报告把「是否处理正确 / 是否生成发票」（布尔）与「`quality_score`」
> （100 分起扣）**分两列**呈现。两者是不同口径，不可互相替代，也不应合并成单一"成功率"。

## 十五、LLM 盲审链路契约冒烟（无模型可跑）

> 2026-11-08 加。评分定位里「Qwen-compatible 冒烟」是缺口；在拿到评测方模型之前，
> **链路本身**可以先被证明。

```bash
python scripts/smoke-llm-audit.py            # 正控：合法响应 ⇒ CLI exit 0、产 1 行
python scripts/smoke-llm-audit.py --negative # 负控：非法响应 ⇒ 客户端必须拒绝
```

- 起一个本地 OpenAI-compatible 桩（`/v1/chat/completions`），走**真实 CLI** 完整往返；
- 断言：exit 0、输出 1 行合法 JSONL、`case_id`/run 数符合、请求带 `model` 且 `temperature=0`、
  未配置 Key 时不发 `Authorization`；
- **负控**：桩返回"成功 run 带根因"的非法结果 ⇒ 客户端拒绝（exit≠0、不产文件）。
- **它证明**：接口契约、程序校验、密钥边界、落盘链路；**它不证明**任何模型的质量。
- **真实模型冒烟仍需**：本地 Ollama 拉一个 chat 模型，或评测方/自备 API Key。

## 十四、场景扩展：流程拓扑可配置（实测）

- 流程字典（`01_竞赛版流程字典.json`）是**外部数据**：步骤表、顺序、必选、合法转移、
  事件要求全部来自 JSON；换配置**不需要改 Python**。
- 实测：`python scripts/demo-scenario-variant.py` —— 同一批 8 个验证 Case，换成
  “不允许追问”的变体字典（唯一差异＝采集步少一条合法转移），**2/8 个 Case 判定方向改变**
  （`baseline_better → insufficient_evidence`）。
- **诚实边界**：业务规则层仍绑定本赛题 15 个 `step_id`（全包实测 70 处字符串引用，含注释复核后），
  全新领域需按域实现规则模块。逐模块耦合度、接入成本估算（按覆盖判据面 2–8 天/领域；本项目从零到 v0.2.1 实测 8.2 天）
  与后续收敛路径见 `docs/50-deliverables/extensibility.md`。
