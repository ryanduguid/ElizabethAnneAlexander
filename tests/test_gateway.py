from __future__ import annotations

import json
from pathlib import Path

import pytest

from xero_ai_review_gateway.errors import GatewayError
from xero_ai_review_gateway.gateway import _load_tb, evaluate, validate_review, write_evaluation


ROOT = Path(__file__).resolve().parents[1]


def _evaluate():
    return evaluate(
        context_path=ROOT / "samples" / "contexts" / "sample-monthly-variance.context.json",
        request_path=ROOT / "samples" / "requests" / "sample-revenue-variance.request.json",
        policy_path=ROOT / "policy" / "demo-policy-v1.json",
    )


def test_policy_bound_evaluation_returns_one_redacted_revenue_finding() -> None:
    model, evidence, receipt = _evaluate()

    assert model["status"] == "REVIEW_READY"
    assert len(model["findings"]) == 1
    assert model["findings"][0]["section"] == "Revenue"
    model_text = json.dumps(model)
    assert "Demo Entity Pty Ltd" not in model_text
    assert "Demo Sales" not in model_text
    assert "acct-300" not in model_text
    assert evidence["items"][0]["account_name"] == "Demo Sales"
    assert receipt["run_id"] == model["run_id"]


def test_evaluation_writes_only_below_build_and_decision_can_be_validated(tmp_path: Path) -> None:
    model, evidence, receipt = _evaluate()
    output = ROOT / "build" / "test-output"
    paths = write_evaluation(model, evidence, receipt, output)

    assert all(path.exists() for path in paths.values())
    result = validate_review(
        evidence_path=paths["evidence"],
        receipt_path=paths["receipt"],
        decision_path=ROOT / "samples" / "decisions" / "sample-review-decision.json",
    )
    assert result["status"] == "DECISION_RECORDED"


def test_unbalanced_source_fails_closed(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    source = (ROOT / "samples" / "inputs" / "sample-tb-2026-06-30.csv").read_text(encoding="utf-8")
    bad.write_text(source.replace(",10000.00,0.00,50000.00", ",10000.01,0.00,50000.00"), encoding="utf-8")

    with pytest.raises(GatewayError, match="movement debit and credit totals"):
        _load_tb(bad)


def test_unknown_section_is_denied_by_policy(tmp_path: Path) -> None:
    model, _, _ = _evaluate()
    request = json.loads((ROOT / "samples" / "requests" / "sample-revenue-variance.request.json").read_text(encoding="utf-8"))
    request["section"] = "Assets"
    bad = tmp_path / "request.json"
    bad.write_text(json.dumps(request), encoding="utf-8")

    from xero_ai_review_gateway.gateway import _load_policy, _load_request

    policy = _load_policy(ROOT / "policy" / "demo-policy-v1.json")
    with pytest.raises(GatewayError, match="not allowlisted"):
        _load_request(bad, policy)
    assert model["mode"] == "synthetic"


def test_v01_source_does_not_import_a_network_client() -> None:
    package_sources = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "xero_ai_review_gateway").glob("*.py"))
    for forbidden in ("requests", "urllib", "http.client", "socket", "mcp"):
        assert forbidden not in package_sources
