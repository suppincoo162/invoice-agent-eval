# LLM 独立盲审试点（INV-V03）

> 状态：**本地 Ollama 试点完成**。盲审输出独立保存，不修改正式 `submission.jsonl`，也不进入正式评分。

## 试点配置

| 项 | 内容 |
|---|---|
| Case | `INV-V03` |
| 模型 | 本地 `deepseek-r1:8b`；云端 `deepseek-flash` |
| 接口 | OpenAI-compatible `/chat/completions` |
| Prompt 版本 | `llm-audit-v4` |
| temperature | `0` |
| 超时 | 300 秒 |
| 正式评测 | 不变，仍使用 `deterministic-v0.2.1` 规则 |

## 输入边界

模型输入仅包括：

- 原始 Case；
- A/B run、events、tool calls；
- 流程字典；
- 业务规则。

不包含确定性评测结果、训练集专家标签、人工结论或其他 Case 的答案。

## 盲审结果

| Run | 处理正确 | 发票生成 | 根因 | 首错 |
|---|---:|---:|---|---|
| V03-A | true | false | 无 | 无 |
| V03-B | false | false | `FIELD_FABRICATION` | `INV-V03-B-05` |

版本方向：

```text
baseline_better
```

本地与云端模型的核心判断一致。

## 本地与云端差异

| 项目 | 本地 `deepseek-r1:8b` | 云端 `deepseek-flash` |
|---|---|---|
| V03-A | true / false | true / false |
| V03-B | false / false | false / false |
| 根因 | `FIELD_FABRICATION` | `FIELD_FABRICATION` |
| 首错 | `INV-V03-B-05` | `INV-V03-B-05` |
| 方向 | `baseline_better` | `baseline_better` |
| B 根因证据 | `B-05` | `B-05`、`B-06`、`B-07` |
| B run 证据范围 | `B-01`～`B-06` | `B-04`～`B-07` |

云端模型更接近确定性评测器的传播链判断，纳入了预览事件 `B-07`；
本地模型只引用首因 `B-05`。云端额外包含验证事件 `B-06`，它是流程上下文，
但不是金额传播的必要证据。

比较汇总：

```text
core_diagnosis_agree=true
root_evidence_agree=false
assessment_evidence_agree=false
fully_agree=false
```

这证明“结论一致”不等于“证据范围完全一致”。

## 与确定性评测对比

一致项：

- 两个 run 的处理正确性；
- 两个 run 的发票生成事实；
- 根因标签和首错事件；
- 版本方向。

差异项：

- 确定性根因证据：`INV-V03-B-05`、`INV-V03-B-07`；
- 本地模型根因证据：仅 `INV-V03-B-05`；
- 云端模型根因证据：`INV-V03-B-05`、`INV-V03-B-06`、`INV-V03-B-07`；
- 本地模型漏掉传播证据 `B-07`；
- 云端模型抓到 `B-07`，但同时包含非必要的流程事件 `B-06`。

因此比较结果不是完全一致，但也说明：

- 两个不同模型都可以独立判断主要结论；
- 模型仍可能在证据范围上偏离；
- 确定性校验和证据比较不能省略；
- 不能用多数投票替代真实轨迹事实。

## 复现

```bash
INVOICE_EVAL_LLM_MODEL=deepseek-r1:8b \
INVOICE_EVAL_LLM_BASE_URL=http://127.0.0.1:11434/v1 \
python3 -m invoice_eval audit \
  --cases docs/00-brief/data/04_无标注验证轨迹.jsonl \
  --output outputs/llm-review-v03.jsonl \
  --case-id INV-V03 \
  --rules docs/00-brief/rules.md \
  --timeout 300 \
  --cache-dir outputs/llm-cache

python3 -m invoice_eval compare-audit \
  --submission outputs/validation-v021.jsonl \
  --llm-review outputs/llm-review-v03.jsonl \
  --output outputs/audit-comparison-v03.jsonl \
  --case-id INV-V03
```

云端：

```bash
INVOICE_EVAL_LLM_MODEL=deepseek-flash \
INVOICE_EVAL_LLM_BASE_URL=https://api.deepseek.com \
INVOICE_EVAL_LLM_API_KEY="$INVOICE_EVAL_LLM_API_KEY" \
python3 -m invoice_eval audit \
  --cases docs/00-brief/data/04_无标注验证轨迹.jsonl \
  --output outputs/llm-review-v03-deepseek.jsonl \
  --case-id INV-V03 \
  --rules docs/00-brief/rules.md \
  --timeout 120 \
  --cache-dir outputs/llm-cache-deepseek
```

## 限制

- 这是单个无官方标签 Case 的试点，不代表模型整体准确率。
- 本地模型在早期 Prompt 下返回过非法根因枚举和错误开票事实，均被程序校验拦截。
- 该结论不能外推到全部验证集或隐藏集。
