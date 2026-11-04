# invoice-agent-eval

云帐房 AI 技术创新大赛 · **赛题三：AI 开票 Agent 离线轨迹评测** 参赛仓库。

> 参赛：李经霖 / 王怡然 · 报名截止 2026-11-12 · 初赛截止 2026-11-13

## 这个项目做什么

**评估已执行的开票 Agent，不是实现开票 Agent。**

给定同一业务任务在基线版和候选版下的两条可观测轨迹，本系统要判断：

1. 每次运行是否**按题内规则正确处理**（且必须与"发票是否真正生成"**分开报告**）
2. 失败运行中**首个错误事件**是哪个、如何传播到后续步骤
3. 同一 Case 两个版本的**提升 / 退化 / 无差异**
4. 产出机器可读结果 + 人读版本分析报告

## 先读这个（人或 Agent 都是这三步）

1. **你是谁、按什么规矩干活** → [`AGENTS.md`](AGENTS.md)（项目工作规则；Agent 请优先读它）
2. **文档地图** → [`docs/README.md`](docs/README.md)（六层导航，按编号顺序读）
3. **现在到哪一步了** → 见下方「当前状态」，活台账在 [`docs/40-plan/tasks.md`](docs/40-plan/tasks.md)

快速上手看三处：

- [`docs/00-brief/dataset.md`](docs/00-brief/dataset.md) —— 字段结构 + **必踩的陷阱**
- [`docs/00-brief/rules.md`](docs/00-brief/rules.md) —— **9 条业务规则 × 轨迹里拿什么字段核对**（判对错的第一手依据）
- [`docs/00-brief/labeled-reference.md`](docs/00-brief/labeled-reference.md) —— **官方答案长什么样**

## 目录

| 目录 | 内容 |
|---|---|
| `docs/00-brief/data/` | **官方资料包（只读）**——轨迹、流程字典、数据字典、提交格式、校验脚本 |
| `docs/` | 全部项目文档（六层，见导航） |
| — | 代码目录待定（见 `docs/40-plan/tasks.md`） |

## 数据与合规

- 所有客户、商品、发票、时间、工具响应均为**合成沙箱数据**
- **不得**调用真实开票 / 报税 / 记账系统
- 提交内容只使用本资料包或组委会另行提供的竞赛数据

## 协作

**只用一个 `main` 分支 + 各自本地开发分支 + MR 合并** —— 完整规范见 [`docs/git-workflow.md`](docs/git-workflow.md)。

## 当前状态（**as of 2026-11-04** · 快照，非实时）

> 实时进度只在一处维护：[`docs/40-plan/tasks.md`](docs/40-plan/tasks.md)。以下是带日期的快照，方便"刚拿到仓库的人/Agent"一眼判断该不该往下干。

| 项 | 状态 |
|---|---|
| **所处阶段** | **确定性评测、训练/验证回归和交付文档已完成；进入最终审查与打包** |
| 已完成 | 事实层与四项判据 · JSONL 读取与索引 · 全部确定性规则 · 训练/验证回归 · 确定性归因与评分 · CLI 输出 · [方法说明](docs/50-deliverables/method.md) · [版本报告](docs/50-deliverables/version-report.md) |
| 未完成 | LLM 可选增强 · 提交前审查与最终打包 |
| **下一步** | 审查交付物并决定是否启用可选模型增强，见 [`docs/40-plan/tasks.md`](docs/40-plan/tasks.md) |
| 谁能动 | 任何人都可以读；**改 `main` 一律走 MR**（见 [`docs/git-workflow.md`](docs/git-workflow.md)）；`docs/00-brief/data/` 是组委会资料，**只读** |
