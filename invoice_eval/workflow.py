from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from invoice_eval.models import Run


class WorkflowFormatError(ValueError):
    """Raised when the workflow dictionary is malformed."""


# The supplied dictionary is explicitly an external simplification. The public
# trajectories and expert labels show this business-stop transition in
# INV-T05-A (correct) and INV-V02-B, so treating it as unknown would be a false
# positive. Keep the exception explicit and evidence-backed.
OBSERVED_BUSINESS_STOP_TRANSITIONS = frozenset(
    {
        ("VALIDATE_DATA", "FAIL_TASK"),
    }
)


@dataclass(frozen=True)
class WorkflowStep:
    order: int
    step_id: str
    name: str
    stage: str
    required_by_default: bool
    possible_next_steps: tuple[str, ...]
    raw: dict[str, Any]


@dataclass(frozen=True)
class Workflow:
    workflow_id: str
    steps: tuple[WorkflowStep, ...]
    step_by_id: dict[str, WorkflowStep]
    entry_step_ids: tuple[str, ...]
    terminal_step_ids: tuple[str, ...]
    raw: dict[str, Any]

    def can_transition(self, current_step_id: str, next_step_id: str) -> bool:
        current = self.step_by_id.get(current_step_id)
        if current is None:
            return False
        return (
            next_step_id in current.possible_next_steps
            or (current_step_id, next_step_id)
            in OBSERVED_BUSINESS_STOP_TRANSITIONS
        )


@dataclass(frozen=True)
class WorkflowFinding:
    rule_id: str
    actor: str
    first_fault_event_id: str
    evidence_event_ids: tuple[str, ...]
    from_step_id: str | None
    to_step_id: str
    message: str


def load_workflow(path: str | Path) -> Workflow:
    workflow_path = Path(path)
    try:
        raw = json.loads(workflow_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowFormatError(
            f"{workflow_path}: invalid JSON: {exc.msg} at column {exc.colno}"
        ) from exc

    if not isinstance(raw, dict):
        raise WorkflowFormatError(f"{workflow_path}: workflow must be an object")

    workflow_id = _required_text(raw, "workflow_id", str(workflow_path))
    raw_steps = raw.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise WorkflowFormatError(
            f"{workflow_path}: field 'steps' must be a non-empty list"
        )

    steps: list[WorkflowStep] = []
    step_by_id: dict[str, WorkflowStep] = {}
    for index, raw_step in enumerate(raw_steps):
        location = f"{workflow_path}: steps[{index}]"
        step = _parse_step(raw_step, location)
        if step.step_id in step_by_id:
            raise WorkflowFormatError(
                f"{location}: duplicate step_id {step.step_id!r}"
            )
        steps.append(step)
        step_by_id[step.step_id] = step

    for step in steps:
        unknown_targets = set(step.possible_next_steps) - set(step_by_id)
        if unknown_targets:
            raise WorkflowFormatError(
                f"{workflow_path}: step {step.step_id!r} points to unknown "
                f"steps {sorted(unknown_targets)!r}"
            )

    incoming_steps = {
        next_step_id
        for step in steps
        for next_step_id in step.possible_next_steps
    }
    entry_steps = tuple(
        step.step_id for step in steps if step.step_id not in incoming_steps
    )
    if len(entry_steps) != 1:
        raise WorkflowFormatError(
            f"{workflow_path}: expected exactly one entry step, "
            f"found {entry_steps!r}"
        )

    terminal_steps = tuple(
        step.step_id for step in steps if not step.possible_next_steps
    )
    return Workflow(
        workflow_id=workflow_id,
        steps=tuple(sorted(steps, key=lambda step: step.order)),
        step_by_id=step_by_id,
        entry_step_ids=entry_steps,
        terminal_step_ids=terminal_steps,
        raw=raw,
    )


def find_workflow_transition_findings(
    run: Run, workflow: Workflow
) -> tuple[WorkflowFinding, ...]:
    if not run.events:
        return ()

    findings: list[WorkflowFinding] = []
    first_event = run.events[0]
    if first_event.step_id not in workflow.entry_step_ids:
        findings.append(
            WorkflowFinding(
                rule_id="WORKFLOW_ENTRY",
                actor="AGENT",
                first_fault_event_id=first_event.event_id,
                evidence_event_ids=(first_event.event_id,),
                from_step_id=None,
                to_step_id=first_event.step_id,
                message=(
                    f"Workflow must start with one of "
                    f"{workflow.entry_step_ids!r}, found {first_event.step_id!r}"
                ),
            )
        )

    for previous, current in zip(run.events, run.events[1:]):
        if workflow.can_transition(previous.step_id, current.step_id):
            continue
        findings.append(
            WorkflowFinding(
                rule_id="WORKFLOW_TRANSITION",
                actor="AGENT",
                first_fault_event_id=current.event_id,
                evidence_event_ids=(previous.event_id, current.event_id),
                from_step_id=previous.step_id,
                to_step_id=current.step_id,
                message=(
                    f"Illegal workflow transition: "
                    f"{previous.step_id} -> {current.step_id}"
                ),
            )
        )
    return tuple(findings)


def _parse_step(raw_step: Any, location: str) -> WorkflowStep:
    if not isinstance(raw_step, dict):
        raise WorkflowFormatError(f"{location}: step must be an object")

    order = raw_step.get("order")
    if isinstance(order, bool) or not isinstance(order, int):
        raise WorkflowFormatError(f"{location}: field 'order' must be an integer")

    step_id = _required_text(raw_step, "step_id", location)
    name = _required_text(raw_step, "name", location)
    stage = _required_text(raw_step, "stage", location)
    required_by_default = raw_step.get("required_by_default")
    if not isinstance(required_by_default, bool):
        raise WorkflowFormatError(
            f"{location}: field 'required_by_default' must be a boolean"
        )

    raw_next_steps = raw_step.get("possible_next_steps")
    if not isinstance(raw_next_steps, list):
        raise WorkflowFormatError(
            f"{location}: field 'possible_next_steps' must be a list"
        )
    next_steps = tuple(
        _non_empty_string(value, "possible_next_steps", location)
        for value in raw_next_steps
    )
    if len(set(next_steps)) != len(next_steps):
        raise WorkflowFormatError(
            f"{location}: field 'possible_next_steps' contains duplicates"
        )

    return WorkflowStep(
        order=order,
        step_id=step_id,
        name=name,
        stage=stage,
        required_by_default=required_by_default,
        possible_next_steps=next_steps,
        raw=raw_step,
    )


def _required_text(raw: dict[str, Any], field: str, location: str) -> str:
    return _non_empty_string(raw.get(field), field, location)


def _non_empty_string(value: Any, field: str, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise WorkflowFormatError(
            f"{location}: field {field!r} must be a non-empty string"
        )
    return value
