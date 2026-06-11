# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-06-11

### Added

- Text-level diagnostics with line numbers: UTF-8 BOM, invalid encoding,
  unbalanced parens / unterminated strings (quote-aware scanner reporting
  the opening line), over-precision floats.
- Tree-level diagnostics: missing `lib_symbols` definitions (loads without
  error, pins silently fail), duplicate footprint references (legal, but
  Specctra DSN export writes a 0-byte file), library-file header fields
  inside footprint instances, sheet paths missing the component UUID.
- Summary counts (footprints/pads/segments/vias/zones, symbol instances/
  wires/labels) to catch truncated-but-valid saves.
- Severity calibration against real KiCad-10-saved boards **and KiCad's
  official demo boards**: fields KiCad 10 writes itself (`embedded_fonts`,
  `duplicate_pad_numbers_are_jumpers`, library fields in embedded
  lib_symbols) and `gr_text` multi-line `\n` / `(justify ...)` are
  deliberately not flagged; float precision, duplicate references and
  stray `)` are warnings, not errors (an official demo board ships 349
  stray parens and pcbnew loads it fine — orphaned top-level forms after
  an early-closed root are folded back in so summary counts stay
  truthful).
- pre-commit hook definition.
- CLI with text/JSON output, `--strict`, multi-file aggregation (one
  unreadable file no longer aborts the rest), exit codes 0/1/2. 34-test
  pytest suite; zero errors on 4 real project files and the official
  demo set.
