# 内部数据模型

> 状态：**读取与索引已实现**。这是**我们自己程序内部**的内存模型，不是官方文件格式或数据库。

## 已实现结构

- [x] 如何把官方 `Case/Run/Event` 读成内部结构
- [ ] 是否需要中间层（normalized event / evidence graph）
- [ ] 证据引用的表示（event_id 集合？带序关系？）
- [x] 确定性规则引擎的输入输出结构
- [ ] 模型判断层的输入输出结构（含置信度）

`invoice_eval.data.load_dataset(path)` 逐行读取 JSONL，并返回不可变的 `Dataset`。每个容器同时保存：

- `raw`：完整原始 JSON，避免读取层遗漏后续规则需要的字段；
- 类型化字段：读取与定位常用的 `case_id`、`run_id`、`event_id`、`seq`、`step_id` 和 `step_status`；
- 字典索引：`case_by_id`、`run_by_id`、`event_by_id`，查询不到时抛出 `KeyError`。

事件只在所属 run 内建立 `event_id` 索引；读取后按 `seq` 升序保存。JSONL 非法、Case 不是对象、run 数量不是 2，或同一 Case/run 内标识重复时，抛出带文件与行号的 `DatasetFormatError`。

确定性规则层使用同一 run 内的 `RootCause` 表达根因，并转换为带 `BUSINESS_RESULT` / `PROCESS` / `TOOL_CALL` / `RISK_CONTROL` 维度的 `PenaltyItem`。`evaluate_case(case, workflow)` 汇总流程、金额、确认和工具结果，生成单 Case 的两条 run assessment 与版本比较；模型层尚未接入。

## 一条已定的原则

**事件编号是唯一可引用的稳定句柄。** 内部任何结论都必须能回指到 event_id，否则不算证据。
