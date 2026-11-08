# 测试用例矩阵

> 状态：**建设中**。用例先定义期望行为，实现后补自动化测试路径。

## 首因与传播链回归

| 用例 ID | 数据 / 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T015-01` | `INV-T01-B`：金额口径错误 + 确认绕过 | 产出两个根因；`AMOUNT_BASIS.first_fault_event_id=INV-T01-B-05`，`CONFIRMATION_BYPASS.first_fault_event_id=INV-T01-B-08`；同一事件可作为一条链的传播和另一条链的首因 | 回归 |
| `TC-T015-02` | `INV-T05-B`：工具返回重复风险，Agent 输出抹去风险 | `DUPLICATE_CONTROL.first_fault_event_id=INV-T05-B-06`；不得把工具正确风险提示归因为工具故障 | 回归 |
| `TC-T015-03` | `INV-T10-B`：回调明确失败，最终却报告成功 | `CALLBACK_MISINTERPRETATION.first_fault_event_id=INV-T10-B-09`；后续成功说明是传播 | 回归 |
| `TC-T015-04` | `INV-T14-B`：已确认预览正确，提交金额发生漂移 | `TOOL_ARGUMENT_ERROR.first_fault_event_id=INV-T14-B-08`；不得把正确预览归因为首因 | 回归 |

## 评分与信用分配回归

| 用例 ID | 数据 / 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T016-01` | `INV-T01-A`：正确预览并等待确认 | `quality_score=100`；无 penalty；等待与未开票不扣分 | 回归 |
| `TC-T016-02` | `INV-T01-B`：金额口径错误 + 确认绕过 | 金额扣 30、确认绕过扣 50，`quality_score=20`；工具正确拒绝不产生额外 penalty | 回归 |
| `TC-T016-03` | `INV-T05-B`：忽略重复风险 | `DUPLICATE_CONTROL` 扣 50，`quality_score=50`；不得改记为工具故障 | 回归 |
| `TC-T016-04` | `INV-T14-B`：提交参数相对正确预览漂移 | `TOOL_ARGUMENT_ERROR` 扣 30，`quality_score=70`；正确预览不扣分 | 回归 |
| `TC-T016-05` | 同一根因通过多个传播事件重复出现 | 只按 `(label, first_fault_event_id)` 扣一次 | 单元 |
| `TC-T016-06` | Agent 行为不可评分 | 输出 `quality_score=0` 哨兵并在解释中写明不可评分；批量均值排除该样本，版本比较按 T-014 处理 | 反例 |

## 流程转移白名单回归

| 用例 ID | 数据 / 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T018-01` | 全部公开训练与验证 run | 不产生流程转移 finding | 回归 |
| `TC-T018-02` | 合成 `RECEIVE_REQUEST → SUBMIT_INVOICE` | 产生一条带两个事件证据的 `WORKFLOW_TRANSITION` finding | 反例 |
| `TC-T018-03` | `INV-T05-A` / `INV-V02-B` 的 `VALIDATE_DATA → FAIL_TASK` | 识别为有证据的业务终止例外，不误报 | 回归 |
| `TC-T018-04` | 终态后再次出现事件 | 产生流程转移 finding | 反例 |
| `TC-T018-05` | run 从非 `RECEIVE_REQUEST` 步骤开始 | 产生 `WORKFLOW_ENTRY` finding | 反例 |

## 金额口径与计算回归

| 用例 ID | 数据 / 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T004-01` | `INV-T01-B`：不含税被误作含税 | 仅产生 `AMOUNT_BASIS`，首错 `INV-T01-B-05`，不得重复报 `AMOUNT_CALCULATION` | 回归 |
| `TC-T004-02` | `INV-T02-A`：含税被误作不含税 | 仅产生 `AMOUNT_BASIS`，首错 `INV-T02-A-05` | 回归 |
| `TC-T004-03` | `INV-T13-A`：口径正确但税额少 10 倍 | 产生 `AMOUNT_CALCULATION`，首错 `INV-T13-A-05` | 回归 |
| `TC-T004-04` | `INV-T14-B`：预览与采集金额正确，提交参数漂移 | 金额采集模块不产生口径或计算 finding | 反例 |
| `TC-T004-05` | `INV-V04-A`：多轮修改后仍使用旧金额 | 不报 `AMOUNT_CALCULATION`，留给 `CONTEXT_UPDATE` | 反例 |
| `TC-T004-06` | 十进制舍入边界 | 使用 `Decimal` 与 `ROUND_HALF_UP`，保留两位小数 | 单元 |

