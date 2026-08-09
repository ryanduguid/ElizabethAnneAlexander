from __future__ import annotations

import json
from pathlib import Path

import pytest

from xero_ai_review_gateway.errors import GatewayError
from xero_ai_review_gateway.gateway import _load_tb, evaluate, validate_review, write_evaluation
from xero_ai_review_gateway.util import package_root

PKG = Path(__file__).resolve().parents[1] / "xero_ai_review_gateway"


def _evaluate():
    return evaluate(
        context_path=Path("samples/contexts/sample-monthly-variance.context.json"),
        request_path=Path("samples/requests/sample-revenue-variance.request.json"),
        policy_path=Path("policy/demo-policy-v1.json"),
    )


def test_bundled_data_resolves_from_the_package() -> None:
    root = package_root()
    assert (root / "policy" / "demo-policy-v1.json").is_file()
    assert (root / "samples" / "inputs" / "sample-tb-2026-06-30.csv").is_file()


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


def test_evaluation_writes_only_below_cwd_build_and_decision_can_be_validated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    model, evidence, receipt = _evaluate()
    paths = write_evaluation(model, evidence, receipt, Path("build") / "test-output")

    assert all(path.exists() for path in paths.values())
    assert all(path.is_relative_to(tmp_path / "build") for path in paths.values())
    result = validate_review(
        evidence_path=paths["evidence"],
        receipt_path=paths["receipt"],
        decision_path=Path("samples/decisions/sample-review-decision.json"),
    )
    assert result["status"] == "DECISION_RECORDED"


def test_decision_file_is_accepted_from_cwd_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    model, evidence, receipt = _evaluate()
    paths = write_evaluation(model, evidence, receipt, Path("build") / "run")
    local_decision = tmp_path / "build" / "run" / "decision.json"
    local_decision.write_text((PKG / "samples" / "decisions" / "sample-review-decision.json").read_text(encoding="utf-8"), encoding="utf-8")

    result = validate_review(evidence_path=paths["evidence"], receipt_path=paths["receipt"], decision_path=local_decision)
    assert result["status"] == "DECISION_RECORDED"


def test_decision_file_outside_samples_and_build_is_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    model, evidence, receipt = _evaluate()
    paths = write_evaluation(model, evidence, receipt, Path("build") / "run")
    stray = tmp_path / "decision.json"
    stray.write_text((PKG / "samples" / "decisions" / "sample-review-decision.json").read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(GatewayError, match="human decision must exist under"):
        validate_review(evidence_path=paths["evidence"], receipt_path=paths["receipt"], decision_path=stray)


def test_evaluation_output_outside_cwd_build_is_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    model, evidence, receipt = _evaluate()

    with pytest.raises(GatewayError, match="output directory must stay within"):
        write_evaluation(model, evidence, receipt, tmp_path / "elsewhere")


def test_unbalanced_source_fails_closed(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    source = (PKG / "samples" / "inputs" / "sample-tb-2026-06-30.csv").read_text(encoding="utf-8")
    bad.write_text(source.replace(",10000.00,0.00,50000.00", ",10000.01,0.00,50000.00"), encoding="utf-8")

    with pytest.raises(GatewayError, match="movement debit and credit totals"):
        _load_tb(bad)


def test_unknown_section_is_denied_by_policy(tmp_path: Path) -> None:
    model, _, _ = _evaluate()
    request = json.loads((PKG / "samples" / "requests" / "sample-revenue-variance.request.json").read_text(encoding="utf-8"))
    request["section"] = "Assets"
    bad = tmp_path / "request.json"
    bad.write_text(json.dumps(request), encoding="utf-8")

    from xero_ai_review_gateway.gateway import _load_policy, _load_request

    policy = _load_policy(PKG / "policy" / "demo-policy-v1.json")
    with pytest.raises(GatewayError, match="not allowlisted"):
        _load_request(bad, policy)
    assert model["mode"] == "synthetic"


def test_v01_source_does_not_import_a_network_client() -> None:
    package_sources = "\n".join(path.read_text(encoding="utf-8") for path in PKG.glob("*.py"))
    for forbidden in ("requests", "urllib", "http.client", "socket", "mcp"):
        assert forbidden not in package_sources
