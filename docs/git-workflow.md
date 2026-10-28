# Git 协作规范

> 两人协作（李经霖 / 王怡然），**云端只有一个 `main`，任何人不得直接 push `main`。**

## 一、分支模型

```
origin/main            ← 唯一长期分支，永远可运行
  ├── ljl/<topic>      ← 经霖的开发分支（本地 → 推送）
  └── wyr/<topic>      ← 怡然的开发分支（本地 → 推送）
```

**规则**：

1. **`main` 是保护分支** —— 只接受 MR，禁止直接 push
2. **每人一个自己的开发分支**，按 `<名字缩写>/<主题>` 命名
3. **开发完推送自己的分支**到云端，然后**提 MR** 请求合并进 `main`
4. **合并后删除远端主题分支**（保持远端清爽；本地分支可留）

### 分支命名

| 前缀 | 用途 | 例 |
|---|---|---|
| `ljl/` `wyr/` | 个人主题分支 | `ljl/rules-engine` |
| `feat/` | 两人共同的较大功能 | `feat/llm-layer` |
| `fix/` | 修 bug | `fix/amount-rounding` |

**禁止**：`test`、`tmp`、`dev`、`master`、`main` 这类无信息名字。

## 二、日常流程

```bash
# 1. 开工前先同步 main
git switch main
git pull --rebase origin main

# 2. 建自己的分支（从最新 main）
git switch -c ljl/rules-engine

# 3. 干活，分小步提交
git add -A
git commit -m "feat(rules): 实现金额口径校验"

# 4. 推送自己的分支
git push -u origin ljl/rules-engine

# 5. 在 GitHub 上提 MR → 目标 main
#    标题写清做什么，描述写清怎么验证

# 6. 合并后清理
git switch main && git pull --rebase origin main
git branch -d ljl/rules-engine            # 删本地
git push origin --delete ljl/rules-engine # 删远端（若 GitHub 没自动删）
```

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
- ❌ `git push --force`（对共享分支）；只能用 `--force-with-lease` 且仅限自己的分支
- ❌ 提交 `data/` 里官方文件的修改（那是组委会资料，**只读**）
- ❌ 提交密钥 / PAT / `.env` / 大文件（见 `.gitignore`）
- ❌ 一个 MR 混多个不相关主题
- ❌ 把别人的分支强推覆盖

## 七、当前状态

- `main` 现有 1 个提交：`f3e891a chore: 初始化仓库与赛题资料`
- 尚无分支保护规则 —— **建议在 GitHub 上给 `main` 开 branch protection**（要求 MR + 至少 1 人 approve），见下方待办
