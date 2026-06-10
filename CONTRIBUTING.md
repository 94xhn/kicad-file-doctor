# Contributing

The most valuable issue you can file: **a KiCad file that KiCad rejects but
this tool passes** (or the reverse — a healthy file it complains about).
Attach the file or a minimal snippet plus your KiCad version.

## Development setup

```bash
git clone https://github.com/94xhn/kicad-file-doctor
cd kicad-file-doctor
python -m venv .venv
.venv/bin/pip install -e .[dev]      # Windows: .venv\Scripts\pip install -e .[dev]
```

## Running checks

```bash
ruff check .
pytest
```

Both must pass; CI runs them on Python 3.9 / 3.11 / 3.13 plus a gitleaks
secret scan.

## Architecture conventions

- `kicad_file_doctor/sexp.py` — S-expression parser, no KiCad knowledge.
- `kicad_file_doctor/checks.py` — all diagnostics plus the `diagnose()`
  driver. Text-level checks (regex/scanner, they carry line numbers) run
  even when the file does not parse; tree-level checks run after a
  successful parse.
- `kicad_file_doctor/cli.py` — argument parsing, file I/O, rendering.

Rules for new checks:

1. It must encode a **reproducible failure mode** (KiCad version noted),
   not folklore.
2. Run it against several real KiCad-saved files first. If healthy files
   trigger it, downgrade to warning or drop it — calibration against real
   files is this project's core promise.
3. Text-level checks should report a line number.

The package stays **zero-dependency**.
