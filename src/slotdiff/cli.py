"""Command-line interface for storage layout comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import LayoutError, compare_layouts, load_layout


EXIT_CODES = {"PASS": 0, "REVIEW": 1, "FAIL": 2, "UNASSESSED": 3}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare Solidity compiler storage layouts offline")
    parser.add_argument("old", type=Path, help="Previous storageLayout or solc output JSON")
    parser.add_argument("new", type=Path, help="Proposed storageLayout or solc output JSON")
    parser.add_argument("--old-contract", help="SOURCE:NAME in previous solc output")
    parser.add_argument("--new-contract", help="SOURCE:NAME in proposed solc output")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)
    try:
        old = load_layout(json.loads(args.old.read_text(encoding="utf-8")), args.old_contract)
        new = load_layout(json.loads(args.new.read_text(encoding="utf-8")), args.new_contract)
        report = compare_layouts(old, new)
        report["inputs"] = {"old": str(args.old), "new": str(args.new),
                            "old_contract": args.old_contract,
                            "new_contract": args.new_contract}
    except (OSError, json.JSONDecodeError, LayoutError) as exc:
        report = {"status": "UNASSESSED", "reason": str(exc), "issues": []}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{report['status']} storage layout comparison")
        for issue in report["issues"]:
            print(f"  {issue['severity']} {issue['code']} {issue['variable']}: {issue['detail']}")
        if report["status"] == "UNASSESSED":
            print(f"  reason: {report['reason']}")
    return EXIT_CODES[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
