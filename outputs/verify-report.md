# 确定性评测回归报告

> 生成时间：2026-11-08 20:10:52 ｜ 代码版本：`c98f7b2-dirty` ｜ 由 `python scripts/verify.py` 自动生成，请勿手改。

## 1. 五阶段结论

| # | 阶段 | 结论 | 说明 |
|---|---|---|---|
| 1 | 单元/回归测试 | ✅ 通过 | 112 passed in 0.18s |
| 2 | 训练集归因回归 | ✅ 通过 | 14 Case / 28 run 全部一致 |
| 3 | 验证集 + 官方校验 | ✅ 通过 | 8 Case / 16 run 格式 exit 0，覆盖完整 |
| 4 | 确定性复跑 | ✅ 通过 | 两次运行输出逐字节相同 |
| 5 | Rubric 双轨校验 | ✅ 通过 | 14/28 与 8/16 公式、封顶和正式方向不变量全部通过 |

> ⚠️ **口径提示**：下表「布尔结论」（是否处理正确 / 是否生成发票）与 「质量分」是**两套口径**——前者回答「做对没有」，后者是 100 分起扣的惩罚性打分。两者不可互相替代，也不应合并成单一「成功率」。

## 2. 逐 Case 结果（布尔结论 vs 质量分）

| 数据集 | Case | 版本方向 | A 处理正确 | B 处理正确 | A 质量分 | B 质量分 |
|---|---|---|---|---|---:|---:|
| 训练 | INV-T01 | baseline_better | ✅ 是 | ❌ 否 | 100 | 20 |
| 训练 | INV-T02 | candidate_better | ❌ 否 | ✅ 是 | 70 | 100 |
| 训练 | INV-T03 | baseline_better | ✅ 是 | ❌ 否 | 100 | 50 |
| 训练 | INV-T04 | candidate_better | ❌ 否 | ✅ 是 | 70 | 100 |
| 训练 | INV-T05 | baseline_better | ✅ 是 | ❌ 否 | 100 | 50 |
| 训练 | INV-T06 | candidate_better | ❌ 否 | ✅ 是 | 70 | 100 |
| 训练 | INV-T07 | baseline_better | ✅ 是 | ❌ 否 | 100 | 70 |
| 训练 | INV-T08 | baseline_better | ✅ 是 | ❌ 否 | 100 | 50 |
| 训练 | INV-T09 | candidate_better | ❌ 否 | ✅ 是 | 70 | 100 |
| 训练 | INV-T10 | baseline_better | ✅ 是 | ❌ 否 | 100 | 50 |
| 训练 | INV-T11 | baseline_better | ✅ 是 | ❌ 否 | 100 | 50 |
| 训练 | INV-T12 | candidate_better | ❌ 否 | ✅ 是 | 70 | 100 |
| 训练 | INV-T13 | candidate_better | ❌ 否 | ✅ 是 | 70 | 100 |
| 训练 | INV-T14 | baseline_better | ✅ 是 | ❌ 否 | 100 | 70 |
| 验证 | INV-V01 | baseline_better | ✅ 是 | ❌ 否 | 100 | 70 |
| 验证 | INV-V02 | candidate_better | ❌ 否 | ✅ 是 | 50 | 100 |
| 验证 | INV-V03 | baseline_better | ✅ 是 | ❌ 否 | 100 | 50 |
| 验证 | INV-V04 | candidate_better | ❌ 否 | ✅ 是 | 70 | 100 |
| 验证 | INV-V05 | baseline_better | ✅ 是 | ❌ 否 | 100 | 70 |
| 验证 | INV-V06 | equal | ✅ 是 | ✅ 是 | 100 | 100 |
| 验证 | INV-V07 | baseline_better | ✅ 是 | ❌ 否 | 100 | 70 |
| 验证 | INV-V08 | candidate_better | ❌ 否 | ✅ 是 | 70 | 100 |

## 3. 汇总

- 整体：**通过**（5/5 阶段）
- 复跑命令：`python scripts/verify.py`
