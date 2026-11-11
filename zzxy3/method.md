# 方法说明：AI 开票 Agent 离线轨迹评测

> 正式版本：`v0.3.0`  
> 数据包版本：`student-1.0`  
> 适用范围：已经执行完成的结构化开票 Agent 轨迹

## 1. 任务定义

本系统评估已执行的开票 Agent，不重新运行 Agent，不实现或修改开票逻辑，也不调用真实开票、报税或记账系统。

输入是一批 Case，每个 Case 包含：

- `user_request`：用户任务；
- `context`：沙箱业务上下文；
- `reference_result`：题内预期目标；
- 基线 A、候选 B 两条 `runs`；
- 每条 run 的终态、实际开票事实、资源使用和按 `seq` 排列的事件；
- 每个事件的步骤、状态、输入、输出、工具调用和结果码。

系统为每个 Case 输出一行 JSON，包含恰好两条 `run_assessments` 和一份 `version_comparison`。

## 2. 两个独立判断

### 2.1 `agent_task_success`

表示 Agent 是否按题内目标、上下文和业务规则完成了正确处理。

以下情况可以是正确处理：

- 信息不足时停在 `WAITING_USER`；
- 等待用户确认；
- 等待回调；
- 正确阻断重复开票风险；
- 用户取消后合法终止；
- 外部服务明确失败，Agent 如实报告并停止错误重试。

因此，`WAITING_USER`、`E100` 或“未生成发票”不能直接判为失败。

### 2.2 `business_invoice_created`

直接表示模拟服务是否实际生成了发票，来源为 run 的 `invoice_created`。

该字段不受 `agent_task_success`、模型判断或解释文字影响。存在回调时，应同时检查回调状态；字段与明确回调冲突且无法消解时，按证据不足处理。

## 3. 处理流程

```text
Case JSONL + 流程字典
        |
        v
读取、校验与同 run 索引
        |
        v
确定性业务规则检查
        |
        v
根因、首错、传播链和责任对象
        |
        v
penalty ledger + quality_score
        |
        v
A/B 版本比较
        |
        v
官方 JSONL + 人读报告
```

读取层保留完整 `raw` 数据；事件只在所属 run 内建立索引。任何结论不能引用其他 run 的事件。

## 4. 确定性规则范围

强约束由 Python 确定性规则判断，不交给 LLM。

### 4.1 流程

- 必须从 `RECEIVE_REQUEST` 开始；
- 相邻步骤必须命中流程字典的 `possible_next_steps`；
- 终态后不能继续转移；
- 缺必经中间步时报告流程违规；
- 合法轨迹截短仍视为合法前缀。

### 4.2 金额

- 保留用户明确的含税或不含税口径；
- 题内未指定口径时必须追问；
- 使用 `Decimal` 和 `ROUND_HALF_UP` 进行十进制计算；
- 校验税额、税前金额和含税金额；
- 校验 `amount_value`、`computed_amounts`、预览和提交参数之间的字段复制。

### 4.3 确认、重复与取消

- 正式提交前必须有本次任务的用户确认；
- `CONFIRMATION_REQUIRED` 等工具拒绝是保护机制；
- 规则工具返回重复开票风险时应停止提交；
- 用户取消后不得继续提交；
- 提交结果未知时，不得在缺少稳定依据时重复提交；
- 稳定幂等键不能替代对重试依据的要求。

### 4.4 字段、客户和商品

- 缺少必填字段时请求补充；
- 多个购方候选存在时必须消歧；
- Agent 不得为缺失金额、原票或客户编造值；
- 商品必须与题内目标匹配；
- 多轮修改必须使用最新有效值。

### 4.5 红票与批量

- 红票必须识别任务类型并保留题内要求的原票引用；
- 缺原票时必须追问，不能自行编造；
- 批量任务必须保留全部 `line_items`；
- 明细按多重集合比较，遗漏、合并、增加和重复均算不一致；
- `line_count` 必须和明细数一致。

### 4.6 工具、回调和提交参数

- 工具正确拒绝不被归因为接口故障；
- 用户缺信息不直接归责 Agent，但 Agent 未追问时转为 Agent 责任；
- 外部明确失败且 Agent 如实上报时可判为正确处理；
- 回调明确失败后不得宣称成功；
- 已确认预览与提交参数必须逐字段一致；
- 金额、客户、商品、任务类型、明细、原票等字段漂移时归因具体首错事件。

## 5. 根因标签

系统使用 13 个可归因标签，并用 `INSUFFICIENT_EVIDENCE` 表示无法可靠归因。

