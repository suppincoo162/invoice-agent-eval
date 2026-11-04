import unittest
from pathlib import Path

from invoice_eval import (
    Event,
    Run,
    find_workflow_transition_findings,
    load_dataset,
    load_workflow,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "docs" / "00-brief" / "data"
WORKFLOW_PATH = DATA_DIR / "01_竞赛版流程字典.json"


class WorkflowTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = load_workflow(WORKFLOW_PATH)

    def test_public_trajectories_have_no_transition_findings(self) -> None:
        findings = []
        for path in (
            DATA_DIR / "02_公开训练轨迹.jsonl",
            DATA_DIR / "04_无标注验证轨迹.jsonl",
        ):
            dataset = load_dataset(path)
            for case in dataset.cases:
                for run in case.runs:
                    findings.extend(
                        find_workflow_transition_findings(
                            run, self.workflow
                        )
                    )

        self.assertEqual(findings, [])

    def test_rejects_transition_outside_whitelist(self) -> None:
        run = _run_with_steps(
            ("RECEIVE_REQUEST", "SUBMIT_INVOICE"),
        )

        findings = find_workflow_transition_findings(
            run, self.workflow
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "WORKFLOW_TRANSITION")
        self.assertEqual(
            findings[0].evidence_event_ids,
            ("SYNTHETIC-01", "SYNTHETIC-02"),
        )
        self.assertEqual(
            findings[0].first_fault_event_id,
            "SYNTHETIC-02",
        )

    def test_permits_observed_business_stop_transition(self) -> None:
        dataset = load_dataset(DATA_DIR / "02_公开训练轨迹.jsonl")
        run = dataset.get_case("INV-T05").get_run("INV-T05-A")

        self.assertEqual(
            find_workflow_transition_findings(run, self.workflow),
            (),
        )

    def test_rejects_run_that_does_not_start_at_entry(self) -> None:
        run = _run_with_steps(("SUBMIT_INVOICE",))

        findings = find_workflow_transition_findings(
            run, self.workflow
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "WORKFLOW_ENTRY")
        self.assertEqual(findings[0].from_step_id, None)
        self.assertEqual(findings[0].to_step_id, "SUBMIT_INVOICE")

    def test_rejects_trajectory_missing_required_middle_step(self) -> None:
        """轨迹缺一个必经中间步：相邻两步不在白名单内，必须报 WORKFLOW_TRANSITION。

        形态与「跨多步乱跳」不同——这是真实评测里常见的「某步未被记录 / 轨迹被截断
        一段」；判据看的是删除后相邻的 (from, to) 是否仍合法。
        """

        run = _run_with_steps(("RECEIVE_REQUEST", "RESOLVE_ENTERPRISE"))

        findings = find_workflow_transition_findings(run, self.workflow)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "WORKFLOW_TRANSITION")
        self.assertEqual(findings[0].from_step_id, "RECEIVE_REQUEST")
        self.assertEqual(findings[0].to_step_id, "RESOLVE_ENTERPRISE")

    def test_truncated_legal_prefix_has_no_findings(self) -> None:
        """合法轨迹截短（丢掉末尾事件）仍是合法前缀，不得报违规。

        负控：防止把「记录不全」误判为「流程违规」。这条曾经是真实误判点——
        删掉末事件后相邻转移依然合法时，报告为空才是正确行为。
        """

        dataset = load_dataset(DATA_DIR / "02_公开训练轨迹.jsonl")
        run = dataset.get_case("INV-T01").get_run("INV-T01-A")
        events = run.events[:-1]
        truncated = Run(
            run_id=run.run_id,
            events=events,
            event_by_id={event.event_id: event for event in events},
            raw=run.raw,
        )

        self.assertEqual(
            find_workflow_transition_findings(truncated, self.workflow),
            (),
        )

    def test_terminal_step_cannot_transition_again(self) -> None:
        run = _run_with_steps(
            (
                "RECEIVE_REQUEST",
                "CREATE_TASK",
                "RESOLVE_ENTERPRISE",
                "PARSE_INTENT",
                "COLLECT_INVOICE_DATA",
                "VALIDATE_DATA",
                "FAIL_TASK",
                "RECEIVE_REQUEST",
            ),
        )

        findings = find_workflow_transition_findings(
            run, self.workflow
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].from_step_id, "FAIL_TASK")
        self.assertEqual(findings[0].to_step_id, "RECEIVE_REQUEST")


def _run_with_steps(step_ids: tuple[str, ...]) -> Run:
    events = tuple(
        Event(
            event_id=f"SYNTHETIC-{index:02d}",
            seq=index,
            step_id=step_id,
            step_status="SUCCEEDED",
            raw={},
        )
        for index, step_id in enumerate(step_ids, start=1)
    )
    return Run(
        run_id="SYNTHETIC",
        events=events,
        event_by_id={event.event_id: event for event in events},
        raw={},
    )


if __name__ == "__main__":
    unittest.main()
