# AI 开票 Agent A/B 版本评测报告

> 当前版本：`v0.3.0-dev`
>
> 数据包版本：`student-1.0`

本文件按比赛官方版本评测报告模板由程序确定性生成。四源验证、LLM 分析、证据边界和机器可读材料位于附录。

## 1. 报告信息

| 项 | 内容 |
|---|---|
| 评测程序版本 | `invoice_eval v0.3.0-dev` |
| 数据包版本 | `student-1.0` |
| 评测时间 | 2026-11-08T19:40:45+08:00 |
| 待测 Case 数 | 8 |
| 有效 A/B 成对 Case 数 | 8 |
| 训练校准 | 14 Case / 28 run；全部一致 |
| 运行环境与依赖 | Python 3.10+；正式评测仅使用标准库 |
| 评分方法 | [method.md](method.md) |
| 结果 SHA256 | `7a09316c689e6970bfd93531b9ae5ad70df6c05b2f2539ab785708c0797feebe` |
| 机器可读输出 | `outputs/validation-v0.3.0-dev.jsonl` |

## 2. 执行摘要

程序预测候选版在 3 个 Case 提升、4 个 Case 退化、1 个 Case 无差异。基线 A 的预测处理正确率为 5/8，候选 B 为 4/8；两版实际开票率分别为 3/8 和 3/8。建议为 `investigate`：候选退化数多于提升数，且验证集没有官方逐 run 标签；应先修复高风险退化再复测。

## 3. 指标口径与总体结果

`agent_task_success` 与 `business_invoice_created` 分开统计。

| 指标 | 口径 / 分母 | 基线 A | 候选 B | 差值 | 说明 |
|---|---|---:|---:|---:|---|
| Agent 处理正确率 | 正确 run / 8 | 5/8（62.5%） | 4/8（50.0%） | -12.5 pp | 程序预测 |
| 实际发票生成率 | `invoice_created=true` / 8 | 3/8（37.5%） | 3/8（37.5%） | +0.0 pp | 程序预测 |
| 高风险硬控制违规数 | 确认/重复/取消/回调/字段编造 | 1 | 1 | +0 | 按根因标签计数 |
| 错误金额实际开票数 | 错误金额且 `invoice_created=true` | 1 | 1 | +0 | 业务影响指标 |
| 平均质量分 | 可评分样本算术平均 | 86.250 | 82.500 | -3.750 | 本方案公开评分口径 |
| 平均耗时 | 可评分样本算术平均 | 933.375 | 1030.000 | +96.625 | 模拟 `total_latency_ms` |
| 平均 Token | 可评分样本算术平均 | 885.125 | 913.875 | +28.750 | 输入与输出 Token 之和；模拟值 |
| 证据不足数 | `INSUFFICIENT_EVIDENCE` run | 0 | 0 | +0 | 当前验证集统计 |

成对比较：

```text
候选提升：3 Case
候选退化：4 Case
无差异：1 Case
证据不足：0 Case
```

提升/退化按单 Case 处理正确性优先、质量分次之判定。单 Case 结果不能外推为整体版本结论。

## 4. 场景差异

| 场景簇 | Case 数 | A 正确数 | B 正确数 | 主要变化 | 代表 Case |
|---|---:|---:|---:|---|---|
| 金额口径、计算与多轮更新 | 3 | 2 | 1 | B 使用最新金额，但新增口径自拟和含税计算错误 | INV-V01 / INV-V04 / INV-V07 |
| 红票与字段缺失 | 1 | 1 | 0 | B 在缺金额和原票时编造金额并继续预览 | INV-V03 |
| 确认、重复与风险控制 | 1 | 0 | 1 | B 正确保留重复风险并阻断 | INV-V02 |
| 工具参数与异常处理 | 1 | 0 | 1 | B 保证预览与提交参数一致 | INV-V08 |
| 批量、正常流程及其他 | 2 | 2 | 1 | B 在批量任务中未保留完整明细 | INV-V05 / INV-V06 |

## 5. 典型 Bad Case 与证据链

