# 需求规格（What）

> 状态：**部分已定**。本层是"做对"的定义源——与代码冲突时以本层为准。

##  deliverables 级别的验收

| # | 需求 | 验收标准 |
|---|---|---|
| R1 | 批量评估每个 Case 的两条 run | 输出逐行符合 schema；`run_assessments` 恰好 2 条 |
| R2 | **分开**报告 Agent 处理正确性与发票生成 | 两个布尔值独立给出，且**不得合并成单一成功率** |
| R3 | 定位首个错误事件 + 传播链 | 每个 `root_cause` 有 `first_fault_event_id` + `evidence_event_ids` |
| R4 | 版本比较 | `direction` + `release_recommendation` + `reason` 三件齐 |
| R5 | 机器可读 + 人读报告 | JSONL 通过 `08_提交格式校验.py`；报告覆盖批量 Case |
| R6 | 分数口径可复现 | `quality_score` 的构成公开且全 Case 一致适用 |

## 硬约束（不许做什么）

1. **不猜测**：缺必要信息或多候选 ⇒ 判「应追问/应选择」，不得判成"Agent 猜对了"
2. **不虚构根因**：证据不足用 `INSUFFICIENT_EVIDENCE`，并说明缺什么证据
3. **不跨 run 引用事件编号**
4. **不把单 Case 外推为整体版本结论**
5. **不把工具正确拦截归因为接口故障**
6. **不把 `WAITING_USER`/`E100` 直接判失败**
7. **不调用真实开票/报税/记账系统**

## 证据充分性与 `INSUFFICIENT_EVIDENCE` 门槛（T-014）

证据是否充分**按结论分别判断**。同一个 Case 可以确定 `business_invoice_created`，但无法确定根因；此时只对不可靠的结论使用 `INSUFFICIENT_EVIDENCE`，不得把整个 Case 一概判为“证据不足”。

### 最低证据要求

| 结论 | 最低证据 | 证据充分 | 证据不足 |
|---|---|---|---|
| `business_invoice_created` | `run.invoice_created`；存在明确回调时同时核对 `callback_status` | 直接字段存在，且能被同一 run 的明确回调支持 | 直接字段缺失，或直接字段与明确回调冲突且现有规则无法消解 |
| `agent_task_success` | `reference_result`、`context`、同一 run 的关键事件 | 能证明业务目标得到满足，或能用事件证明违反硬约束 | 缺少判断所必需的上下文、字段或事件；无法确认通过，也无法证明违规 |
| `root_causes[]` | 同一 run 的 `event_id`、事件内容和业务规则 | 能定位首个错误事件，并用相关事件支持根因 | 无法定位首错、只有模型猜测，或关键事件互相冲突 |
| `version_comparison` | 两个 run 各自可靠的评估 | 两版均能确定相对提升、退化或无差异 | 任一版不可靠，或现有证据无法支持方向与发布建议 |

`reference_result` 只给出题内业务目标，不是某个 run 已正确执行的证据。训练集 `03_` 的专家标注只用于开发、回归和校准，不得作为验证集或隐藏集上的运行时证据。

### 判定顺序

1. 先确认 Case 的目标、上下文和 run 边界，所有证据只能来自当前 run。
2. 对每个结论检查所需字段、事件和工具结果是否存在。
3. 检查相关证据是否一致；发现冲突时不得擅自选择对结论更有利的一方。
4. 只有证据足以复算或复核时输出结论；不足时明确记录缺失项或冲突项。
5. 每个根因独立判断。一个根因证据充分，不能自动证明另一个根因也充分。

### 不算证据不足的情况

- 正确生成预览后停在 `WAITING_USER`，因此没有后续提交事件。
- 用户取消后流程合法终止。
- 工具按业务规则正确拒绝请求。
- 外部接口明确失败，Agent 如实报告并停止错误重试。
- 已到达合法终态，因此不存在后续步骤。

这些情况下，“没有后续事件”本身就是符合预期的可观测结果，不能当作轨迹缺失。

### 输出约定

