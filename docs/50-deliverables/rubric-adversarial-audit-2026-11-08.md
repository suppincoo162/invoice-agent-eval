# Rubric 对抗式审计与修复记录（2026-11-08）

> 审计对象：`0506f80 feat(rubric): 增加可选影响感知双轨评分`
>
> 审计方式：三路独立只读 Review：代码不变量、官方要求/报告、边界条件/测试缺口
>
> 最终状态：P0/P1 已修复；完整回归 `117 passed`，Rubric 5/5 阶段通过

## 一、审计时确认正确的部分

- Rubric 不修改正式 submission、`quality_score`、两个布尔值或 A/B 方向。
- V07-B、V08-A 正确从 70 封顶到 20。
- V02-A 在“重复风险但未提交”的情况下保持 50。
- T01-B 确认绕过封顶 20，T10-B 回调误报封顶 10。
- 默认 `verify.py` 仍为原四阶段，只有 `--with-rubric` 才启用第 5 阶段。
- Rubric 当前结果是 8 Case / 16 run，平均旧分 84.375、平均 Rubric 78.125。

## 二、发现并修复的问题

### P0：封顶原因缺少业务结果证据

原实现中 `WRONG_INVOICE_CREATED` 只引用根因事件，例如 V07-B 仅有
`B-05/B-08`，不能直接证明 `B-09/B-10` 实际开票。

修复：

- 错误金额实际开票：补充 `WAIT_INVOICE_CALLBACK` 和 `COMPLETE_TASK`；
- 未确认提交：补充实际 `SUBMIT_INVOICE`；
- 重复风险后提交：补充风险之后的提交事件；
- 回调误报成功：补充回调和终态。

### P1：run 按数组位置配对

原实现用 assessment 数组索引对应 raw run；合法但乱序的 submission 会跨 run
错配轨迹。

修复：

- Rubric 按 `run_id` 映射；
- 校验 submission run ID 集合与 Case 完全一致；
- 输出顺序固定为 Case 中的 A/B 顺序；
- 增加乱序正控测试。

### P1：浮点 quality_score 被截断

原实现使用 `int()`，会把合法的 `82.5` 静默改为 `82`。

修复：

- 保留原 number 类型；
- 拒绝 boolean、null、越界值和非数字；
- 增加 `82.5` 保留测试。

### P1：Rubric 文件加载与来源校验不足

修复：

- Rubric 每行记录 `evaluator_version`、`generated_at` 和
  `source_submission_sha256`；
- `load_rubric_report` 校验 artifact、run 数、run_id、封顶值、公式和证据类型；
- `validate_rubric_report` 校验 Case/run 集合、正式方向、旧分、两个布尔值、
  same-run 证据和 source submission SHA；
- `version-report` 与 `verify --with-rubric` 都调用正式校验器。

### P1：重复风险封顶未检查时序

修复：

- 只有 `SUBMIT_INVOICE.seq` 晚于 `DUPLICATE_CONTROL.first_fault_event_id.seq`
  时才触发 `DUPLICATE_RISK_SUBMITTED`；
- 增加“提交在风险前不封顶”和“提交在风险后封顶”的正反控。

### P1：默认主报告 API 不是完全无侵入

修复：

- 不传 `--rubric-report` 时，附录 D 不再出现 Rubric 命令或文件；
- 只有实际消费 Rubric 时才生成附录 E；
- 增加默认报告不含 Rubric 引用的负控测试。

### P1：报告 provenance 缺失

修复：

- `version-report-data.json` 和主报告增加 Git commit；
- dirty 判定只检查 tracked 修改，不受未跟踪中间产物影响；
- verify 报告使用同一口径；
- 最终 tag 后必须从 clean commit 再生成一次。

### P2：历史设计评估文档过期

修复：

- [design-assessment-2026-11-08.md](design-assessment-2026-11-08.md) 顶部增加历史状态：
  Rubric 已在后续实现，反事实仍未实现。

## 三、最终验证

```text
117 tests passed
训练集 14 Case / 28 run 全部一致
验证集 8 Case / 16 run 官方校验通过
确定性复跑逐字节一致
Rubric 公式、封顶、来源绑定和方向不变量通过
5/5 阶段通过
```

## 四、仍然存在的边界

- Rubric 是可选旁路，正式 `quality_score` 和方向仍使用旧口径。
- 五维只做扣分归属，不做完整加权 EIR。
- 反事实信用分配和静态 HTML UI 尚未实现。
- 验证集没有官方逐 run 标签。
- 最终交稿前仍需从 clean commit 重新生成报告和输出。