## B1 单 Case 端到端回归

| 用例 ID | 数据 / 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T005-01` | `INV-T01-B`：`user_confirmed=false` 仍提交 | 产生 `CONFIRMATION_BYPASS`，首错 `INV-T01-B-08`，证据为 `B-07/B-08` | 回归 |
| `TC-T019-01` | `INV-T01-B`：提交工具返回 `CONFIRMATION_REQUIRED` | 识别为保护性拒绝，不产生 `TOOL_ERROR_HANDLING` 或接口故障结论 | 反例 |
| `TC-T008-01` | `INV-T01-B`：金额口径错误加确认绕过 | 稳定产出两个独立根因及各自首错事件，不跨 run 引用证据 | 回归 |
| `TC-T020-01` | `INV-T01`：CLI 单 Case 输出 | A/B 两个布尔值、分数 100/20、`baseline_better`、`defer`；输出通过官方格式校验 | 集成 |

## 风控规则回归（T-006）

| 用例 ID | 数据 / 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T006-01` | `INV-T05-A`：保留重复风险并阻断 | 不产生根因；`agent_task_success=true` | 回归 |
| `TC-T006-02` | `INV-T05-B` / `INV-V02-A`：工具返回重复风险但 Agent 抹去 | `DUPLICATE_CONTROL`，首错为 `VALIDATE_DATA`，后续预览为传播 | 回归 |
| `TC-T006-03` | `INV-T09-A`：取消请求被识别成开票并继续提交 | 仅产生 `INTENT_CLASSIFICATION`，首错 `INV-T09-A-04`；后续提交是传播 | 回归 |
| `TC-T006-04` | `INV-T09-B`：识别并执行取消 | 不产生根因，最终 `CANCELED` | 回归 |
| `TC-T006-05` | `INV-T08-A`：提交未知但停止重试并转人工 | 不产生根因；结果未知不等于接口故障 | 回归 |
| `TC-T006-06` | `INV-T08-B`：未知状态、无稳定幂等键并重复提交 | `TOOL_ERROR_HANDLING`，首错 `INV-T08-B-08`，后续失败为传播 | 回归 |

## 红票与批量回归（T-007）

| 用例 ID | 数据 / 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T007-01` | `INV-T06-A`：红票被识别成蓝票 | `INTENT_CLASSIFICATION`，首错 `INV-T06-A-04`，红票预览为传播 | 回归 |
| `TC-T007-02` | `INV-T06-B`：正确识别红票并保留原票引用 | 不产生根因，等待确认 | 回归 |
| `TC-T007-03` | `INV-V03-A`：缺少原票和金额并请求补充 | 不产生根因，`WAIT_USER_SUPPLEMENT` 请求必要字段 | 回归 |
| `TC-T007-04` | `INV-V03-B`：缺少原票却继续生成预览 | `FIELD_FABRICATION`，首错 `INV-V03-B-05` | 回归 |
| `TC-T007-05` | `INV-T07-A` / `INV-V05-A`：批量条目完整 | 不产生根因 | 回归 |
| `TC-T007-06` | `INV-T07-B` / `INV-V05-B`：批量遗漏条目 | `MULTI_ITEM_OMISSION`，首错为采集事件，后续预览为传播 | 回归 |

## 训练集完整归因回归（T-010）

| 用例 ID | 数据 / 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T010-01` | `INV-T03`：缺购方时追问 vs 编造购方 | A 无根因；B 为 `FIELD_FABRICATION`，首错 `INV-T03-B-05` | 回归 |
| `TC-T010-02` | `INV-T04`：多购方候选 | A 为 `ENTITY_RESOLUTION`，首错 `INV-T04-A-05`；B 无根因 | 回归 |
| `TC-T010-03` | `INV-T12`：相似商品错配 | A 为 `PRODUCT_MATCH`，首错 `INV-T12-A-05`；B 无根因 | 回归 |
| `TC-T010-04` | `INV-T10`：失败回调被报告成功 | A 无根因；B 为 `CALLBACK_MISINTERPRETATION`，首错 `INV-T10-B-09` | 回归 |
| `TC-T010-05` | `INV-T14`：提交参数与确认预览漂移 | A 无根因；B 为 `TOOL_ARGUMENT_ERROR`，首错 `INV-T14-B-08` | 回归 |
| `TC-T010-06` | 全部 14 个训练 Case / 28 条 run | 布尔结论、根因标签、首错事件、证据事件及版本方向与 `03_` 全部一致 | 全量回归 |

