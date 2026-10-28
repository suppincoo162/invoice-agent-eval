# 术语与枚举对照

> 状态：**骨架**（枚举值必须与 `06_提交格式.schema.json` / `07_数据字典` **逐字一致**）

## 结果码 `result_code`

| 码 | 含义 | 判读要点 |
|---|---|---|
| `E100` | 进行中 | 含等待用户补充 / 等待确认 / 等待回调。**≠ 失败** |
| `E200` | 模拟开票成功 | |
| `E400` | 任务失败 | 业务规则阻断 **或** 外部回调失败；是否"正确处理"须结合参考结果 |
| `E500` | 任务超时 | |
| `E600` | 转人工处理 | |
| `E700` | 任务终止 | |
| `E800` | 用户取消 | |

## 步骤状态 `step_status`

- `WAITING_USER` —— 步骤/截取状态，**不是"模型必然失败"**

## 根因标签（14 个，来自 schema enum）

| 标签 | 判定边界 |
|---|---|
| `INTENT_CLASSIFICATION` | 开票/红票/取消等**任务意图或类型**识别错误 |
| `ENTITY_RESOLUTION` | 多购方候选却擅自选择，或选错 |
| `FIELD_FABRICATION` | 必填字段缺失/含糊时**自行编造** |
| `AMOUNT_BASIS` | 含税 vs 不含税**口径理解反** |
| `AMOUNT_CALCULATION` | 口径对但**金额/税额算错** |
| `PRODUCT_MATCH` | 商品项目与用户描述不匹配 |
| `TOOL_ARGUMENT_ERROR` | 预览正确但**传参改变** |
| `MULTI_ITEM_OMISSION` | 批量任务遗漏或错误合并 |
| `CONTEXT_UPDATE` | 多轮修改后**继续用旧值** |
| `DUPLICATE_CONTROL` | 忽略重复开票风险 |
| `CONFIRMATION_BYPASS` | 未确认就尝试提交 |
| `TOOL_ERROR_HANDLING` | 超时/未知状态**错误重试或错误降级** |
| `CALLBACK_MISINTERPRETATION` | 无视明确失败回调、误报成功 |
| `INSUFFICIENT_EVIDENCE` | 轨迹不足以可靠定根因 |

## 扣分维度 `penalty_items[].dimension`（4 个）

`BUSINESS_RESULT` · `PROCESS` · `TOOL_CALL` · `RISK_CONTROL`

## 版本比较 `version_comparison`

- `direction`：`baseline_better` / `candidate_better` / `equal` / `insufficient_evidence`
- `release_recommendation`：`release` / `gray` / `defer` / `investigate`
