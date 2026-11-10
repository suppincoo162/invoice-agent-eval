# 演示视频 · 一键演示环境

启动 WebUI 静态服务，并打印每个分镜的**直达链接**（录屏时直接粘贴到地址栏即可）。
**Windows 用 `.ps1`，Linux / macOS（以及 Git Bash）用 `.sh`，两者行为一致。**

## 用法（Windows）

```powershell
powershell -ExecutionPolicy Bypass -File docs\50-deliverables\demo-video\start-demo.ps1

# 不打开浏览器（只起服务 + 打印链接）：
... start-demo.ps1 -NoBrowser

# 换端口（默认 8000）：
... start-demo.ps1 -Port 8080
```

## 用法（Linux / macOS / Git Bash）

```bash
bash docs/50-deliverables/demo-video/start-demo.sh

# 不打开浏览器：
bash .../start-demo.sh --no-browser

# 换端口：
PORT=8080 bash .../start-demo.sh
```

## 停止服务

```powershell
# Windows（PowerShell）
Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

```bash
# macOS / Linux
lsof -ti:8000 | xargs kill
# 或者用脚本写下的 pidfile：
kill "$(cat "${TMPDIR:-/tmp}/invoice-eval-demo-8000.pid")"
```

> ⚠️ Git Bash 下 pidfile 里是 **MSYS PID**，可能对不上 Windows 进程号——那种情况按端口停。

## 分镜直达链接（脚本会打印同样的清单）

| 分镜 | 链接 |
|---|---|
| S4 · INV-V07 摘要 | `http://127.0.0.1:8000/index.html#case=INV-V07&tab=summary` |
| S4 · INV-V07 时间线 | `http://127.0.0.1:8000/index.html#case=INV-V07&tab=timeline` |
| S5 · INV-V08 摘要 | `http://127.0.0.1:8000/index.html#case=INV-V08&tab=summary` |
| S5 · INV-V08 时间线 | `http://127.0.0.1:8000/index.html#case=INV-V08&tab=timeline` |
| S6 · INV-V04 四方对照 | `http://127.0.0.1:8000/index.html#case=INV-V04&tab=sources` |
| 附录 | `http://127.0.0.1:8000/appendices/`（报告/JSONL 原件） |

> 页面顶栏显示 `v0.3.0-dev`、`8 Cases / 16 Runs`、`建议 investigate` 与生成时的 commit——
> 这就是"版本锚点"，录屏时让它始终在画面里。

## 安全/合规

- WebUI **完全离线**，不联网、不调模型、不读密钥；
- 数据全部来自赛题资料包（`docs/00-brief/data/`），符合手册「演示只应使用本资料包数据」；
- 录制时仍建议关通知 / 用干净桌面，避免无关窗口入镜。
