from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from invoice_eval.models import Event, Run


PROTECTIVE_ERROR_CODES = frozenset(
    {
        "CONFIRMATION_REQUIRED",
        "DUPLICATE_INVOICE",
    }
)


@dataclass(frozen=True)
class ProtectiveRejection:
    event_id: str
    tool_name: str
    reason_code: str
    explanation: str


def find_protective_rejections(
    run: Run,
) -> tuple[ProtectiveRejection, ...]:
    rejections: list[ProtectiveRejection] = []
    for event in run.events:
        if event.step_id != "SUBMIT_INVOICE":
            continue
        reason_code = event.raw.get("error_code")
        if not isinstance(reason_code, str):
            continue
        for call in _tool_calls(event):
            result = _as_object(call.get("result"))
            if (
                reason_code in PROTECTIVE_ERROR_CODES
                and result is not None
                and result.get("submit_status") == "rejected"
            ):
                rejections.append(
                    ProtectiveRejection(
                        event_id=event.event_id,
                        tool_name=str(call.get("name", "unknown")),
                        reason_code=reason_code,
                        explanation=(
                            "工具根据业务前置条件拒绝了提交，"
                            "不属于接口故障。"
                        ),
                    )
                )
                break
    return tuple(rejections)


def _tool_calls(event: Event) -> list[dict[str, Any]]:
    raw_calls = event.raw.get("tool_calls")
    if not isinstance(raw_calls, list):
        return []
    return [call for call in raw_calls if isinstance(call, dict)]


def _as_object(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None