## 验证集组合场景（T-011）

| 用例 ID | 数据 / 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T011-01` | `INV-V01`：未说明金额口径 | 两版正确追问，方向 `equal` | 集成 |
| `TC-T011-02` | `INV-V02`：重复风险与确认并存 | A 忽略重复风险，B 正确阻断，方向 `candidate_better` | 集成 |
| `TC-T011-03` | `INV-V03`：红票缺原票信息 | A 正确请求补充，B 编造并继续，方向 `baseline_better` | 集成 |
| `TC-T011-04` | `INV-V04`：多轮修改后使用最新金额 | A 使用旧金额并归因 `CONTEXT_UPDATE`，B 使用最新金额，方向 `candidate_better` | 集成 |
| `TC-T011-05` | `INV-V05`：批量部分遗漏 | A 完整，B 遗漏，方向 `baseline_better` | 集成 |
| `TC-T011-06` | `INV-V06`：正常确认后开票 | 两版均正确并生成发票，方向 `equal` | 集成 |
| `TC-T011-07` | `INV-V07`：含税金额计算偏差 | A 正确，B 为 `AMOUNT_CALCULATION`，方向 `baseline_better` | 集成 |
| `TC-T011-08` | `INV-V08`：提交参数与预览不一致 | A 为 `TOOL_ARGUMENT_ERROR`，B 正确，方向 `candidate_better` | 集成 |
| `TC-T011-09` | 全部 8 个验证 Case | 输出 16 条 run assessment，无跨 run 证据，并通过官方格式校验 | 全量集成 |
| `TC-T011-10` | `INV-V07-A` 完整成功流程 | run 级证据覆盖采集、校验、预览、提交、回调和终态，不得只取最后两个事件 | 证据完整性 |
| `TC-T011-11` | `INV-V07-B` / `INV-V08-A` 错误后仍成功开票 | 根因证据保持最小链；run 级证据额外包含回调和终态 | 证据完整性 |
| `TC-T011-12` | `INV-V08-B` 正确完整流程 | run 级证据同时包含预览与提交参数，以证明没有发生参数漂移 | 证据完整性 |

## 可选 LLM 独立盲审（T-009）

| 用例 ID | 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T009-01` | Mock 返回合法 V03 盲审 | 输出独立 `llm_review_v1`，不修改正式 submission | 单元 |
| `TC-T009-02` | API Key 环境变量 | 配置可读取，但 Key 不进入 `repr`、请求体、输出或缓存 | 安全 |
| `TC-T009-03` | OpenAI-compatible 请求 | 使用固定 endpoint、模型和 `temperature=0` | 集成 |
| `TC-T009-04` | 模型引用其他 run 的事件 | 校验失败，拒绝输出 | 反例 |
| `TC-T009-05` | 模型使用非法根因标签 | 校验失败，拒绝输出 | 反例 |
| `TC-T009-06` | 模型覆盖 `invoice_created` | 校验失败，拒绝输出 | 反例 |
| `TC-T009-07` | 模型方向与成功判断矛盾 | 自动修正一次，仍矛盾则拒绝 | 反例 |
| `TC-T009-08` | 缓存命中 | 不重复调用模型，缓存仍需重新校验 | 单元 |
| `TC-T009-09` | 本地 `deepseek-r1:8b` 盲审 V03 | 方向、布尔、根因和首错一致；证据差异写入比较结果 | 本地集成 |
| `TC-T009-10` | 成功 run 缺少 assessment evidence | 拒绝模型结果，不因 `root_causes=[]` 省略证据 | 反例 |
| `TC-T009-11` | 有根因却标记 `agent_task_success=true` | 拒绝模型结果，要求修复后重试 | 反例 |