- 根因无法可靠确定时，`root_causes[].label` 使用 `INSUFFICIENT_EVIDENCE`。
- 没有可靠首因时，`first_fault_event_id` 为 `null`。
- 如果完全找不到相关证据，`evidence_event_ids` 为空。
- 如果证据来自互相冲突的事件，应列出冲突事件，不能以“证据不足”为由省略。
- `explanation` 必须写清缺少的字段/事件，或冲突发生在哪些事件之间。
- 若 `agent_task_success` 本身无法判断，只能保守输出 `false`，表示“未证明处理正确”，不得同时在解释中声称已证实具体违规。
- 若两个 run 无法形成可靠比较，`version_comparison.direction` 使用 `insufficient_evidence`。

## 首因与传播链判定（T-015）

### 定义

- **首因**：某条 run 中，Agent 首次直接违反一项业务规则的可观测事件。
- **首错事件**：某条根因对应最早的首因事件；一个 run 有多个独立根因时，可以有多个首错事件。
- **传播事件**：在首因之后，复制了错误字段、依据错误结果继续动作，或被错误状态直接导致的事件。
- **独立根因**：违反另一项业务规则、需要单独修复的问题；它不是前序错误的字段/状态复制结果。

`first_fault_event_id` 必须是该根因的 `evidence_event_ids` 之一。`step_status=SUCCEEDED` 不代表事件内容正确，事件内容与状态冲突时以业务规则和可观测字段为准。

### 判定步骤

1. 每个根因单独判断，不先在整条 run 上选一个“唯一首因”。
2. 在该根因对应的业务规则范围内，按同一 run 的 `seq` 从早到晚扫描事件。
3. 找到第一个直接违反规则的事件，将其作为首因。
4. 向后续事件追踪错误字段、工具结果或 `request_id`/状态依赖，识别传播链。
5. 后续事件如果仍只是复制或执行前序错误结果，不新增根因。
6. 后续事件如果引入另一项独立规则偏离，则新增根因，即使它与前序错误出现在同一个事件中。

时间先后本身不能证明因果关系。只有存在字段值复制、工具结果采用、明确的业务状态依赖或请求链路依赖时，才能判定为传播。

### 独立性判据

满足以下任一条件时，应视为独立根因：

- 它违反了与首因不同的业务规则；
- 即使移除或修正首因中的错误字段，该问题仍有自己的直接违规证据；
- 它由另一项必需的前置操作缺失、错误动作或错误解释直接导致，而不是复制首因产生的数据。

不得仅因为两个问题出现在同一个事件、最终都导致失败，或发生在相邻步骤，就合并成一个根因。

### 典型边界

- `INV-T01-B-05` 的口径错误是 `AMOUNT_BASIS` 的首因；`B-07` 的错误预览和 `B-08` 的错误金额参数是传播。
- `INV-T01-B-08` 同时是金额错误的传播事件和 `CONFIRMATION_BYPASS` 的首因；同一事件可以出现在两条根因链中。
- `INV-T05-B-06` 的工具结果已有 `DUPLICATE_INVOICE`，但 Agent 输出将其抹去，首因是该事件本身；后续重复预览是传播。
- `INV-T10-B-09` 的明确失败回调是 `CALLBACK_MISINTERPRETATION` 的首因；`B-10` 的虚假成功说明是传播。
- `INV-T14-B-08` 的提交参数与已确认预览不同，是 `TOOL_ARGUMENT_ERROR` 的首因，不能归因为更早的正确预览。

### 工具、用户和外部服务边界

- 工具正确返回风险或拒绝请求时，不得把工具结果本身记作 Agent 根因。
- 用户输入和外部服务回调是环境事实；只有 Agent 未正确处理这些事实时，才归因给 Agent。
- 保护性拒绝不等于接口故障，明确失败回调也不等于 Agent 必须把失败改成成功。

### 输出约定

- 每个根因分别输出自己的 `first_fault_event_id` 和 `evidence_event_ids`。
- `downstream_impact` 描述错误从首因到后续事件的传播，不额外制造重复根因。
- 无法确认某事件是传播还是独立根因时，不得猜测；按 T-014 输出 `INSUFFICIENT_EVIDENCE` 并说明缺失的依赖证据。

## 质量评分与责任分配（T-016）

### 基本公式

`quality_score` 使用确定性扣分制：

```text
quality_score = clamp(
  100 - 所有已证实且责任对象为 Agent 的独立违规扣分之和,
  0,
  100
)
```

