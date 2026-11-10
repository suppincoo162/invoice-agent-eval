# invoice-agent-eval v0.3.0

- 发布目标：AI 开票 Agent 离线轨迹评测
- 基线提交：`f1081648a726f3d4c3de5a8d25dff18e2701d932`
- 数据包版本：`student-1.0`
- 运行环境：Python 3.10+，正式评测仅使用标准库
- 提交结果：8 Case / 16 run
- 回归入口：`python3 scripts/verify.py --with-rubric`

## 主要内容

- 分开输出 `agent_task_success` 与 `business_invoice_created`；
- 确定性流程、金额、确认、风控、红票、批量和工具异常校验；
- 根因、首错、传播证据和 A/B 版本方向；
- 可选 LLM 独立审计、四源对照和事实/推断/未知分析；
- `impact-aware-dual-v1` Rubric 双轨旁路；
- 官方七节版本报告和离线只读 WebUI；
- 训练/验证回归、官方格式校验和确定性复跑。

## 验证

详见 `VERIFY-REPORT.md`。发布包要求来自 clean commit；提交结果已通过官方
`08_提交格式校验.py`。

## 边界

- 验证集没有官方逐 run 标签，版本方向是评测程序预测。
- 训练集全部一致不代表隐藏测试集准确率。
- LLM 输出不进入正式评分主链路。
- 全部客户、商品、发票和工具响应均为合成沙箱数据。
