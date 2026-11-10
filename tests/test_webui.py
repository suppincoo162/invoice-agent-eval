import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from invoice_eval import load_dataset
from invoice_eval.cli import main
from invoice_eval.rubric import load_rubric_report
from invoice_eval.version_report import load_jsonl_cases
from invoice_eval.webui import build_webui_data, write_webui
from invoice_eval.webui import APPENDIX_FILES


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = (
    PROJECT_ROOT / "docs" / "00-brief" / "data"
    / "04_无标注验证轨迹.jsonl"
)
SUBMISSION_PATH = (
    PROJECT_ROOT / "outputs" / "validation-v0.3.0.jsonl"
)
FOUR_WAY_PATH = PROJECT_ROOT / "outputs" / "four-way-report.json"
RUBRIC_PATH = PROJECT_ROOT / "outputs" / "rubric-report.jsonl"
ANALYSIS_PATH = (
    PROJECT_ROOT / "outputs" / "four-way-llm-analysis.json"
)


class WebUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = load_dataset(CASES_PATH)
        cls.submission = load_jsonl_cases(SUBMISSION_PATH)
        cls.four_way = json.loads(FOUR_WAY_PATH.read_text(encoding="utf-8"))
        cls.rubric = load_rubric_report(RUBRIC_PATH)
        cls.analysis = json.loads(
            ANALYSIS_PATH.read_text(encoding="utf-8")
        )
        cls.data = build_webui_data(
            dataset=cls.dataset,
            submission=cls.submission,
            four_way_report=cls.four_way,
            rubric_report=cls.rubric,
            llm_analysis=cls.analysis,
            submission_path=SUBMISSION_PATH,
        )

    def test_builds_complete_case_and_run_index(self) -> None:
        self.assertEqual(self.data["metadata"]["case_count"], 8)
        self.assertEqual(self.data["metadata"]["run_count"], 16)
        self.assertEqual(
            self.data["source_coverage"]["local_llm"]["present_count"],
            7,
        )
        self.assertEqual(
            self.data["source_coverage"]["local_llm"]["missing_cases"],
            ["INV-V04"],
        )
        self.assertEqual(
            len({case["case_id"] for case in self.data["cases"]}),
            8,
        )
        for case in self.data["cases"]:
            self.assertEqual(
                [run["run_id"] for run in case["runs"]],
                [
                    run.run_id
                    for run in self.dataset.get_case(case["case_id"]).runs
                ],
            )

    def test_rubric_caps_and_evidence_are_preserved(self) -> None:
        v07 = next(
            case
            for case in self.data["cases"]
            if case["case_id"] == "INV-V07"
        )
        v07_b = next(
            run for run in v07["runs"] if run["run_id"] == "INV-V07-B"
        )
        self.assertEqual(v07_b["assessment"]["quality_score"], 70)
        self.assertEqual(v07_b["rubric"]["rubric_score"], 20)
        self.assertEqual(v07_b["rubric"]["impact_cap"], 20)
        self.assertEqual(
            v07_b["rubric"]["evidence_event_ids"],
            [
                "INV-V07-B-05",
                "INV-V07-B-08",
                "INV-V07-B-09",
                "INV-V07-B-10",
            ],
        )

        v08 = next(
            case
            for case in self.data["cases"]
            if case["case_id"] == "INV-V08"
        )
        v08_a = next(
            run for run in v08["runs"] if run["run_id"] == "INV-V08-A"
        )
        self.assertEqual(v08_a["rubric"]["rubric_score"], 20)
        self.assertEqual(v08_a["rubric"]["impact_cap"], 20)

    def test_local_contract_rejection_is_kept_as_fact(self) -> None:
        v04 = next(
            case
            for case in self.data["cases"]
            if case["case_id"] == "INV-V04"
        )
        self.assertEqual(
            v04["four_way"]["sources"]["local_llm"]["status"],
            "contract_rejected: successful run cannot include a root cause",
        )

    def test_analysis_can_be_omitted(self) -> None:
        data = build_webui_data(
            dataset=self.dataset,
            submission=self.submission,
            four_way_report=self.four_way,
            rubric_report=self.rubric,
            submission_path=SUBMISSION_PATH,
        )
        self.assertEqual(data["appendices"]["llm_analysis"], "")
        self.assertTrue(
            all(case["analysis"] is None for case in data["cases"])
        )

    def test_writer_emits_offline_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "webui"
            write_webui(self.data, output_dir)
            names = {
                path.name for path in output_dir.iterdir()
            }
            data_js = (output_dir / "data.js").read_text(
                encoding="utf-8"
            )

        # 2026-11-09 改：新增 appendices/ 目录（附录文件复制进站内，见
        # _appendices 的修复说明——原实现用 ../../ 越出静态服务根 ⇒ 链接全 404）
        self.assertEqual(
            names,
            {"index.html", "styles.css", "app.js", "data.js", "appendices"},
        )
        self.assertNotRegex(data_js, r"https?://")
        self.assertNotIn("INVOICE_EVAL_LLM_API_KEY", data_js)

    def test_appendix_links_are_inside_site_root(self) -> None:
        """附录链接必须是站内相对路径，不得用 ../ 越出静态服务根。

        2026-11-09 加：经霖实测页面附录链接全部 404——原实现写死
        `root = "../../"`，而静态服务以 output_dir 为根 ⇒ 越界。
        """
        appendices = self.data["appendices"]
        for key, href in appendices.items():
            if not href:
                continue
            self.assertFalse(
                href.startswith(("../", "/")),
                f"{key} 链接越出站点根：{href}",
            )
            self.assertTrue(
                href.startswith("appendices/"),
                f"{key} 应为 appendices/ 下的站内路径：{href}",
            )

    def test_written_appendix_files_are_reachable(self) -> None:
        """write_webui 必须把附录文件真实复制到 output_dir/appendices/。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "webui"
            write_webui(self.data, output_dir)
            appendix_dir = output_dir / "appendices"
            self.assertTrue(appendix_dir.is_dir(), "appendices/ 未创建")
            produced = {p.name for p in appendix_dir.iterdir()}
            expected = {
                Path(rel).name
                for key, rel in APPENDIX_FILES.items()
                if self.data["appendices"].get(key)
            }
            self.assertTrue(
                expected.issubset(produced),
                f"缺少附录文件：{expected - produced}",
            )

    def test_cli_generates_webui_without_changing_submission(self) -> None:
        before = hashlib.sha256(SUBMISSION_PATH.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "webui"
            exit_code = main(
                [
                    "webui",
                    "--cases",
                    str(CASES_PATH),
                    "--submission",
                    str(SUBMISSION_PATH),
                    "--four-way-report",
                    str(FOUR_WAY_PATH),
                    "--rubric-report",
                    str(RUBRIC_PATH),
                    "--llm-analysis",
                    str(ANALYSIS_PATH),
                    "--output-dir",
                    str(output_dir),
                ]
            )
            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "index.html").is_file())
            self.assertTrue((output_dir / "styles.css").is_file())
            self.assertTrue((output_dir / "app.js").is_file())
            self.assertTrue((output_dir / "data.js").is_file())
        after = hashlib.sha256(SUBMISSION_PATH.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    def test_rubric_source_hash_mismatch_is_rejected(self) -> None:
        rubric = copy.deepcopy(self.rubric)
        first_case = next(iter(rubric.values()))
        first_case["source_submission_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            build_webui_data(
                dataset=self.dataset,
                submission=self.submission,
                four_way_report=self.four_way,
                rubric_report=rubric,
                submission_path=SUBMISSION_PATH,
            )


if __name__ == "__main__":
    unittest.main()