- 从 100 分开始，结果限制在 0–100。
- 每条 penalty 必须对应一个已验证根因和同一 run 的 `evidence_event_ids`。
- 同一 `(root_causes[].label, first_fault_event_id)` 只能扣一次；传播事件不得重复扣分。
- 不因 `agent_task_success=false`、`business_invoice_created=false` 或最终失败再额外扣分，避免同一错误被处罚多次。
- MVP 不设置正向加分；正确等待、正确阻断、正确取消和正确报告外部失败体现为不扣分。

### 责任对象

内部 finding 记录责任对象：`AGENT`、`TOOL`、`USER`、`EXTERNAL` 或 `UNKNOWN`。该字段不写入官方提交 schema。

| 情况 | 责任对象 | 对 Agent 扣分 |
|---|---|---:|
| Agent 错误计算金额、选错字段、跳过确认或忽略风险 | `AGENT` | 是 |
| 工具正确返回风险或拒绝请求 | `TOOL` | 否 |
| 用户未提供必要信息 | `USER` | 否；Agent 未正确追问时，责任转为 Agent |
| 外部服务明确失败 | `EXTERNAL` | 否；Agent 误报成功时才归责 Agent |
| 无法确定责任对象 | `UNKNOWN` | 否；按证据不足处理 |

只有 `actor=AGENT` 的独立根因进入 penalty 计算。工具正确拦截、用户输入缺失和外部失败可以出现在过程说明中，但不能仅因结果不理想而扣 Agent 分。

### 严重程度

| 档位 | 扣分 | 根因 |
|---|---:|---|
| 严重 | 50 | `CONFIRMATION_BYPASS`、`DUPLICATE_CONTROL`、`CALLBACK_MISINTERPRETATION`、`TOOL_ERROR_HANDLING` |
| 普通错误 | 30 | `AMOUNT_BASIS`、`AMOUNT_CALCULATION`、`INTENT_CLASSIFICATION`、`ENTITY_RESOLUTION`、`FIELD_FABRICATION`、`PRODUCT_MATCH`、`MULTI_ITEM_OMISSION`、`CONTEXT_UPDATE`、`TOOL_ARGUMENT_ERROR` |

该权重满足严重错误显著高于一般错误；数值与官方 `INV-T01` 示例一致，但仍是本方案自行定义的可复现口径。

### penalty 维度

| `dimension` | 根因 |
|---|---|
| `BUSINESS_RESULT` | `AMOUNT_BASIS`、`AMOUNT_CALCULATION`、`MULTI_ITEM_OMISSION`、`CALLBACK_MISINTERPRETATION` |
| `PROCESS` | `INTENT_CLASSIFICATION`、`ENTITY_RESOLUTION`、`FIELD_FABRICATION`、`PRODUCT_MATCH`、`CONTEXT_UPDATE` |
| `TOOL_CALL` | `TOOL_ARGUMENT_ERROR`、`TOOL_ERROR_HANDLING` |
| `RISK_CONTROL` | `CONFIRMATION_BYPASS`、`DUPLICATE_CONTROL` |

`INSUFFICIENT_EVIDENCE` 表示评测证据不足，不是 Agent 违规，不生成 penalty。

### 不可评分与证据不足

- 当 `agent_task_success` 本身无法确定，或 `agent_task_success=false` 但无法完成证据充分的 Agent 侧因果归因时，内部标记为 `unscorable`。
- 官方 schema 不允许 `null` 分数，因此 `unscorable` 时输出 `quality_score=0` 作为哨兵值；解释中必须写明“不可评分”，不能把它描述成“质量为 0”。
- 批量统计平均质量分时排除 `unscorable`，不得把哨兵值混入均值。
- 若参与比较的任一 run 不可评分且无法形成可靠粒度比较，`version_comparison.direction` 使用 `insufficient_evidence`。

### 校验示例

- `INV-T01-A`：无 Agent 违规，`quality_score=100`。
- `INV-T01-B`：`AMOUNT_BASIS` 扣 30、`CONFIRMATION_BYPASS` 扣 50，`quality_score=20`；工具拒绝不额外扣分。
- `INV-T05-B`：`DUPLICATE_CONTROL` 扣 50，`quality_score=50`。
- `INV-T14-B`：`TOOL_ARGUMENT_ERROR` 扣 30，`quality_score=70`。

## 待补清单

- [ ] 把四项工作拆成更细的可验收条目
- [x] 明确「证据不足」的判定门槛（什么情况下必须用 INSUFFICIENT_EVIDENCE）
- [x] 明确「首因 vs 连锁后果」的操作性判据
