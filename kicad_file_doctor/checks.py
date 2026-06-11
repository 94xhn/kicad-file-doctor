"""Diagnostics for KiCad files that fail to load or behave oddly.

KiCad's only feedback on a bad file is a generic "failed to load" dialog —
``pcbnew.LoadBoard()`` returns ``None`` without raising, ``kicad-cli`` prints
nothing useful, and some defects (a missing lib_symbols definition, a
truncated save) load *successfully* and corrupt behaviour downstream. Each
check here encodes a failure mode observed in real script-generated files,
with a line number where the text allows it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .sexp import parse

#: footprint-instance fields that belong only in .kicad_mod library files;
#: KiCad 10 rejects boards that carry these inside (footprint ...) instances.
#: NOT flagged: (embedded_fonts ...) and (duplicate_pad_numbers_are_jumpers
#: ...) — KiCad 10 writes both into instances itself (verified on real
#: KiCad-10-saved boards).
FP_FILE_FIELDS_ERROR = ("version", "generator", "generator_version")

_FLOAT_RE = re.compile(r"-?\d+\.\d{7,}")


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str  # "error" | "warning" | "info"
    message: str
    line: int | None = None

    def to_dict(self) -> dict:
        out = {"check": self.check, "severity": self.severity, "message": self.message}
        if self.line is not None:
            out["line"] = self.line
        return out


# ------------------------------------------------------------- text checks


def check_bom(data: bytes) -> list[Finding]:
    if data.startswith(b"\xef\xbb\xbf"):
        return [
            Finding(
                "utf8-bom",
                "error",
                "file starts with a UTF-8 BOM (EF BB BF) - KiCad rejects it; "
                "write UTF-8 without BOM (PowerShell's 'Out-File -Encoding "
                "utf8' adds one)",
                line=1,
            )
        ]
    return []


def check_balance(text: str) -> list[Finding]:
    """Track parens and strings by hand so errors carry line numbers."""
    open_lines: list[int] = []
    line = 1
    in_string = False
    escape = False
    string_line = 0
    for ch in text:
        if ch == "\n":
            line += 1
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            string_line = line
        elif ch == "(":
            open_lines.append(line)
        elif ch == ")":
            if not open_lines:
                # warning, not error: KiCad's own parser tolerates stray ')'
                # (an official demo board carries hundreds and loads fine) —
                # but stricter S-expression tools will choke on them.
                return [
                    Finding(
                        "unbalanced",
                        "warning",
                        f"stray ')' at line {line} with no matching '(' - "
                        "KiCad itself tolerates this and still loads the "
                        "file, but strict S-expression tools will not",
                        line=line,
                    )
                ]
            open_lines.pop()
    if in_string:
        return [
            Finding(
                "unbalanced",
                "error",
                f"string opened at line {string_line} is never closed "
                "(check for an unescaped quote)",
                line=string_line,
            )
        ]
    if open_lines:
        return [
            Finding(
                "unbalanced",
                "error",
                f"'(' opened at line {open_lines[-1]} is never closed "
                f"({len(open_lines)} unclosed in total)",
                line=open_lines[-1],
            )
        ]
    return []


def check_float_precision(text: str, *, limit: int = 10) -> list[Finding]:
    """Numbers with more than 6 decimal places.

    Warning, not error: KiCad-saved files do occasionally contain long
    decimals and load fine, but full-repr floats (e.g. ``0.9314004358267791``)
    written by scripts have been observed to make KiCad 10 reject a board.
    When a file fails to load, these are prime suspects; format with '%.6f'
    (1 nm, KiCad's native precision).
    """
    findings: list[Finding] = []
    total = 0
    for lineno, line in enumerate(text.splitlines(), 1):
        for match in _FLOAT_RE.finditer(line):
            total += 1
            if len(findings) < limit:
                findings.append(
                    Finding(
                        "float-precision",
                        "warning",
                        f"line {lineno}: '{match.group(0)}' has more than 6 "
                        "decimal places - script-written full-repr floats "
                        "are known to break some KiCad 10 loads; prefer "
                        "'%.6f' (1 nm, KiCad's native precision)",
                        line=lineno,
                    )
                )
    if total > limit:
        findings.append(
            Finding(
                "float-precision",
                "warning",
                f"... and {total - limit} more over-precision floats",
            )
        )
    return findings


# NOTE: earlier drafts also flagged literal \n escapes and (justify ...)
# inside top-level gr_text. Both were dropped after running KiCad's own demo
# boards: 6/12 official boards store multi-line text with \n escapes and one
# board alone carries 1000+ justified gr_text nodes — all load fine. A check
# that fires on official demo boards is a false positive by definition.


# ------------------------------------------------------------- tree helpers


def _children(node: list):
    for item in node:
        if isinstance(item, list) and item:
            yield item


def _fp_reference(node: list) -> str:
    for item in _children(node):
        if item[0] == "property" and len(item) >= 3 and item[1] == "Reference":
            return str(item[2])
        if item[0] == "fp_text" and len(item) >= 3 and item[1] == "reference":
            return str(item[2])
    return ""


def _subtree_has_head(node: list, head: str) -> bool:
    for item in _children(node):
        if item[0] == head or _subtree_has_head(item, head):
            return True
    return False


# ---------------------------------------------------------------- pcb checks


def check_duplicate_references(root: list) -> list[Finding]:
    counts: dict[str, int] = {}
    for node in _children(root):
        if node[0] in ("footprint", "module"):
            ref = _fp_reference(node)
            if ref:
                counts[ref] = counts.get(ref, 0) + 1
    findings: list[Finding] = []
    for ref, count in sorted(counts.items()):
        if count < 2:
            continue
        placeholder = ref.endswith("?") or ref.endswith("**")
        hint = (
            " (unannotated placeholder - run annotation)"
            if placeholder
            else ""
        )
        # warning, not error: duplicate references are legal in KiCad and
        # official demo boards use them on purpose (stitching-via arrays,
        # microwave polygons) — but Specctra DSN export does fail on them.
        findings.append(
            Finding(
                "dup-reference",
                "warning",
                f"reference '{ref}' is used by {count} footprints{hint} - "
                "legal, but Specctra DSN export fails silently (0-byte "
                "file) on duplicate references",
            )
        )
    return findings


def check_footprint_file_fields(root: list) -> list[Finding]:
    findings: list[Finding] = []
    for node in _children(root):
        if node[0] not in ("footprint", "module"):
            continue
        ref = _fp_reference(node) or "<no ref>"
        heads = {item[0] for item in _children(node)}
        for head in FP_FILE_FIELDS_ERROR:
            if head in heads:
                findings.append(
                    Finding(
                        "fp-library-field",
                        "error",
                        f"{ref}: footprint instance contains library-file "
                        f"field '({head} ...)' - KiCad 10 rejects the board; "
                        "strip it when instantiating from a .kicad_mod",
                    )
                )
    return findings


def check_sheet_paths(root: list) -> list[Finding]:
    findings: list[Finding] = []
    for node in _children(root):
        if node[0] not in ("footprint", "module"):
            continue
        for item in _children(node):
            if item[0] == "path" and len(item) >= 2:
                value = str(item[1])
                if value.endswith("/") and value != "/":
                    ref = _fp_reference(node) or "<no ref>"
                    findings.append(
                        Finding(
                            "sheet-path",
                            "warning",
                            f"{ref}: sheet path '{value}' ends with '/' (no "
                            "component UUID) - usually a netlist parsed with "
                            "the wrong tstamps; update-from-schematic may "
                            "not match this footprint",
                        )
                    )
    return findings


def _count(root: list, *heads: str) -> int:
    return sum(1 for node in _children(root) if node[0] in heads)


def pcb_summary(root: list) -> Finding:
    footprints = [n for n in _children(root) if n[0] in ("footprint", "module")]
    pads = sum(1 for fp in footprints for item in _children(fp) if item[0] == "pad")
    return Finding(
        "summary",
        "info",
        f"{len(footprints)} footprints ({pads} pads), "
        f"{_count(root, 'segment')} segments, {_count(root, 'via')} vias, "
        f"{_count(root, 'zone')} zones - compare against what you expect; "
        "a broken save can write a structurally valid but nearly empty board",
    )


# ---------------------------------------------------------------- sch checks


def check_lib_symbols(root: list) -> list[Finding]:
    defined: set[str] = set()
    for node in _children(root):
        if node[0] == "lib_symbols":
            for sym in _children(node):
                if sym[0] == "symbol" and len(sym) >= 2:
                    defined.add(str(sym[1]))
    missing: dict[str, int] = {}
    for node in _children(root):
        if node[0] != "symbol":
            continue
        lib_id = next(
            (
                str(item[1])
                for item in _children(node)
                if item[0] == "lib_id" and len(item) >= 2
            ),
            None,
        )
        if lib_id and lib_id not in defined:
            missing[lib_id] = missing.get(lib_id, 0) + 1
    return [
        Finding(
            "missing-lib-symbol",
            "error",
            f"{count} symbol instance(s) reference '{lib_id}' but lib_symbols "
            "has no such definition - KiCad loads the schematic WITHOUT any "
            "error and the symbol's pins silently fail to connect (ERC then "
            "reports unconnected_wire_endpoint / isolated_pin_label nearby)",
        )
        for lib_id, count in sorted(missing.items())
    ]


def sch_summary(root: list) -> Finding:
    instances = _count(root, "symbol")
    defs = sum(
        1
        for node in _children(root)
        if node[0] == "lib_symbols"
        for sym in _children(node)
        if sym[0] == "symbol"
    )
    return Finding(
        "summary",
        "info",
        f"{instances} symbol instances, {defs} lib_symbols definitions, "
        f"{_count(root, 'wire')} wires, "
        f"{_count(root, 'label', 'global_label', 'hierarchical_label')} labels",
    )


# ------------------------------------------------------------------ driver


def diagnose(data: bytes) -> dict:
    """Run every applicable check; returns file type, line count and findings."""
    findings: list[Finding] = []
    findings += check_bom(data)
    if findings:
        data = data[3:]

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        line = data[: exc.start].count(b"\n") + 1
        findings.append(
            Finding(
                "encoding",
                "error",
                f"line {line}: not valid UTF-8 at byte {exc.start} "
                f"({exc.reason}) - KiCad files must be UTF-8",
                line=line,
            )
        )
        text = data.decode("utf-8", errors="replace")

    findings += check_balance(text)
    findings += check_float_precision(text)

    ftype = "unknown"
    parsed = False
    try:
        forms = parse(text)
        parsed = True
    except ValueError:
        forms = []

    root = next((f for f in forms if isinstance(f, list) and f), None)
    if root is not None:
        ftype = str(root[0])
        # A stray ')' can close the root early, orphaning the rest of the
        # file as top-level forms; KiCad still loads such files, so fold the
        # orphans back in before running the structural checks.
        root_idx = forms.index(root)
        orphans = [n for n in forms[root_idx + 1 :] if isinstance(n, list) and n]
        if orphans:
            root = list(root) + orphans

    if not parsed or root is None:
        findings.append(
            Finding(
                "summary",
                "info",
                "structural checks skipped - the file does not parse; fix "
                "the errors above first",
            )
        )
    elif ftype == "kicad_pcb":
        findings += check_duplicate_references(root)
        findings += check_footprint_file_fields(root)
        findings += check_sheet_paths(root)
        findings.append(pcb_summary(root))
    elif ftype == "kicad_sch":
        findings += check_lib_symbols(root)
        findings.append(sch_summary(root))

    order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: (order[f.severity], f.line or 0, f.check))
    return {
        "ftype": ftype,
        "lines": text.count("\n") + 1,
        "parsed": parsed,
        "findings": findings,
    }