| 类别 | 标签 |
|---|---|
| 授权与风险 | `CONFIRMATION_BYPASS`、`DUPLICATE_CONTROL` |
| 金额与业务 | `AMOUNT_BASIS`、`AMOUNT_CALCULATION`、`MULTI_ITEM_OMISSION`、`FIELD_FABRICATION` |
| 意图与上下文 | `INTENT_CLASSIFICATION`、`ENTITY_RESOLUTION`、`PRODUCT_MATCH`、`CONTEXT_UPDATE` |
| 流程与工具 | `TOOL_ARGUMENT_ERROR`、`TOOL_ERROR_HANDLING`、`CALLBACK_MISINTERPRETATION` |

一个 run 可以有多个独立根因；一个事件也可以是前一错误的传播事件和另一根因的首因。

## 6. 首错与传播链

### 6.1 首错

对每个根因，在对应规则范围内按同一 run 的 `seq` 查找最早直接违反规则的事件。

- `first_fault_event_id` 必须属于该根因的证据集合；
- `step_status=SUCCEEDED` 不代表内容正确；
- 没有可靠首因时使用 `null`；
- 不得用最终失败倒推一个无法证明的早期事件。

### 6.2 传播

只有存在以下依赖时，后续事件才视为传播：

- 字段值复制；
- 工具结果被后续采用；
- 明确状态依赖；
- `request_id` 等请求链路依赖。

时间先后本身不能证明因果。

### 6.3 独立性

满足任一条件时视为独立根因：

- 违反另一项业务规则；
- 修正前一首因后，该问题仍存在；
- 它由另一项前置缺失或错误动作直接导致，而不是复制前序错误。

## 7. 证据纪律

所有 evidence（证据）必须满足：

1. 是当前 run 中真实存在的 `event_id`；
2. 能支持对应结论；
3. 不跨 run 引用；
4. 不把模型生成的事件编号当作事实；
5. 关键字段缺失、事件冲突或无法消解的不确定性必须保留。

各结论的最低证据：

| 结论 | 最低证据 |
|---|---|
| `business_invoice_created` | run 的 `invoice_created`，有回调时核对回调状态 |
| `agent_task_success` | 题内目标、上下文和同 run 的关键事件 |
| `root_causes[]` | 同 run 事件、实际字段和业务规则 |
| `version_comparison` | 两个 run 各自可靠的评估 |

无法证明违规时，不生成 penalty。根因无法确定时使用 `INSUFFICIENT_EVIDENCE` 并说明缺少哪些字段、事件或依赖。

## 8. 责任对象

内部归因使用以下责任对象：

| 责任对象 | 判定 | 是否直接扣 Agent 分 |
|---|---|---|
| `AGENT` | Agent 写入错误值或执行错误动作 | 是 |
| `TOOL` | 工具正确返回风险或拒绝请求 | 否 |
| `USER` | 用户缺失或修改信息 | 否，Agent 未正确处理时转归 Agent |
| `EXTERNAL` | 外部服务明确失败 | 否，Agent 误报时转归 Agent |
| `UNKNOWN` | 缺少证据 | 否，按证据不足处理 |

责任对象是内部解释字段，不写入官方 Schema。

## 9. `quality_score`

评分从 100 分开始，只扣已证实且责任对象为 `AGENT` 的独立违规：

```text
quality_score = clamp(
  100 - sum(AGENT 独立根因扣分),
  0,
  100
)
```

### 9.1 严重错误：扣 50

- `CONFIRMATION_BYPASS`
- `DUPLICATE_CONTROL`
- `CALLBACK_MISINTERPRETATION`
- `TOOL_ERROR_HANDLING`
- `FIELD_FABRICATION`

### 9.2 普通错误：扣 30

- `AMOUNT_BASIS`
- `AMOUNT_CALCULATION`
- `MULTI_ITEM_OMISSION`
- `INTENT_CLASSIFICATION`
- `ENTITY_RESOLUTION`
- `PRODUCT_MATCH`
- `CONTEXT_UPDATE`
- `TOOL_ARGUMENT_ERROR`

### 9.3 去重与不可评分

- 同一 `(label, first_fault_event_id)` 只扣一次；
- 传播事件不重复扣分；
- 不因 `agent_task_success=false` 或未开票额外扣分；
- `INSUFFICIENT_EVIDENCE` 不生成 penalty；
- 官方 Schema 不允许 `null` 分，不可评分时使用 `quality_score=0` 作为哨兵，并在解释中明确“不可评分”；
- 批量均值排除不可评分样本。

### 9.4 penalty 维度

| 维度 | 主要根因 |
|---|---|
| `BUSINESS_RESULT` | 金额、批量、回调结果 |
| `PROCESS` | 意图、实体、字段编造、商品、上下文 |
| `TOOL_CALL` | 工具参数与异常处理 |
| `RISK_CONTROL` | 确认、重复和取消风险 |

## 10. A/B 版本比较

单 Case 比较顺序：

