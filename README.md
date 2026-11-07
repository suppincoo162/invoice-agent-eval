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

## 运行与环境（依赖说明）

- **环境**：Python **≥ 3.10**（用到 `X | Y` 类型标注语法）。
- **第三方依赖：无**。全部为标准库（`argparse` / `json` / `pathlib` / `dataclasses` / `decimal` / `typing` / `collections`），**不需要 `pip install`**，也无任何 LLM / API / 网络调用。
- **运行**：

  ```bash
  python -m invoice_eval evaluate --cases <cases.jsonl> --output <submission.jsonl>
  ```

- **自测**：`python -m pytest -q`（未装 pytest 时用 `python -m unittest discover -s tests -q`）。
- **官方格式校验**：`python docs/00-brief/data/08_提交格式校验.py --cases <cases> --submission <out>`。

### 可选 LLM 独立盲审

正式评测命令始终使用确定性规则。另有一个独立的 `audit` 命令，可调用
OpenAI-compatible API 或本地 Ollama 对 Case 做盲审，输出单独的
`llm-review.jsonl`，不会修改正式 submission。

```bash
cp .env.example .env
# 编辑 .env 后由当前 shell 读取；不要把 .env 提交到 Git
set -a
source .env
set +a

python -m invoice_eval audit \
  --cases docs/00-brief/data/04_无标注验证轨迹.jsonl \
  --output outputs/llm-review.jsonl \
  --case-id INV-V03 \
  --cache-dir outputs/llm-cache

python -m invoice_eval compare-audit \
  --submission outputs/validation-v021.jsonl \
  --llm-review outputs/llm-review.jsonl \
  --output outputs/audit-comparison.jsonl \
  --case-id INV-V03
```

云端 API 与 Ollama 使用同一接口，只需切换 `BASE_URL` 和 `MODEL`。
API Key 只从 `INVOICE_EVAL_LLM_API_KEY` 读取，不接受命令行参数，也不会写入
审计结果或缓存。

已用本地 `deepseek-r1:8b` 和云端 `deepseek-flash` 完成 `INV-V03` 对照。
两个模型与确定性评测在版本方向、两个布尔值、根因和首错上一致，但证据范围
不同；比较结果单独输出，正式 submission 不受影响。

## 当前状态（**as of 2026-11-07** · 快照，非实时）

> 实时进度只在一处维护：[`docs/40-plan/tasks.md`](docs/40-plan/tasks.md)。以下是带日期的快照，方便"刚拿到仓库的人/Agent"一眼判断该不该往下干。

| 项 | 状态 |
|---|---|
| **所处阶段** | **确定性评测、训练/验证回归、交付文档和 LLM 独立盲审试点已完成；进入决赛打磨** |
| 已完成 | 事实层与四项判据 · JSONL 读取与索引 · 全部确定性规则 · 训练/验证回归 · 确定性归因与评分 · CLI 输出 · [方法说明](docs/50-deliverables/method.md) · [版本报告](docs/50-deliverables/version-report.md) · 可选 OpenAI-compatible/Ollama 盲审 |
| 未完成 | 云端 API 实跑 · 决赛演示材料 · 最终发布包 |
| **下一步** | 配置云端 API 并完成三方对照，见 [`docs/40-plan/tasks.md`](docs/40-plan/tasks.md) |
| 谁能动 | 任何人都可以读；**改 `main` 一律走 MR**（见 [`docs/git-workflow.md`](docs/git-workflow.md)）；`docs/00-brief/data/` 是组委会资料，**只读** |
