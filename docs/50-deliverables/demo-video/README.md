# 演示视频材料包（v0.3.0）

赛题要求提交演示。本目录同时提供**两条路**：

- **A. 直接交付已生成视频**（无需录屏）：`rendered/invoice-eval-demo-v0.3.0-norecording.mp4`（3:25 / 1080p / 配音 + 字幕）
- **B. 自己录一版**（已选定 · **3:30 / 6 页 PPT 版**）：**看 `RECORDING-RUNBOOK.md`**，口播看 `narration-script-3m30-ppt.md`，跑 `prep-recording.ps1` 一键布置环境

## 一、目录内容

| 文件 | 用途 |
|---|---|
| **`RECORDING-RUNBOOK.md`** | **手动录屏作战手册（3:30 · 6 页 PPT 版）**：15 分钟准备 → 一条命令布置 → 6 段分镜操作卡（指哪里/说什么）→ 数字提示卡 → 可选 WebUI 补段 |
| **`prep-recording.ps1`** | **录屏环境一键布置**：打开 PPT/PDF/稿子 + 打印 6 段分镜卡（`-DryRun` 空跑；`-WithWebUI` 额外起可选补段服务） |
| **`rendered/invoice-eval-demo-v0.3.0-norecording.mp4`** | **已生成的成片**（1920×1080 / 30fps / H.264+AAC / 3:25 / 约 26 MB），配音 + 烧字幕——路径 A 的兜底 |
| `rendered/subtitles.srt` | 外挂字幕（Edius/剪映/上传平台可直接用） |
| `build-video.py` | **可复现构建脚本**：TTS（edge-tts）→ 静态卡缓慢推近 → 拼接 → 烧字幕；`FFMPEG`/`FFPROBE`/`BUILD_DIR` 可配 |
| `presentation.pptx` | 6 页幻灯片（16:9），可直接改 |
| `presentation.pdf` | 同上，PDF 版（备份/直投） |
| `slides/s1–s6.png` | 1920×1080 逐页图，**录屏时全屏看图切换**（避免 PPT 软件 UI 入镜） |
| 架构导图（规范资产） | `docs/assets/architecture/`：`invoice-agent-eval-architecture.png`（2800×1760）＋ HTML 源 ＋ 深色版；**PPT 第 3 页已内嵌**，不在此目录重复存图 |
| `slides/card-v08.png` · `card-four-source.png` · `card-package.png` | 补充视觉卡（V08 漂移 / 四源对照 / 提交物），已用于 TTS 成片 |
| **`narration-script-3m30-ppt.md`** | **主用口播稿（3:30 · 6 页 PPT）**：王怡然 11-11 版，已修正第 2 页一处事实错误 |
| `narration-script-4m20-webui.md` | 备用：4:20 混合版（PPT + WebUI 操作），含 9 段分镜 |
| `short-video-60s.md` | **竖屏 60 秒版**（抖音/视频号/小红书），含分镜、字幕与三种发法 |
| `start-demo.ps1` | **Windows**：一键起 WebUI 服务 + 打印分镜直达链接（录前布置用，比 prep 轻） |
| `start-demo.sh` | **Linux / macOS**：同上（bash 3.2 兼容，也适用于 Git Bash） |
| `start-demo.readme.md` | 两个脚本的用法与分镜链接表 |

### 成片与录屏版的差别（诚实说明）

| 项 | 已生成成片（A） | 自己录（B） |
|---|---|---|
| 画面 | 幻灯片 + 缓慢推近（无真人/无桌面） | 真实 WebUI 操作过程 |
| 声音 | **TTS 配音**（zh-CN-Yunxi，-4%） | 真人讲解 |
| 字幕 | 已烧入 + 外挂 SRT | 后期加 |
| 时长 | 3:25 | 4:20（脚本时长） |
| 适用 | 想省时间、直接交 | 想展示"真的能跑"、更有说服力 |

> 若时间允许，**A 交底 + B 加分**最好；只交 A 也完整（视频里所有数字都能在仓库复跑）。

## 二、录制流程（约 40 分钟出片）

1. **准备环境**（5 分钟）：1080p / 100% 缩放 / 关通知 / 干净桌面
2. **起演示环境**（按系统选一个）：
   ```powershell
   # Windows
   powershell -ExecutionPolicy Bypass -File docs\50-deliverables\demo-video\start-demo.ps1
   ```
   ```bash
   # Linux / macOS / Git Bash
   bash docs/50-deliverables/demo-video/start-demo.sh
   ```
3. **照 `narration-script.md` 逐段录**（建议分段录，每段一个文件，后期拼接）
4. **剪辑**：按时间轴对齐字幕；S8 的终端命令可现场跑（约 15–20 秒）或贴预跑画面
5. **可选**：用 `short-video-60s.md` 再发一条竖屏短视频（同一批素材，不用重录）

## 三、数字溯源（每个数字都能当场复现）

> 原则：视频里出现的数字，评审若追问必须能指向命令或文件。

| 视频说法 | 复现方式 |
|---|---|
| `128 tests + 31 subtests` | `python -m pytest -q` |
| `训练 28 run / 验证 16 run` | `python scripts/verify.py --with-rubric` |
| `INV-V07-B 首错 B-05` | `outputs/validation-v0.3.0-dev.jsonl` → INV-V07 → root_causes |
| `B-05→B-08→B-09→B-10` | 同上 `evidence_event_ids` |
| `Rubric 70 → 20` / `WRONG_INVOICE_CREATED` | `outputs/rubric-report.jsonl` → INV-V07 → run_assessments |
| `V08 预览 3710` | `docs/00-brief/data/04_无标注验证轨迹.jsonl` → INV-V08-A-07 |
| `V08 提交 3711` | 同上 → INV-V08-A-08 → `tool_calls[0].arguments.amounts.inclusive_amount` |
| `本地 V04 契约拒绝` | `outputs/four-way-report.json` → `sources.local_llm.statuses` |
| `8 Case / 16 Run` | WebUI 顶栏 / `outputs/version-report-data.json` |

## 四、注意事项

1. **合规**：手册要求「演示只应使用本资料包数据」——本演示全部使用 `docs/00-brief/data/`，合规。录制时仍请用干净桌面。
2. **不要现场跑 LLM 审计**：四源对照用预生成产物（`llm-review-*.jsonl`）展示即可；现场跑会受网络/模型稳定性影响，还可能暴露配置。
3. **版本锚点**：画面保留 WebUI 顶栏的版本与 commit；口播只说 `v0.3.0`，具体 commit 由包内 `SUBMISSION-MANIFEST.json` 承担。
4. **脚本编码坑（已修）**：`start-demo.ps1` 保持**纯 ASCII**——Windows PowerShell 5.1 按 ANSI 读 `.ps1`，脚本内的中文会破坏解析（2026-11-10 实测）。`start-demo.sh` 同样保持 ASCII，且兼容 macOS 自带 bash 3.2（无数组/无 `${var,,}`）。
5. **停止服务**：`start-demo.sh` 会把 PID 写进 `${TMPDIR:-/tmp}/invoice-eval-demo-<端口>.pid`；Git Bash 下拿到的可能是 MSYS PID，此时用 `lsof -ti:8000 | xargs kill`（macOS/Linux）或按端口停进程。

## 五、时长

- 完整版 **4:20**（S1–S9）
- 压到 **4:00**：删 S8 后半句；**不建议**删 S4/S5（证据链是核心卖点）
