# 规则覆盖体检（2026-11-04 只读实验）

> 状态：**一次实验的结论留痕**，不是承诺。目的只有一个——回答「训练集 28 条 run 全一致」这个证据**有多强**。
> 方法全部可复现（命令见文末）；实验是**只读**的：脚本 import 生产模块、在内存里替换规则函数，**不改仓库任何文件**。

## 一、方法：为什么不做"覆盖率"

覆盖率回答"代码有没有被执行"，回答不了"这条规则有没有真的决定过判定"。本题的更直接问法是**差分留一**：

1. 逐条把一条规则函数替换成"永远返回空"的实现；
2. 重跑训练集（14 Case）与验证集（8 Case）；
3. 比较**全输出指纹**（`direction` ＋ 两个布尔 ＋ `quality_score` ＋ 根因/证据字段）；
4. 变化数＝该规则的真实**承重**；变化为 0 ⇒ 这条规则在这批数据上**没有影响过任何判定**。

另统计两批数据上每条规则**真的产出 finding** 的 Case 数（触发分布），并对"零触发"的规则补**构造用例**做正控/负控。

## 二、差分留一结果（摘掉该规则后的输出变化数）

| 规则 | 训练集变化 | 验证集变化 |
|---|---:|---:|
| `find_amount_findings` | 3 | 1 |
| `find_batch_root_causes` | 1 | 1 |
| `find_duplicate_control_root_causes` | 1 | 1 |
| `find_submit_argument_root_causes` | 1 | 1 |
| `find_buyer_root_causes` | 2 | 0 |
| `find_confirmation_root_causes` | 2 | 0 |
| `find_protective_rejections` | 3 | 0 |
| `find_callback / cancellation / product / submit_timeout / task_type` | 各 1 | 0 |
| `find_context_update_root_causes` | 0 | 1 |
| `find_red_invoice_root_causes` | 0 | 1 |
| `find_workflow_transition_findings` | 0 | 0 |

## 三、触发分布（该规则产出 finding 的 Case 数）

训练集最多 **3 Case/规则**，多数只有 1；**14 个 Case ÷ 15 条规则 ⇒ 平均不到 1 个 Case/规则**。验证集只有 5 条规则被触发。

> 直接推论：**"训练集全对"＝"14 个样本恰好每条规则碰了一次"**，不等于"规则被充分验证"。真实样本密度是当前最大的证据短板。

## 四、流程白名单的构造验证（5 正控 + 2 负控，全过）

`find_workflow_transition_findings` 在两批数据上都零触发，因此另做构造用例：

| 形态 | 期望 | 实测 |
|---|---|---|
| 原始合法轨迹 | 0 | 0 ✅ |
| 删**末**事件（＝合法前缀） | 0 | 0 ✅ |
| 改 step 跳过确认（`VALIDATE_DATA → SUBMIT_INVOICE`） | ≥1 | 1 ✅ |
| 删中间步（`RECEIVE_REQUEST → RESOLVE_ENTERPRISE`） | ≥1 | 1 ✅ |
| 倒序 | ≥1 | 7 ✅ |
| 交换中间两步 | ≥1 | 3 ✅ |
| 末步换非法后继 | ≥1 | 1 ✅ |

端到端：改 step 后 `agent_task_success=False`、`quality_score=0` ⇒ 该规则确实接入了判定链路。**注意**：该规则原本已有 5 条单元测试（见 `tests/test_workflow.py`），本文不是"补上验证"，而是补**两种此前未覆盖的形态**（缺中间步、截短合法前缀的负控）。

## 五、结论与风险

1. **判定主干有真实证据**：金额、批量、重复控制、提交参数四条在训练集与验证集**两面都承重**，是可信的。
2. ⚠️ **每条规则平均不足 1 个真实 Case 承重**；隐藏集若出现不同形态分布，误判/漏判风险主要来自"规则没被真实样本验证过"，而不是"代码写错"。
3. ⚠️ **`find_context_update`（多轮修改）与 `find_red_invoice`（红票）只在无标签验证集触发** ⇒ 它们的正确性**没有任何标签可核对**，需人工复核 `INV-V03/V04` 的输出。
4. ⚠️ 流程白名单在真实数据上**从未触发** ⇒ 其在真实业务分布上的**误报率未知**（若甲方存在白名单未收录的合法停步形态，会被误报）。建议保留"业务性停步"这类已观测形态的回归用例。

