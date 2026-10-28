# 赛题精读：AI 开票 Agent 离线轨迹评测

> 状态：**已填事实层**（15 步流程 / 9 状态 / 7 结果码 / 数据规模均已实测核实）
> 真源：`docs/00-brief/data/01_竞赛版流程字典.json` 与 `07_数据字典与业务规则.md`

## 赛事基本信息

| 项 | 内容 |
|---|---|
| 主办 | 云帐房科技 · AI 技术创新大赛 |
| 报名截止 | **2026-11-12** |
| 初赛截止 | **2026-11-13** |
| 参赛形式 | 线上完成作品；决赛现场答辩与颁奖 |
| 组队 | 1–2 人，可跨学校跨专业；**本队：李经霖 + 王怡然** |
| 目标赛题 | **赛题三：AI 开票 Agent 离线轨迹评测** |

**奖金池**（税前 10 万元）：卓越奖 30000 · 一等奖 20000 · 二等奖 10000 · 三等奖 5000 · 决赛入围 1000

**人才通道**：晋级复赛有机会校招免笔试/技术面绿色通道；进答辩环节有机会获 Offer 快速评估。

### 相关链接

| 用途 | 链接 |
|---|---|
| 大赛官网 | https://aicxds.yunzhangfang.com/ |
| **赛题三详情** | https://aicxds.yunzhangfang.com/challenge-03.html?v=20261016-7 |
| 报名页 | https://new.saikr.com/vse/yunzhangfang?inc=03ba43db1793090088 |
| 推文详情 | https://mp.weixin.qq.com/s/yeMV75OH-ntQpduImHIORg |
| **参赛仓库**（王怡然建） | https://github.com/suppincoo162/invoice-agent-eval |

> ⚠️ 官网/报名页需要登录态；报名信息以官网为准（本文是 2026-10-28 从组队邀请中记录，可能有变动）。

---

## 一句话

**不是实现开票 Agent，是评估已执行的开票 Agent。** 给定同一业务任务在基线版/候选版下的两条可观测轨迹，判断谁做对了、错在哪、影响多大、哪个版本更好。

## 四项必做工作

1. 判断每次运行是否**按题内规则正确处理** —— 且必须把「Agent 处理是否正确」与「发票是否真正生成」**分开报告**
2. 定位**首个错误事件**，解释错误如何传播，列出支持结论的事件编号
3. 同 Case 比较两版本：局部**提升 / 退化 / 无差异**
4. 产出**机器可读结果** + **人读版本分析报告**

---

## 一、三种任务类型

| code | 类型 | 关键要求 |
|---|---|---|
| `1` | 蓝票 | 常规开票 |
| `2` | 红票 | **必须有原票引用**；缺则要求补充 |
| `3` | 批量开票 | **必须保留全部条目**，遗漏/合并/重复都要识别 |

## 二、15 个流程步骤（**带转移白名单**）

> `→` 后面是**合法的下一步**。这张表是本题最值钱的确定性判据。

| # | step_id | 名称 | 阶段 | 必需 | 合法下一步 |
|---|---|---|---|---|---|
| 1 | `RECEIVE_REQUEST` | 接收开票请求 | 任务接入 | ✅ | `CREATE_TASK` |
| 2 | `CREATE_TASK` | 创建开票任务 | 任务初始化 | ✅ | `RESOLVE_ENTERPRISE` |
| 3 | `RESOLVE_ENTERPRISE` | 识别销方企业 | 上下文识别 | ✅ | `PARSE_INTENT` |
| 4 | `PARSE_INTENT` | 解析用户开票意图 | 意图理解 | ✅ | `CANCEL_TASK` · `COLLECT_INVOICE_DATA` |
| 5 | `COLLECT_INVOICE_DATA` | 采集发票信息 | 信息采集 | ✅ | `VALIDATE_DATA` · `WAIT_USER_SUPPLEMENT` · `TIMEOUT_TASK` |
| 6 | `WAIT_USER_SUPPLEMENT` | 等待用户补充信息 | 人机交互 | ⬜ | `VALIDATE_DATA` · `CANCEL_TASK` · `TIMEOUT_TASK` |
| 7 | `VALIDATE_DATA` | 校验开票数据 | 规则校验 | ✅ | `CONFIRM_INVOICE` · `WAIT_USER_SUPPLEMENT` · `TRANSFER_TO_HUMAN` |
| 8 | `CONFIRM_INVOICE` | 确认开票内容 | 用户确认 | ✅ | `SUBMIT_INVOICE` · `COLLECT_INVOICE_DATA` · `CANCEL_TASK` · `TIMEOUT_TASK` |
| 9 | `SUBMIT_INVOICE` | 提交开票 | 开票执行 | ✅ | `WAIT_INVOICE_CALLBACK` · `TRANSFER_TO_HUMAN` · `FAIL_TASK` |
| 10 | `WAIT_INVOICE_CALLBACK` | 等待开票结果回调 | 结果等待 | ✅ | `COMPLETE_TASK` · `FAIL_TASK` · `TIMEOUT_TASK` |
| 11 | `COMPLETE_TASK` | 完成任务并返回结果 | 任务完成 | ✅ | （终态） |
| 12 | `FAIL_TASK` | 记录失败并返回原因 | 异常终态 | ⬜ | （终态） |
| 13 | `TIMEOUT_TASK` | 任务超时 | 异常终态 | ⬜ | （终态） |
| 14 | `TRANSFER_TO_HUMAN` | 转人工处理 | 人工接管 | ⬜ | （终态） |
| 15 | `CANCEL_TASK` | 取消任务 | 取消终态 | ⬜ | （终态） |

