# 系统架构

> 状态：**确定性 MVP 已实现**（2026-11-04）。当前只覆盖 `INV-T01` 所需规则，LLM 默认关闭。

## 当前分层

```text
官方 JSONL + 流程字典
        ↓
invoice_eval/data.py + models.py
  Case / Run / Event 索引
        ↓
workflow.py · amounts.py · confirmation.py · tooling.py
  确定性 findings / root causes
        ↓
scoring.py
  penalty ledger + quality_score
        ↓
evaluator.py
  run assessment + version comparison
        ↓
cli.py
  submission JSONL
```

- 读取层保留完整 `raw`，事件只在所属 run 内索引。
- 规则层只使用同一 run 的真实字段和 `event_id`。
- 评分层只对已证实且责任对象为 Agent 的独立根因扣分。
- LLM 层尚未接入；未来只能处理证据已结构化的语义辅助，不能修改确定性事实和分数。
- 确定性版本不依赖网络或模型，可独立生成 schema 输出。

## 尚未实现

- LLM 语义增强与置信度校准；
- 批量版本报告。

## 一条已定的方向（来自手册）

> 对金额、确认、取消、重复风险等**强约束**，建议采用**确定性校验**；
> 大模型适合处理口语表达、复杂证据组织等难以完全规则化的部分。

⇒ 所以架构上应该是「确定性内核 + 模型外壳」，而不是让模型做全判。