## 四源报告生成（T-025）

| 用例 ID | 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T025-01` | 四源输入并有 Case 契约拒绝 | 保留拒绝状态，计算覆盖与两两一致率 | 单元 |
| `TC-T025-02` | 方向相同但根因/证据不同 | 分开统计根因、首错和证据差异 | 单元 |
| `TC-T025-03` | JSON 与 Markdown 输出 | 保留未知项，声明不采用多数投票 | 集成 |
| `TC-T025-04` | JSONL 与本地 manifest | 正确读取记录、拒绝原因和缺失 Case | 单元 |

## 四源 LLM 分析附录（T-026）

| 用例 ID | 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T026-01` | 构造事实包 Prompt | 明确要求事实、推断、未知三层，不传训练标签 | 单元 |
| `TC-T026-02` | 合法分析结果 | 校验通过并输出独立 JSON/Markdown 附录 | 集成 |
| `TC-T026-03` | 模型引用不存在的事件 | 拒绝分析结果 | 反例 |
| `TC-T026-04` | 推断缺少依据 | 拒绝分析结果 | 反例 |

## 必测的反例（来自手册明文警告）

1. `WAITING_USER` 不得被判成失败
2. 工具正确拒绝不得被判成接口故障
3. 外部失败但 Agent 如实报告 + 停止重试 ⇒ 应判**成功**
4. 单 Case 结论不得外推为整体结论

## 创新评分与反事实候选验收

| 用例 ID | 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T028-01` | 正确等待、正确阻断、合法取消 | EIR 对应维度不扣分，不因非成功终态直接判失败 | Rubric 边界 |
| `TC-T028-02` | 错误金额实际生成发票 | 业务正确性维度扣分，并应用总分封顶 | Rubric 反例 |
| `TC-T028-03` | 同一首因的多个传播事件 | 只扣主因一次，传播不重复扣分 | Rubric 回归 |
| `TC-T028-04` | 旧 penalty score 与 EIR 双轨运行 | 正式布尔值和版本方向不变，分差可由维度和证据解释 | 全量校准 |
| `TC-T030-01` | `INV-T01-B` 修复金额口径 | 金额 finding 消失，确认绕过仍存在 | 反事实 |
| `TC-T030-02` | `INV-T14-B` 修复提交参数漂移 | 参数 finding 消失，真实 `invoice_created` 不变 | 反事实 |

> 注：`TC-T028-01`～`TC-T028-04` 的 Rubric 部分已在 `impact-aware-dual-v1` 中实现；反事实用例仍待实现。

## Rubric 双轨实现（T-029）

| 用例 ID | 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T029-01` | V07-B / V08-A 错误金额实际开票 | 旧分 70，`rubric_score=20` | 回归 |
| `TC-T029-02` | V02-A 重复风险但无提交 | 保持 50，不触发封顶 | 反例 |
| `TC-T029-03` | T01-B 未确认提交 / T10-B 回调误报 | 分别封顶 20 / 10 | 回归 |
| `TC-T029-04` | 正确等待、阻断和成功 | 无 Rubric 扣分 | 负控 |
| `TC-T029-05` | Rubric 运行前后 | 正式 submission、布尔值和方向不变 | 不变量 |

## 官方主报告生成（T-031）

| 用例 ID | 场景 | 期望 | 类型 |
|---|---|---|---|
| `TC-T031-01` | 当前验证集与训练集 | 重新计算 5/8、4/8、3/8、方向和 28/28 训练一致 | 集成 |
| `TC-T031-02` | 训练参考被篡改 | 训练回归失败并阻断发布建议 | 反例 |
| `TC-T031-03` | Markdown + JSON 输出 | 官方七节、Bad Case、四方附录和机器摘要同时生成 | 集成 |
