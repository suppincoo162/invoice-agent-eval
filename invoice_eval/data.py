from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from invoice_eval.models import Case, Dataset, Event, Run


class DatasetFormatError(ValueError):
    """Raised when a JSONL dataset does not satisfy the evaluator contract."""


def load_dataset(path: str | Path) -> Dataset:
    dataset_path = Path(path)
    cases: list[Case] = []
    case_by_id: dict[str, Case] = {}

    with dataset_path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue

            location = f"{dataset_path}:{line_number}"
            try:
                raw_case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DatasetFormatError(
                    f"{location}: invalid JSON: {exc.msg} at column {exc.colno}"
                ) from exc

            case = _parse_case(raw_case, location)
            if case.case_id in case_by_id:
                raise DatasetFormatError(
                    f"{location}: duplicate case_id {case.case_id!r}"
                )

            cases.append(case)
            case_by_id[case.case_id] = case

    return Dataset(
        cases=tuple(cases),
        case_by_id=case_by_id,
        source_path=dataset_path,
    )


def _parse_case(raw_case: Any, location: str) -> Case:
    if not isinstance(raw_case, dict):
        raise DatasetFormatError(f"{location}: Case must be a JSON object")

    case_id = _required_text(raw_case, "case_id", location)
    raw_runs = _required_list(raw_case, "runs", location)
    if len(raw_runs) != 2:
        raise DatasetFormatError(
            f"{location}: case {case_id!r} must contain exactly 2 runs, "
            f"found {len(raw_runs)}"
        )

    runs: list[Run] = []
    run_by_id: dict[str, Run] = {}
    for run_index, raw_run in enumerate(raw_runs):
        run_location = f"{location} case {case_id!r} run[{run_index}]"
        run = _parse_run(raw_run, run_location)
        if run.run_id in run_by_id:
            raise DatasetFormatError(
                f"{run_location}: duplicate run_id {run.run_id!r}"
            )
        runs.append(run)
        run_by_id[run.run_id] = run

    return Case(
        case_id=case_id,
        runs=tuple(runs),
        run_by_id=run_by_id,
        raw=raw_case,
    )


def _parse_run(raw_run: Any, location: str) -> Run:
    if not isinstance(raw_run, dict):
        raise DatasetFormatError(f"{location}: Run must be a JSON object")

    run_id = _required_text(raw_run, "run_id", location)
    raw_events = _required_list(raw_run, "events", location)
    if not raw_events:
        raise DatasetFormatError(f"{location}: run {run_id!r} must contain events")

    events: list[Event] = []
    event_by_id: dict[str, Event] = {}
    seen_sequences: set[int] = set()
    for event_index, raw_event in enumerate(raw_events):
        event_location = f"{location} event[{event_index}]"
        event = _parse_event(raw_event, event_location)
        if event.event_id in event_by_id:
            raise DatasetFormatError(
                f"{event_location}: duplicate event_id {event.event_id!r}"
            )
        if event.seq in seen_sequences:
            raise DatasetFormatError(
                f"{event_location}: duplicate seq {event.seq} in run {run_id!r}"
            )
        events.append(event)
        event_by_id[event.event_id] = event
        seen_sequences.add(event.seq)

    events.sort(key=lambda event: event.seq)
    return Run(
        run_id=run_id,
        events=tuple(events),
        event_by_id=event_by_id,
        raw=raw_run,
    )


def _parse_event(raw_event: Any, location: str) -> Event:
    if not isinstance(raw_event, dict):
        raise DatasetFormatError(f"{location}: Event must be a JSON object")

    event_id = _required_text(raw_event, "event_id", location)
    step_id = _required_text(raw_event, "step_id", location)
    step_status = _required_text(raw_event, "step_status", location)
    seq = raw_event.get("seq")
    if isinstance(seq, bool) or not isinstance(seq, int):
        raise DatasetFormatError(
            f"{location}: event {event_id!r} field 'seq' must be an integer"
        )

    return Event(
        event_id=event_id,
        seq=seq,
        step_id=step_id,
        step_status=step_status,
        raw=raw_event,
    )


def _required_text(raw: dict[str, Any], field: str, location: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value:
        raise DatasetFormatError(
            f"{location}: field {field!r} must be a non-empty string"
        )
    return value


def _required_list(
    raw: dict[str, Any], field: str, location: str
) -> list[Any]:
    value = raw.get(field)
    if not isinstance(value, list):
        raise DatasetFormatError(f"{location}: field {field!r} must be a list")
    return value
