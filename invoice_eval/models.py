from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Event:
    event_id: str
    seq: int
    step_id: str
    step_status: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class Run:
    run_id: str
    events: tuple[Event, ...]
    event_by_id: dict[str, Event]
    raw: dict[str, Any]

    def get_event(self, event_id: str) -> Event:
        return self.event_by_id[event_id]


@dataclass(frozen=True)
class Case:
    case_id: str
    runs: tuple[Run, ...]
    run_by_id: dict[str, Run]
    raw: dict[str, Any]

    def get_run(self, run_id: str) -> Run:
        return self.run_by_id[run_id]


@dataclass(frozen=True)
class Dataset:
    cases: tuple[Case, ...]
    case_by_id: dict[str, Case]
    source_path: Path

    def get_case(self, case_id: str) -> Case:
        return self.case_by_id[case_id]


@dataclass(frozen=True)
class RootCause:
    label: str
    first_fault_event_id: str | None
    evidence_event_ids: tuple[str, ...]
    explanation: str
    actor: str = "AGENT"
    source: str = "deterministic"


@dataclass(frozen=True)
class PenaltyItem:
    dimension: str
    points_deducted: int
    evidence_event_ids: tuple[str, ...]
    explanation: str
