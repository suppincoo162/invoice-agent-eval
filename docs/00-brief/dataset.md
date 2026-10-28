# 数据结构与字段陷阱

> 状态：**骨架**（待从数据字典 + 实际数据双向校验）

## 文件清单（`data/`）

| 文件 | 用途 |
|---|---|
| `01_竞赛版流程字典.json` | 15 个步骤 + 状态/结果码/可能后续步骤 |
| `02_公开训练轨迹.jsonl` | 14 Case / 28 运行（带参考目标） |
| `03_公开训练参考标注.jsonl` | 训练集专家归因 |
| `04_无标注验证轨迹.jsonl` | 8 Case / 16 运行（**无专家归因**） |
| `05_提交结果示例.json` | 一条公开 Case 的完整输出样例 |
| `06_提交格式.schema.json` | 输出契约（JSON Schema） |
| `07_数据字典与业务规则.md` | 字段定义 + 题内计算口径 |
| `08_提交格式校验.py` | 本地格式检查 |
| `09_模拟客户与商品档案.json` | 独立汇总档案 |
| `10_版本评测报告模板.md` | 报告模板 |

## 结构速查

```
Case
├── case_id / scenario / user_request / context
├── reference_result          # 题内预期（不是专家评分！）
└── runs[2]                   # 基线版 + 候选版
    ├── run_id / agent_version / task_id / trace_id
    ├── final_state / snapshot_state / workflow_terminal
    ├── invoice_created
    ├── resource_usage
    └── events[]              # 按 seq 排序
        ├── event_id / seq / step_id / module / action / step_status
        ├── error_code / error_message / retry_count
        ├── observed_input / observed_output
        └── tool_calls[]      # attempt 从 1 开始
```

## 🔴 已知陷阱（**这几条决定对错**）

1. **`WAITING_USER` / `E100` 不是失败** —— 等待用户补充/确认/回调时，正确 Agent 就该停在这里，`invoice_created=false`
2. **`E400` 也可能是正确处理** —— 业务规则阻断或外部回调失败时，如实报告 + 停止重试 = 正确
3. **`reference_result` ≠ 专家评分** —— 它只是题内预期业务状态；训练集的专家标签在单独文件里
4. **`retry_count=2` 意味着该事件列了 3 次调用**（attempt 从 1 开始）—— 别用 `retry_count` 当调用次数
5. **批量/红票不能只看 `line_count`** —— 必须核 `line_items` 明细与 `original_invoice_id`
6. **不得引用其他 run 的事件编号**
7. **不得把单 Case 结论外推为整体版本结论**

## 待补清单

- [ ] 15 个 step_id 与 module 的实际分布（统计 `02_` 与 `04_`）
- [ ] 每种 scenario 的覆盖情况（哪些题库里有、哪些没有）
- [ ] observed_input/output 的字段结构（逐 step_id 归纳）
- [ ] tool_calls 的 tool 种类清单