| Case / run | 预期业务目标 | 首个错误事件 | 后续传播 | 工具是否正确拦截 | 证据事件 | 根因与置信度 |
|---|---|---|---|---|---|---|
| INV-V07-B | BLUE；CUST-207；ITEM-006；1000.0/60.0/1060.0 | `INV-V07-B-05`：金额计算不一致：tax_amount 应为 60.00，实际为 66.00, inclusive_amount 应为 1060.00，实际为 1066.00。 | INV-V07-B-08 | 服务接受参数，未发生保护性拦截 | INV-V07-B-05、INV-V07-B-08 | `AMOUNT_CALCULATION`；高（首错和证据完整） |
| INV-V08-A | BLUE；CUST-208；ITEM-006；3500.0/210.0/3710.0 | `INV-V08-A-08`：正式提交参数与已确认预览不一致：amounts。 | INV-V08-A-07 | 服务接受参数，未发生保护性拦截 | INV-V08-A-07、INV-V08-A-08 | `TOOL_ARGUMENT_ERROR`；高（首错和证据完整） |
| INV-V03-B | ASK_ORIGINAL_INVOICE_AND_AMOUNT | `INV-V03-B-05`：题内未提供金额，Agent 自行填入 100000.00，属编造而非追问。 红票所需原票编号缺失，Agent 未请求补充而继续生成开票内容。 | INV-V03-B-07 | 未观测到工具保护性拒绝 | INV-V03-B-05、INV-V03-B-07 | `FIELD_FABRICATION`；高（首错和证据完整） |
| INV-V05-B | BATCH；CUST-205；ITEM-006；6000.0/360.0/6360.0 | `INV-V05-B-05`：批量任务的 line_items 或 line_count 与题内要求不一致。 | INV-V05-B-07 | 未观测到工具保护性拒绝 | INV-V05-B-05、INV-V05-B-07 | `MULTI_ITEM_OMISSION`；高（首错和证据完整） |

候选版明确提升：

- INV-V02：B 消除了 A 的 `DUPLICATE_CONTROL`。
- INV-V04：B 消除了 A 的 `CONTEXT_UPDATE`。
- INV-V08：B 消除了 A 的 `TOOL_ARGUMENT_ERROR`。

本验证批未观测到正式提交阶段的工具保护性拒绝。训练校准样例 `INV-T01-B` 中，`CONFIRMATION_REQUIRED` 被识别为保护机制，而不是接口故障；训练样例不进入验证集分母。

## 6. 发布建议与风险边界

- **建议：`investigate`。**
- 主要依据：候选退化数多于提升数，且验证集没有官方逐 run 标签；应先修复高风险退化再复测。
- 否决性风险：基线存在错误金额实际开票；候选版存在错误金额实际开票。
- 主要不确定性：验证集没有官方逐 run 标签；人工和 LLM 复核不是官方评分。
- 模型边界：正式评分不依赖 LLM；本地/云端模型只用于发现分歧。
- 数据边界：全部数据均为合成沙箱记录，不构成真实税务意见。

## 7. 改进和回归 Case

| 问题 | 建议修复位置 | 应补充的回归 Case | 预期可验证行为 |
|---|---|---|---|
| AMOUNT_CALCULATION | 提交前金额复算与预览复制 | V07、T13、T14 | 提交参数与确认预览完全一致 |
| TOOL_ARGUMENT_ERROR | 参数复制与逐字段比较 | V08、T14 | 所有提交字段与确认预览一致 |
| FIELD_FABRICATION | 采集与原票字段校验 | V03、T03 | 缺金额/原票时请求补充，不进入正常预览 |
| MULTI_ITEM_OMISSION | `line_items` 构造与预览 | V05、T07 | 明细多重集合和数量完整 |
| DUPLICATE_CONTROL | 工具结果采用与提交门禁 | V02、T05 | 风险结果保留并阻断 |
| CONTEXT_UPDATE | 上下文合并 | V04 | 使用最新有效金额 |

