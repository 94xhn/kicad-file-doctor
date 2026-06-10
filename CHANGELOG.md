# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-06-11

### Added

- Text-level diagnostics with line numbers: UTF-8 BOM, invalid encoding,
  unbalanced parens / unterminated strings (quote-aware scanner reporting
  the opening line), over-precision floats, `gr_text` literal `\n`.
- Tree-level diagnostics: missing `lib_symbols` definitions (loads without
  error, pins silently fail), duplicate footprint references (Specctra DSN
  exports a 0-byte file), library-file header fields inside footprint
  instances, sheet paths missing the component UUID, top-level `gr_text`
  justify.
- Summary counts (footprints/pads/segments/vias/zones, symbol instances/
  wires/labels) to catch truncated-but-valid saves.
- Severity calibration against real KiCad-10-saved boards: fields KiCad 10
  writes itself (`embedded_fonts`, `duplicate_pad_numbers_are_jumpers`,
  library fields in embedded lib_symbols) are deliberately not flagged;
  float precision is a warning, not an error.
- CLI with text/JSON output, `--strict`, multi-file aggregation, exit codes
  0/1/2. 33-test pytest suite; verified zero errors on 4 real project files.