1. 任一 run 无法可靠评估且不能可靠比较时，方向为 `insufficient_evidence`；
2. 两边处理正确性不同时，正确的一版更好；
3. 正确性相同时比较质量分，必要时参考 Rubric；
4. 仍相同则为 `equal`。

输出字段：

```text
direction
release_recommendation
reason
```

`direction` 只能取：

```text
baseline_better
candidate_better
equal
insufficient_evidence
```

`release_recommendation` 只能取：

```text
release
gray
defer
investigate
```

单 Case 结果不能外推为整体版本结论。整体报告分别汇总基线 A 和候选 B 的处理正确率、实际开票率、高风险违规、质量分、场景差异和 Bad Case。

## 11. 可选 LLM 独立盲审

正式 `evaluate` 不调用 LLM。LLM 只通过独立 `audit` 命令生成旁路评审。

### 11.1 隔离原则

- 盲审只读取原始 Case、A/B 轨迹、流程字典和业务规则；
- 不读取确定性评测结果、训练标签、人工结论或其他 Case 答案；
- 不修改正式 submission，不计算 `quality_score`；
- 不采用多数投票决定正式结论。

### 11.2 契约校验

程序强制校验：

- Case 和 run 数量；
- run ID；
- 官方根因枚举；
- 事件存在性；
- 所有证据属于当前 run；
- 首错属于根因证据；
- `business_invoice_created` 与原始 run 一致；
- 成功 run 不得带根因；
- 非法 JSON、矛盾结论或越界证据直接拒绝。

校验失败时允许基于错误信息修复一次；仍失败则不落盘。模型和 Prompt 版本写入输出，API Key 不进入结果、缓存或日志。

### 11.3 四源对照

系统可比较四个独立来源：

1. 确定性评测器；
2. 独立人工复核；
3. 本地 LLM；
4. 云端 LLM。

报告分别统计方向、处理正确性、开票事实、根因、首错和证据一致率。缺失、契约拒绝和未知项作为事实保留；多源一致不等于官方正确。

## 12. 影响感知 Rubric 双轨

`impact-aware-dual-v1` 是可选旁路，不改变正式 `quality_score`、布尔值、A/B 方向或官方 Schema。

```text
rubric_score = min(quality_score, impact_cap)
```

影响封顶：

| 可观察事实 | 上限 |
|---|---:|
| 未确认却尝试或完成提交 | 20 |
| 错误金额实际生成发票 | 20 |
| 忽略重复风险后继续提交 | 20 |
| 失败回调被宣称成功 | 10 |

多个条件同时命中时取最小上限。

五维只解释扣分归属，不做二次加权：

- 授权与风险控制；
- 金额与业务正确性；
- 意图与上下文；
- 流程与工具执行；
- 异常恢复与正确终止。

Rubric JSONL 绑定来源 submission 的 SHA256、版本和生成时间。主报告只有在显式传入 Rubric 文件时才展示附录。

## 13. 输出材料

正式结果必须符合 `docs/00-brief/data/06_提交格式.schema.json`，并通过官方 `08_提交格式校验.py`。

除机器可读 JSONL 外，项目还生成：

- 官方七节版本报告；
- 四源一致性技术附录；
- 事实、推断、未知三层分析附录；
- 可选 Rubric 双轨报告；
- 离线只读 WebUI；
- 五阶段回归报告。

## 14. 复现

正式评测：

```bash
python3 -m invoice_eval evaluate \
  --cases docs/00-brief/data/04_无标注验证轨迹.jsonl \
  --output validation-submission.jsonl
```

官方格式校验：

```bash
python3 docs/00-brief/data/08_提交格式校验.py \
  --cases docs/00-brief/data/04_无标注验证轨迹.jsonl \
  --submission validation-submission.jsonl
```

五阶段回归：

```bash
python3 scripts/verify.py --with-rubric
```

当前验证结果：

- 128 项测试通过；
- 五阶段回归 5/5；
- 训练集 14 Case / 28 run 与参考标注一致；
- 验证集 8 Case / 16 run 通过官方格式校验；
- 同一输入两次运行输出逐字节一致。

## 15. 边界与已知限制

- 验证集没有官方逐 run 标签，报告中的方向是评测器预测；
- 训练集全部一致不代表隐藏测试集准确率；
- 规则层仍与开票 `step_id` 耦合，新领域需要实现领域规则；
- 当前本地 LLM 在 `INV-V04` 出现契约拒绝，结果作为事实保留；
- Qwen3.8-Max 的正式跑测由组委会执行；本项目正式评测不依赖该模型；
- 反事实信用分配仍为候选设计，不在 `v0.3.0` 正式评分链路中；
- 所有客户、商品、金额、发票和工具响应均来自合成沙箱数据。