### ⭐ 用这张表做**确定性校验**（不依赖模型）

`possible_next_steps` 天然是一张**白名单**：

- `TRANSFER_TO_HUMAN` **只能**由 `VALIDATE_DATA`(7) 或 `SUBMIT_INVOICE`(9) 到达 → 若从别处跳进来 = **流程违规**
- `SUBMIT_INVOICE` **只能**由 `CONFIRM_INVOICE`(8) 到达 → 若跳过确认直接提交 = **`CONFIRMATION_BYPASS` 的硬证据**
- `COMPLETE_TASK` **只能**由 `WAIT_INVOICE_CALLBACK`(10) 到达

⇒ 这一条应进规则引擎，**100% 确定性判定**，不需要 LLM。

## 三、9 种步骤状态 `step_status`

`PENDING` · `RUNNING` · `WAITING_USER` · `WAITING_CALLBACK` · `SUCCEEDED` · `FAILED` · `SKIPPED` · `CANCELED` · `TIMED_OUT`

⚠️ `WAITING_USER` / `WAITING_CALLBACK` **是正常等待态，不是失败**。

## 四、7 个结果码（含是否终态）

| 码 | 名称 | terminal |
|---|---|---|
| `E100` | 进行中 | **false** ← 非终态，最常见的误判点 |
| `E200` | 开票成功 | true |
| `E400` | 开票失败 | true |
| `E500` | 任务超时 | true |
| `E600` | 转人工处理 | true |
| `E700` | 任务终止 | true |
| `E800` | 任务取消（alias `CANCELED`） | true |

## 五、数据规模与分布（**实测统计**）

| 集合 | Case | 运行数 | 专家归因 |
|---|---|---|---|
| 公开训练 `02_` | **14** | **28** | ✅ 有（`03_`） |
| 无标注验证 `04_` | **8** | **16** | ❌ 无 |

### 🔴 训练集 `final_state` 分布（28 条运行）

| 状态 | 数量 | 占比 |
|---|---|---|
| `WAITING_USER` | **13** | **46%** |
| `SUCCEEDED` | 7 | 25% |
| `FAILED` | 6 | 21% |
| `TRANSFERRED_TO_HUMAN` | 1 | 4% |
| `CANCELED` | 1 | 4% |
| （`invoice_created=true`） | **6** | **21%** |

### 🔴 验证集 `final_state` 分布（16 条运行）

| 状态 | 数量 |
|---|---|
| `WAITING_USER` | **9** |
| `SUCCEEDED` | 6 |
| `FAILED` | 1 |
| （`invoice_created=true`） | **6** |

> [!IMPORTANT]
> **两集里 `WAITING_USER` 都是最大单一状态（46% / 56%），而 `invoice_created=true` 只占约 21%。**
>
> 这用数据印证了手册那句警告：**正确 Agent 大量停在等待态，且大量 Case 的正确结果就是"不开票"**。
> ⇒ 任何"把 WAITING_USER 当失败"或"用开票率衡量成功率"的做法，**开局就会系统性判错一半**。

### 训练集 14 个场景（每个 1 Case，单一考点）

明确不含税金额且尚待确认 · 明确含税金额且已确认 · 缺少购方时应追问 · 同名购方应先消歧 · 重复开票风险应阻断 · 红票任务类型识别 · 批量开票项目完整性 · 提交接口超时与幂等处理 · 用户取消任务 · 开票回调明确失败 · 未经确认不得提交 · 相似商品匹配 · 税额计算错误 · 预览正确但提交参数漂移

### 验证集 8 个场景（**组合场景**）

未说明金额口径的追问 · **重复风险与用户确认并存** · 红票缺少原票信息 · **多轮修改后应使用最新金额** · 批量任务部分项目遗漏 · 正常确认后开票两版均正确 · 含税金额计算偏差 · 提交参数与预览不一致

> **判据**：验证集是**组合场景**（如"重复风险 + 用户确认并存""多轮修改"），训练集是**单一考点**。
> ⇒ 规则要有**组合能力**，不能只对单点打补丁。这一条决定了架构不能是"14 条 if 分支"。

## 六、提交物清单

- [ ] 结果 JSONL（对齐 `06_提交格式.schema.json`）
- [ ] 可运行程序 + 源代码 + 依赖说明
- [ ] 方法说明（含 `quality_score` 构成、确定性/模型分界、置信度校准）
- [ ] 版本评估报告（基于批量 Case）

## 待补清单

- [ ] 题内业务规则 9 条的逐条展开（见 `docs/00-brief/data/07_数据字典与业务规则.md` §二）
- [ ] 「完整示例 INV-T01」的逐步复现（手工走一遍 A/B 两条轨迹）
- [ ] 15 个 step_id 在真实轨迹里的实际出现频率（统计 `02_`/`04_`）
- [ ] `tool_calls` 的 tool 种类清单
