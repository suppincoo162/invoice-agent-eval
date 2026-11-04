# 方法说明（比赛交付物）

> 版本：deterministic-v0.2.0（2026-11-04）
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
- 不使用 LLM，不调用外部模型 API。
- 因此当前版本不需要模型置信度，也不会输出没有校准依据的 `confidence`。

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
| 严重 | 50 | `CONFIRMATION_BYPASS`、`DUPLICATE_CONTROL`、`CALLBACK_MISINTERPRETATION`、`TOOL_ERROR_HANDLING` |
| 普通错误 | 30 | 其余可扣分根因，包括金额、意图、实体、商品、批量、上下文、提交参数等 |

约束：

- 同一 `(label, first_fault_event_id)` 只扣一次；
- 不因布尔值为 false 再额外扣分；
- 等待、取消、保护性拒绝和外部失败本身不扣分；
- `INSUFFICIENT_EVIDENCE` 不生成 penalty；
- 不可评分时以 `quality_score=0` 作为 schema 哨兵，并在解释中注明“不代表质量为 0”，批量均值排除该样本。

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
