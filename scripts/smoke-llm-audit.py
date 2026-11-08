# -*- coding: utf-8 -*-
"""LLM 盲审链路契约冒烟（无需模型、无需 API Key）。

为什么需要它（2026-11-08 加）：
    竞赛评分定位里「Qwen-compatible 冒烟」是一项明确缺口。但在没有评测方模型、
    也没有任何 API Key 的机器上，真实模型冒烟跑不了；而**链路本身**（发请求 →
    收 OpenAI-compatible 响应 → 程序校验 → 落盘 llm-review.jsonl）是可以被证明的。

    本脚本起一个本地桩服务（`/v1/chat/completions`），按真实契约返回一份合法盲审
    结果，然后走真实 CLI 跑一遍 `audit`，断言：
      1. CLI exit 0（不报错）；
      2. 输出文件存在且为合法 JSONL；
      3. 请求里带 `model` 与 `temperature=0`（可复现控制）；
      4. 服务端收到的 Authorization 头为空（未配置 key 时不得伪造）。

    它证明「链路通、契约对、校验生效」；**不证明**任何模型的质量——后者需要真端点。

用法：
    python scripts/smoke-llm-audit.py
    python scripts/smoke-llm-audit.py --case-id INV-V03

边界：
    - 桩返回的结论是脚本构造的，不代表任何模型判断；
    - 真实 Qwen-compatible 冒烟仍需：本地 Ollama 拉 chat 模型，或评测方/自备 API。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

DATA_DIR = PROJECT_ROOT / "docs" / "00-brief" / "data"
VALID_CASES = DATA_DIR / "04_无标注验证轨迹.jsonl"
WORKFLOW = DATA_DIR / "01_竞赛版流程字典.json"
RULES = PROJECT_ROOT / "docs" / "00-brief" / "rules.md"


class _Capture:
    """记录桩服务收到的请求，供事后断言。"""

    def __init__(self) -> None:
        self.bodies: list[dict] = []
        self.auth_headers: list[str] = []
        self.paths: list[str] = []


def _build_review(case_id: str, body_text: str, invalid: bool = False) -> dict:
    """按契约构造一份合法盲审结果。

    证据事件从请求正文里提取（请求里本就带 case 轨迹），
    因此不需要另猜 event_id 格式。
    """
    events = sorted(set(re.findall(rf"{re.escape(case_id)}-[AB]-\d+", body_text)))
    a_events = [e for e in events if f"{case_id}-A-" in e]
    b_events = [e for e in events if f"{case_id}-B-" in e]
    if not a_events or not b_events:
        raise RuntimeError("请求正文里没找到 A/B 事件 id，无法构造桩响应")

    if invalid:
        # 负控：成功 run 却带根因（契约明令禁止）⇒ 客户端必须拒绝。
        return {
            "case_id": case_id,
            "run_assessments": [
                {
                    "run_id": f"{case_id}-A",
                    "agent_task_success": True,
                    "business_invoice_created": False,
                    "root_causes": [
                        {
                            "label": "FIELD_FABRICATION",
                            "first_fault_event_id": a_events[0],
                            "evidence_event_ids": [a_events[0]],
                            "explanation": "负控：成功 run 不应有根因。",
                        }
                    ],
                    "evidence_event_ids": [a_events[0]],
                    "explanation": "负控。",
                    "unknowns": [],
                },
                {
                    "run_id": f"{case_id}-B",
                    "agent_task_success": False,
                    "business_invoice_created": False,
                    "root_causes": [
                        {
                            "label": "FIELD_FABRICATION",
                            "first_fault_event_id": b_events[0],
                            "evidence_event_ids": [b_events[0]],
                            "explanation": "负控。",
                        }
                    ],
                    "evidence_event_ids": [b_events[0]],
                    "explanation": "负控。",
                    "unknowns": [],
                },
            ],
            "version_comparison": {
                "direction": "baseline_better",
                "reason": "负控。",
            },
        }

    # 依据 run 的 invoice_created 事实填写（B 侧按失败构造一个根因）。
    return {
        "case_id": case_id,
        "run_assessments": [
            {
                "run_id": f"{case_id}-A",
                "agent_task_success": True,
                "business_invoice_created": False,
                "root_causes": [],
                "evidence_event_ids": [a_events[0], a_events[-1]],
                "explanation": "桩响应：A 侧未发现阻断性违规。",
                "unknowns": [],
            },
            {
                "run_id": f"{case_id}-B",
                "agent_task_success": False,
                "business_invoice_created": False,
                "root_causes": [
                    {
                        "label": "FIELD_FABRICATION",
                        "first_fault_event_id": b_events[0],
                        "evidence_event_ids": [b_events[0]],
                        "explanation": "桩响应：B 侧首个事件即出现字段编造。",
                        "confidence": 0.9,
                    }
                ],
                "evidence_event_ids": [b_events[0]],
                "explanation": "桩响应：B 侧存在根因。",
                "unknowns": ["桩响应：不确定点占位。"],
            },
        ],
        "version_comparison": {
            "direction": "baseline_better",
            "reason": "桩响应：A 侧成功、B 侧存在字段编造，故本 Case 基线下更优（不外推）。",
        },
    }


def _make_handler(capture: _Capture, case_id: str, model_id: str, invalid: bool = False):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # 静默
            return

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body_text = self.rfile.read(length).decode("utf-8", errors="replace")
            capture.paths.append(self.path)
            capture.auth_headers.append(self.headers.get("Authorization") or "")

            try:
                body = json.loads(body_text)
            except json.JSONDecodeError:
                body = {}
            capture.bodies.append(body)

            review = _build_review(case_id, body_text, invalid=invalid)
            response = {
                "id": "stub-1",
                "object": "chat.completion",
                "model": body.get("model") or model_id,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(review, ensure_ascii=False),
                        },
                        "finish_reason": "stop",
                    }
                ],
            }
            payload = json.dumps(response, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LLM 盲审链路契约冒烟（无模型）")
    parser.add_argument("--case-id", default="INV-V03")
    parser.add_argument("--model", default="stub-qwen-compatible")
    parser.add_argument(
        "--negative",
        action="store_true",
        help="负控：桩返回非法响应，断言客户端拒绝（exit≠0 且不产文件）",
    )
    args = parser.parse_args(argv)

    capture = _Capture()
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        _make_handler(capture, args.case_id, args.model, invalid=args.negative),
    )
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    failures: list[str] = []
    try:
        with tempfile.TemporaryDirectory(prefix="smoke-llm-") as tmp:
            out = Path(tmp) / "llm-review.jsonl"
            env = dict(os.environ)
            env.update(
                {
                    "INVOICE_EVAL_LLM_MODEL": args.model,
                    "INVOICE_EVAL_LLM_BASE_URL": f"http://127.0.0.1:{port}/v1",
                    "INVOICE_EVAL_LLM_API_KEY": "",
                    "INVOICE_EVAL_LLM_TIMEOUT": "30",
                }
            )
            proc = subprocess.run(
                [
                    sys.executable, "-m", "invoice_eval", "audit",
                    "--cases", str(VALID_CASES),
                    "--output", str(out),
                    "--workflow", str(WORKFLOW),
                    "--rules", str(RULES),
                    "--case-id", args.case_id,
                    "--timeout", "30",
                ],
                cwd=str(PROJECT_ROOT),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            print("=" * 70)
            print("LLM 盲审链路契约冒烟（本地桩 · 无模型 · 无 API Key）")
            print("=" * 70)
            print(f"  桩地址      : http://127.0.0.1:{port}/v1/chat/completions")
            print(f"  Case        : {args.case_id}")
            print(f"  CLI exit    : {proc.returncode}")
            if proc.returncode != 0:
                failures.append(f"CLI exit {proc.returncode}: {proc.stdout.strip()[-300:]}")
                print(f"  stderr      : {proc.stderr.strip()[-300:]}")
            else:
                print("  ✅ CLI 正常退出")

            # 断言 1：输出文件
            if not out.exists():
                failures.append("未生成 llm-review.jsonl")
            else:
                lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]
                ok_shape = len(lines) == 1
                try:
                    review = json.loads(lines[0]) if lines else {}
                except json.JSONDecodeError:
                    review = {}
                ok_case = review.get("case_id") == args.case_id
                ok_runs = len(review.get("run_assessments") or []) == 2
                print(f"  输出行数    : {len(lines)}（应 1）")
                print(f"  case_id     : {review.get('case_id')}（应 {args.case_id}）")
                print(f"  run 数      : {len(review.get('run_assessments') or [])}（应 2）")
                if not (ok_shape and ok_case and ok_runs):
                    failures.append("输出结构不符合契约")
                else:
                    print("  ✅ 契约校验通过（clients 侧 validate_review 未拒绝）")

            # 断言 2：请求可复现控制
            if not capture.bodies:
                failures.append("桩服务没收到请求")
            else:
                body = capture.bodies[0]
                temp = body.get("temperature")
                has_model = bool(body.get("model"))
                print(f"  请求 model  : {body.get('model')}")
                print(f"  temperature : {temp}（应为 0）")
                if temp != 0:
                    failures.append(f"temperature 不是 0（{temp}）")
                if not has_model:
                    failures.append("请求未带 model")
                if not capture.paths[0].endswith("/chat/completions"):
                    failures.append(f"请求路径异常：{capture.paths[0]}")
                print(f"  请求路径    : {capture.paths[0]}")

            # 断言 3：未配置 key 时不得伪造 Authorization
            auth = capture.auth_headers[0] if capture.auth_headers else ""
            print(f"  Authorization: {'（空）' if not auth else '⚠️ 非空'}")
            if auth:
                failures.append("未配置 API Key 却发送了 Authorization 头")

    finally:
        server.shutdown()
        server.server_close()

    print("-" * 70)
    if args.negative:
        # 负控期望：CLI 非 0 且不产文件
        ok = (proc.returncode != 0) and (not out.exists())
        print(f"  负控结论：{'✅ 客户端拒绝了非法响应' if ok else '❌ 非法响应被放过（假绿）'}")
        if not ok:
            print(f"    CLI exit={proc.returncode}，产物存在={out.exists()}")
        print("  说明：以上「失败」清单（若有）为正控投影，负控下不计。")
        return 0 if ok else 1
    if failures:
        print("  结论：❌ 冒烟失败")
        for f in failures:
            print(f"    - {f}")
        return 1
    print("  结论：✅ 通过（链路通 / 契约对 / 校验生效 / 未伪造密钥）")
    print("  边界：桩响应由脚本构造，不代表任何模型质量；真实模型冒烟另行执行。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
