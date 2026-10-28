# Git 协作规范

> 两人协作（李经霖 / 王怡然），**云端只有一个 `main`，任何人不得直接 push `main`。**

## 一、分支模型：**只有 3 个分支，长期存在**

```
origin/main          ← 唯一长期主干，保护分支，永远可运行
  ├── ljl/dev        ← 经霖的常驻开发分支（合并后不删，继续用）
  └── wyr/dev        ← 怡然的常驻开发分支（合并后不删，继续用）
```

**三条规则**：

1. **`main` 只接受 MR**，禁止直接 push
2. **每人只有一个常驻开发分支**（`ljl/dev` / `wyr/dev`），**不按任务开新分支**
3. **MR 合并后不删开发分支** —— 继续在同一条分支上下一次开发

> **为什么不用「一任务一分支」**：
> 两人小项目 + 一个多月周期，主题分支会堆成十几个，合并完还要清理，纯增管理成本。
> **常驻分支 + 每次合并前 rebase 同步 main**，就够隔离工作，且分支数恒定。

**唯一的例外**：要做一个**高风险实验**（可能推翻重来、或改动面很大）时，可以临时开 `ljl/exp-<主题>`，**实验完无论成败都删掉**。

## 二、日常流程

```bash
# 1. 切到自己的常驻分支（第一次：git switch -c ljl/dev，之后直接 switch）
git switch ljl/dev

# 2. 先同步 main 上的他人改动（每次都做，减少后面冲突）
git fetch origin
git rebase origin/main

# 3. 干活，分小步提交
git add -A
git commit -m "feat(rules): 实现金额口径校验"

# 4. 推送自己的分支
git push origin ljl/dev
#    ⚠️ rebase 过后历史变了，要用 --force-with-lease（见第五节）

# 5. 在 GitHub 上提 MR：源 ljl/dev → 目标 main
#    标题写清做什么，描述写清「怎么验证的」

# 6. MR 合并后 —— **不删分支**，回到第 1 步继续下一次
```

**关键**：第 2 步的 `rebase origin/main` **每次开工都做**。常驻分支的风险就是"攒太久没同步"，天天同步就不会有冲突。

## 三、提交信息规范

```
<type>(<scope>): <简短说明>

<可选：为什么这么做、影响什么>
```

| type | 用途 |
|---|---|
| `feat` | 新功能 |
| `fix` | 修 bug |
| `docs` | 只改文档 |
| `test` | 只改测试 |
| `refactor` | 重构（不改行为） |
| `chore` | 杂项（依赖、配置） |
| `data` | 数据结构/字段相关 |

**scope 建议**：`rules`（确定性规则）、`llm`（模型层）、`io`（读写）、`score`（评分）、`docs`。

**坏例子**（禁止）：`update`、`修改`、`改完了`、`fix bug`。

## 四、MR（Pull Request）要求

**标题**：与提交信息同规范，例：`feat(rules): 实现金额口径与税额计算校验`

**描述至少包含三段**：

```markdown
## 做了什么
- 实现了不含税/含税两种口径的换算与四舍五入
- 覆盖 AMOUNT_BASIS 与 AMOUNT_CALCULATION 两类根因

## 怎么验证
- `python -m pytest tests/test_amount.py` 全绿
- 用训练集 14 Case 跑一遍，与 `03_公开训练参考标注.jsonl` 对比：28/28 一致

## 影响面
- 只新增 rules/amount.py，未改其他模块
```

**判据**：**MR 描述里必须能看出"怎么验证的"** ——写不出来说明还没验。

## 五、冲突处理

1. **优先 rebase，不 merge**（保持线性历史）：
   ```bash
   git switch ljl/rules-engine
   git fetch origin
   git rebase origin/main
   # 解决冲突后
   git rebase --continue
   git push --force-with-lease   # 注意：--force-with-lease，不是 --force
   ```
2. **冲突解决不了就停**，在 MR 里说明卡在哪，不要硬合
3. **永远不要对 `main` 做 `force push`**

## 六、禁做清单

- ❌ 直接 push 到 `main`
- ❌ `git push --force`（对 `main` 绝对禁止）；自己做 rebase 后需强推时**只能用 `--force-with-lease`，且仅限自己的 `ljl/dev` / `wyr/dev`**
- ❌ 提交 `docs/00-brief/data/` 里官方文件的修改（那是组委会资料，**只读**）
- ❌ 提交密钥 / PAT / `.env` / 大文件（见 `.gitignore`）
- ❌ 一个 MR 混多个不相关主题
- ❌ 按任务开一堆主题分支（除非是高风险实验，见第一节例外）
- ❌ 把别人的分支强推覆盖

## 七、当前分支状态

- `main` —— 长期主干（已合并初始化文档与工程原则层）
- `ljl/dev` —— 经霖的常驻开发分支
- `wyr/dev` —— 怡然的常驻开发分支（待建）

> **建议**：在 GitHub 上给 `main` 开 branch protection（要求 MR + 至少 1 人 approve），否则本规范只是纸面约定。
