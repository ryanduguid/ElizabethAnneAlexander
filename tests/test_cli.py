from __future__ import annotations

from pathlib import Path

from xero_ai_review_gateway.cli import main


ROOT = Path(__file__).resolve().parents[1]


def test_cli_end_to_end() -> None:
    output = ROOT / "build" / "cli-test"
    assert main([
        "evaluate",
        "--context", str(ROOT / "samples" / "contexts" / "sample-monthly-variance.context.json"),
        "--request", str(ROOT / "samples" / "requests" / "sample-revenue-variance.request.json"),
        "--policy", str(ROOT / "policy" / "demo-policy-v1.json"),
        "--out", str(output),
    ]) == 0
    assert main([
        "validate-review",
        "--evidence", str(output / "reviewer-evidence.json"),
        "--receipt", str(output / "receipt.json"),
        "--decision", str(ROOT / "samples" / "decisions" / "sample-review-decision.json"),
    ]) == 0
