"""Command-line interface for kicad-file-doctor."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from . import __version__
from .checks import diagnose

EXIT_HEALTHY = 0
EXIT_PROBLEMS = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kicad-file-doctor",
        description=(
            "Explain why KiCad rejects (or silently mis-loads) a "
            ".kicad_pcb / .kicad_sch file. KiCad's own error dialog says "
            "nothing; this prints the defect and the line number."
        ),
    )
    parser.add_argument(
        "files", nargs="+", metavar="FILE", help=".kicad_pcb / .kicad_sch file(s)"
    )
    parser.add_argument(
        "--format", choices=("text", "json"), default="text", dest="fmt"
    )
    parser.add_argument(
        "--strict", action="store_true", help="treat warnings as errors"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def _render_text(path: str, report: dict) -> str:
    errors = sum(1 for f in report["findings"] if f.severity == "error")
    warnings = sum(1 for f in report["findings"] if f.severity == "warning")
    lines = [
        f"{path}: {report['ftype']}, {report['lines']} lines - "
        f"{errors} error(s), {warnings} warning(s)"
    ]
    for f in report["findings"]:
        lines.append(f"  {f.severity.upper():7s} {f.check:17s} {f.message}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    reports = []
    for raw in args.files:
        path = Path(raw)
        try:
            data = path.read_bytes()
        except OSError as exc:
            print(f"error: cannot read {path}: {exc}", file=sys.stderr)
            return EXIT_USAGE
        report = diagnose(data)
        if args.strict:
            report["findings"] = [
                dataclasses.replace(f, severity="error")
                if f.severity == "warning"
                else f
                for f in report["findings"]
            ]
        reports.append((str(path), report))

    total_errors = sum(
        1 for _, r in reports for f in r["findings"] if f.severity == "error"
    )
    total_warnings = sum(
        1 for _, r in reports for f in r["findings"] if f.severity == "warning"
    )

    if args.fmt == "json":
        payload = {
            "version": __version__,
            "files": [
                {
                    "path": path,
                    "ftype": r["ftype"],
                    "lines": r["lines"],
                    "parsed": r["parsed"],
                    "findings": [f.to_dict() for f in r["findings"]],
                }
                for path, r in reports
            ],
            "total_errors": total_errors,
            "total_warnings": total_warnings,
        }
        print(json.dumps(payload, indent=2))
    else:
        for path, report in reports:
            print(_render_text(path, report))
        verdict = "PROBLEMS" if total_errors else "OK"
        print(
            f"{verdict}: {total_errors} error(s), {total_warnings} warning(s) "
            f"across {len(reports)} file(s)"
        )
    return EXIT_PROBLEMS if total_errors else EXIT_HEALTHY


if __name__ == "__main__":
    sys.exit(main())
