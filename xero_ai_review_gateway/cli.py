from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .errors import GatewayError
from .gateway import evaluate, validate_review, write_evaluation
from .util import build_root, path_within


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a fixed-policy, synthetic Xero review boundary.")
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate_parser = commands.add_parser("evaluate", help="evaluate the one allowlisted variance review")
    evaluate_parser.add_argument("--context", required=True, type=Path)
    evaluate_parser.add_argument("--request", required=True, type=Path)
    evaluate_parser.add_argument("--policy", required=True, type=Path)
    evaluate_parser.add_argument("--out", required=True, type=Path)
    decision_parser = commands.add_parser("validate-review", help="validate a human acknowledgement/escalation record")
    decision_parser.add_argument("--evidence", required=True, type=Path)
    decision_parser.add_argument("--receipt", required=True, type=Path)
    decision_parser.add_argument("--decision", required=True, type=Path, help="decision JSON under the bundled samples/ data or the working directory's build/")
    decision_parser.add_argument("--out", type=Path, help="optional JSON validation output below build/")
    return parser


def _survive_a_narrow_stream(stream: object) -> None:
    """Keep a path that the output encoding cannot represent from killing a finished run.

    Redirected stdout on Windows defaults to the ANSI code page, so a working
    directory holding one character outside it made the gateway exit 1 after
    the artefacts had already been written correctly.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(errors="backslashreplace")
    except (OSError, ValueError):
        pass


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        _survive_a_narrow_stream(stream)
    try:
        if args.command == "evaluate":
            model, evidence, receipt = evaluate(context_path=args.context, request_path=args.request, policy_path=args.policy)
            outputs = write_evaluation(model, evidence, receipt, args.out)
            print(f"xero-ai-review-gateway: REVIEW_READY; {len(model['findings'])} bounded finding(s)")
            for name, path in outputs.items():
                print(f"  {name}: {path}")
            return 0
        validation = validate_review(evidence_path=args.evidence, receipt_path=args.receipt, decision_path=args.decision)
        if args.out:
            out = path_within(args.out, build_root(), label="validation output", require_exists=False)
            try:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            except OSError as exc:
                raise GatewayError(f"validation output cannot be written to {out}: {exc}.") from exc
        print(f"xero-ai-review-gateway: {validation['status']}; {validation['decision_count']} decision(s); {validation['undecided_count']} undecided finding(s)")
        return 0
    except GatewayError as exc:
        print(f"xero-ai-review-gateway: blocked: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
