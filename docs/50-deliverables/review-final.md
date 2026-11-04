# 交付前终审报告（2026-11-04）

> 状态：**一次性复审的结论留痕**。复审对象＝`main`（`dce9a6b`）；复审方式＝只读复跑 ＋ 官方校验器 ＋ 文档一致性核对。
> 结论：**可以交付**。硬验收全部通过；未完成项均为"可选增强"或"打包口径"，不阻塞提交。

## 一、硬验收（每条都是复跑得到的，不是转述）

| 检查项 | 命令 | 结果 |
|---|---|---|
| 单元测试 | `python -m pytest -q` | **68 passed ＋ 27 subtests**（1.0 s 内） |
| CLI 实跑（验证集） | `python -m invoice_eval evaluate --cases 04_无标注验证轨迹.jsonl --output …` | exit 0，输出 **8 行** |
| CLI 实跑（训练集） | 同上，换 `02_公开训练轨迹.jsonl` | exit 0，输出 **14 行** |
| **官方格式校验** | `python docs/00-brief/data/08_提交格式校验.py --cases … --submission …` | 验证集「通过，8 个 Case、16 个 run」；训练集「通过，14 个 Case、28 个 run」；两次 exit 0 |
| 依赖面 | 静态扫描 `invoice_eval/*.py` 的 import | **零第三方依赖**（仅标准库：argparse/json/pathlib/dataclasses/decimal/typing/collections） |

## 二、结构一致性

- `docs/` 六层齐：`00-brief → 10-spec → 20-design → 30-tdd → 40-plan → 50-deliverables`；ADR 机制在用（ADR-001/002/004 已记，ADR-003 本次补记）。
- `docs/40-plan/tasks.md` 每条任务带**证据指针**（文件/测试/行号），可逐条回核——本次复审正是靠它把验收面穷举出来的。
- 交付文档齐：`50-deliverables/method.md`（方法）＋ `version-report.md`（版本报告，明确标注"程序预测 ≠ 专家标签"、结论 `investigate`）。

## 三、二轮复审补的两处（2026-11-04 当天闭环）

1. **题内目标缺失不再默认成功**：`reference_result` 缺 `invoice_should_exist` / `acceptable_snapshot_state` 时，旧逻辑让匹配条件恒为 `True`（可能把"不知道目标"判成成功）。已改为**降级 `INSUFFICIENT_EVIDENCE` 且不可评分**，并补正控/负控各一条。回归证据：改动前后 22 个公开 Case 输出**逐字节一致**。
3. **编造金额漏判已修**：`INV-V03-B` 在题内未给金额时填入 100000，此前无任何规则命中；现按官方标签 `FIELD_FABRICATION`（严重度 50）计入，分数 70→50，候选版均分与基线持平。详见 [`30-tdd/rule-coverage-audit.md`](../30-tdd/rule-coverage-audit.md) §七。
2. **依赖说明补齐**：README 新增「运行与环境（依赖说明）」——Python ≥3.10、**无第三方依赖**、运行与自测命令；同时补 CI（push/PR 自动 `pytest`）与「交付件核对清单」（`40-plan/tasks.md` 阶段 D）。

## 四、仍未完成项（均不阻塞交付）

1. **T-009 接入模型层** 未做；对应 **ADR-003 已定稿：本版不接入**（理由见 ADR-003）。
2. **`QUALITY` 口径提醒**：`quality_score=0` 既表"极差"也当"不可评分哨兵"，若官方按均值排名会拉低——已在 `method.md` 标明，提交时知悉即可。
3. 开发分支 `ljl/dev`、`wyr/dev` 按 `docs/git-workflow.md` 是常驻分支（合并后不删），非缺陷。

## 四、证据边界（这份报告不能证明什么）

- 验证集**没有专家标签** ⇒ 报告里的"预测正确率"是程序口径，不是真值。
- 训练集规模 14 Case / 28 run，规则覆盖密度见 [`30-tdd/rule-coverage-audit.md`](../30-tdd/rule-coverage-audit.md)：**平均不足 1 个 Case/规则**，隐藏集新形态仍是主要风险。
- 本复审**未**评价判据的业务正确性（那需要领域专家逐条确认），只评价"实现与验收链路是否成立"。
