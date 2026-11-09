import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "build-release.py"
VALIDATION = PROJECT_ROOT / "outputs" / "validation-v0.3.0.jsonl"
VERIFY_REPORT = PROJECT_ROOT / "outputs" / "verify-report.md"


class ReleasePackageTests(unittest.TestCase):
    def test_builds_source_archives_manifest_and_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "release"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output-dir",
                    str(output_dir),
                    "--validation",
                    str(VALIDATION),
                    "--verify-report",
                    str(VERIFY_REPORT),
                    "--version",
                    "0.3.0-test",
                    "--allow-dirty",
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )
            names = {path.name for path in output_dir.iterdir()}
            self.assertEqual(
                names,
                {
                    "invoice-agent-eval-v0.3.0-test-source.zip",
                    "invoice-agent-eval-v0.3.0-test-source.tar.gz",
                    "validation-submission.jsonl",
                    "VERIFY-REPORT.md",
                    "RELEASE-NOTES.md",
                    "SUBMISSION-MANIFEST.json",
                    "SHA256SUMS",
                },
            )
            with zipfile.ZipFile(
                output_dir / "invoice-agent-eval-v0.3.0-test-source.zip"
            ) as archive:
                archived = archive.namelist()
            self.assertIn(
                "invoice-agent-eval-v0.3.0-test/invoice_eval/version.py",
                archived,
            )
            self.assertFalse(any(name.endswith("/.env") for name in archived))

            manifest = json.loads(
                (output_dir / "SUBMISSION-MANIFEST.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["case_count"], 8)
            self.assertEqual(manifest["run_count"], 16)

            checksum_lines = (
                output_dir / "SHA256SUMS"
            ).read_text(encoding="utf-8").splitlines()
            for line in checksum_lines:
                digest, name = line.split("  ", 1)
                path = output_dir / name
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    digest,
                )


if __name__ == "__main__":
    unittest.main()