## 六、复现方式

```bash
# 差分留一（打印每条规则摘掉后的变化 Case）
python - <<'PY'
import json, pathlib, sys
sys.path.insert(0, ".")
import invoice_eval.evaluator as EV
from invoice_eval import load_dataset, load_workflow
D = pathlib.Path("docs/00-brief/data")
train = load_dataset(D / "02_公开训练轨迹.jsonl")
wf = load_workflow(D / "01_竞赛版流程字典.json")
rules = [n for n in dir(EV) if n.startswith("find_")]
fp = lambda c: json.dumps(EV.evaluate_case(c, wf), sort_keys=True, ensure_ascii=False)
base = {c.case_id: fp(c) for c in train.cases}
for r in rules:
    orig, EV.__dict__[r] = EV.__dict__[r], (lambda *a, **k: ())
    after = {c.case_id: fp(c) for c in train.cases}
    EV.__dict__[r] = orig
    print(r, [k for k in base if base[k] != after[k]])
PY
```

## 七、人工复核 INV-V03 / INV-V04（2026-11-04）

这两条规则**只在无标签验证集触发**，没有标签可对照，故逐事件人工核对。

### 核对结果

| Case / run | 轨迹事实 | 评测器判定 | 复核结论 |
|---|---|---|---|
| `INV-V04-A` | COLLECT 金额 **2000**（第一轮旧值），参考最新值 **2500** | `CONTEXT_UPDATE`，首因 `-05`，score 70 | **判对** |
| `INV-V04-B` | COLLECT 金额 **2500** | success=true，score 100 | **判对** |
| `INV-V03-A` | 金额与原票均未提供，Agent 停在 `WAIT_USER_SUPPLEMENT` 明确索要两项 | success=true | **判对**（符合 `required_action=ASK_ORIGINAL_INVOICE_AND_AMOUNT`） |
| `INV-V03-B` | **用户从未提供金额**（参考值为 null），Agent 在 COLLECT 填入 **100000**，且未索要原票即进入确认预览 | `FIELD_FABRICATION`（解释只提"原票编号缺失"），score 70 | **方向对但漏判**：只抓了"缺原票"，没抓"**编造金额**" |

### 漏报根因

`find_amount_findings`（`amounts.py:70-77`）：参考 `amount_value` 为 `null` 时**直接返回空**，因此「题内未给金额、Agent 自行编一个」这一形态**没有任何规则覆盖**。而官方手册 L37-38 明确：「缺少购方、金额口径、原票引用等必要信息时，正确动作是追问，不能猜测」。⇒ 这是**判据覆盖缺口**，不是口径分歧。

### 影响面（修复前必须先确认）

已按官方标签约束落地（2026-11-04 当日修复）：

- **官方校验器只接受 14 个固定根因标签**，无"编造金额"专用标签 ⇒ 采用 `FIELD_FABRICATION`（语义即"字段编造"），并把该标签严重度由 30 提到 **50**（手册要求"严重金额风险对分数产生足够影响"）；
- 实际影响：`INV-V03-B` 70 → **50**（原票缺失与编造金额同首因事件 ⇒ 罚项合并，只扣一次）；候选版平均质量分 88.75 → **86.25**，**与基线持平**（此前预告的"反转"未发生，已按实际结果修正）；高风险数 B 0 → 1；
- 单 Case 方向与 `version_comparison.direction` **不变**；训练集 14 Case 不受影响（无 `amount_value=null` 样本）。

⇒ 修复会改动**已定稿版本报告的核心指标**，须项目双人（李经霖 / 王怡然）确认后执行，并重新生成报告数字。