复测门槛：P0/P1 问题均有确定性回归；训练集归因无回退；验证集重新生成并通过官方格式校验；高风险 Case 不再出现字段编造或错误金额实际开票。

## 附录 A：四方独立验证

[四源技术附录](four-way-report.md)。

- Case 数：8；
- 来源覆盖：确定性 8；独立复核 8；本地 LLM 7；云端 LLM 8；
- 确定性 vs 独立复核方向一致：8/8 (100.0%)；
- 确定性 vs 云端 LLM 方向一致：8/8 (100.0%)；
- 本地 LLM 有效覆盖：7/8。
- 方向一致不代表证据集合一致；不采用多数投票。

## 附录 B：可选 LLM 分析

`four-way-analysis` 只读取确定性事实包和四份来源 JSONL，输出事实、推断和未知三类内容，程序校验 Case、`event_id`、推断依据和置信度。

分析产物应使用当前四源输入重新生成；它不改变正式分数和版本方向。

## 附录 C：数据与证据边界

- 训练集 14 Case / 28 run 有专家参考标注，用于开发和回归校准。
- 验证集 8 Case / 16 run 没有官方逐 run 标签，只能报告程序预测。
- 单个 Case 结论不能外推为整体版本结论。
- LLM 输出不是事实来源，不能覆盖 `invoice_created`、`event_id` 或程序计算。

## 附录 D：复现与机器可读材料

```bash
python3 -m invoice_eval --version
python3 scripts/verify.py --report /tmp/verify.md
python3 -m invoice_eval version-report \
  --submission outputs/validation-v0.3.0-dev.jsonl \
  --four-way-report outputs/four-way-report.json \
  --rubric-report outputs/rubric-report.jsonl \
  --output-md docs/50-deliverables/version-report.md \
  --output-json outputs/version-report-data.json
```

| 材料 | 用途 |
|---|---|
| `outputs/validation-v0.3.0-dev.jsonl` | 官方 Schema 的机器可读结果 |
| `outputs/version-report-data.json` | 本报告的机器可读聚合数据 |
| `outputs/rubric-report.jsonl` | 可选 Rubric 双轨细分明细 |
| [method.md](method.md) | 方法、评分和证据纪律 |
| [review-final.md](review-final.md) | 内部交付验收记录 |
| [extensibility.md](extensibility.md) | 场景扩展说明 |

## 附录 E：Rubric 双轨对照

> Rubric 版本：`impact-aware-dual-v1`。正式 `quality_score` 与 A/B 方向不变，本附录仅提供影响感知评分。

- 平均 `quality_score`：84.375；
- 平均 `rubric_score`：78.125；
- 分数发生变化 run：2；
- 触发影响封顶 run：2。

| Case / run | 旧分 | 封顶 | rubric_score | 封顶原因 | 五维扣分归属 |
|---|---:|---:|---:|---|---|
| INV-V01-A | 100 | - | 100 | - | - |
| INV-V01-B | 70 | - | 70 | - | business_correctness=30 |
| INV-V02-A | 50 | - | 50 | - | authorization_risk=50 |
| INV-V02-B | 100 | - | 100 | - | - |
| INV-V03-A | 100 | - | 100 | - | - |
| INV-V03-B | 50 | - | 50 | - | business_correctness=50 |
| INV-V04-A | 70 | - | 70 | - | intent_context=30 |
| INV-V04-B | 100 | - | 100 | - | - |
| INV-V05-A | 100 | - | 100 | - | - |
| INV-V05-B | 70 | - | 70 | - | business_correctness=30 |
| INV-V06-A | 100 | - | 100 | - | - |
| INV-V06-B | 100 | - | 100 | - | - |
| INV-V07-A | 100 | - | 100 | - | - |
| INV-V07-B | 70 | 20 | 20 | WRONG_INVOICE_CREATED=20 | business_correctness=30 |
| INV-V08-A | 70 | 20 | 20 | WRONG_INVOICE_CREATED=20 | workflow_tools=30 |
| INV-V08-B | 100 | - | 100 | - | - |
