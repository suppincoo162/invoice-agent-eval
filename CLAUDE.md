# CLAUDE.md — 宿主入口适配器

> **本文件不是规则源。** 本项目的规则唯一规范源是 [`AGENTS.md`](AGENTS.md)；本文件只负责把
> Claude Code 引导过去，自身不维护任何独立规则。两者若有差异，**以 `AGENTS.md` 为准**。

## 启动指令

1. 读 [`AGENTS.md`](AGENTS.md) —— 项目规则、五条硬约束、开工前必读清单
2. 读 [`docs/README.md`](docs/README.md) —— 六层文档导航
3. 看 [`docs/40-plan/tasks.md`](docs/40-plan/tasks.md) —— **现在在推什么**（唯一活台账）

## 一句话背景

**评估已执行的开票 Agent，不是实现开票 Agent。**（云帐房 AI 大赛 · 赛题三）

## 当前阶段（as of 2026-10-31）

**阶段 A（备料·事实层）已完成，尚未写任何代码。** 下一步是定 4 个判据
（证据不足门槛 / 首因判据 / `quality_score` 口径 / 确定性-模型边界）。
**判据没定之前不要写判定逻辑。** 详情见 `AGENTS.md`「当前阶段」。
