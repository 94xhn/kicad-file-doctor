from kicad_file_doctor.checks import diagnose


def run(text: str) -> list:
    return diagnose(text.encode("utf-8"))["findings"]


def by_check(findings, check):
    return [f for f in findings if f.check == check]


def errors(findings):
    return [f for f in findings if f.severity == "error"]


# ----------------------------------------------------------------- encoding


def test_utf8_bom_detected():
    findings = diagnose(b"\xef\xbb\xbf(kicad_pcb)")["findings"]
    (bom,) = by_check(findings, "utf8-bom")
    assert bom.severity == "error"
    # after stripping the BOM the rest still parses
    assert not by_check(findings, "unbalanced")


def test_invalid_utf8_reported_with_line():
    findings = diagnose(b"(kicad_pcb\n\xff\xfe\n)")["findings"]
    (enc,) = by_check(findings, "encoding")
    assert enc.line == 2


# ------------------------------------------------------------------ balance


def test_stray_close_paren_with_line():
    (finding,) = by_check(run("(kicad_pcb\n)\n)"), "unbalanced")
    assert finding.line == 3
    assert "stray ')'" in finding.message


def test_unclosed_open_paren_reports_deepest():
    # both parens unclosed: the deepest one (line 2) is the likely culprit
    (finding,) = by_check(run("(kicad_pcb\n  (segment"), "unbalanced")
    assert finding.line == 2
    assert "2 unclosed" in finding.message


def test_unclosed_outer_paren_reported():
    # (segment ...) is closed; the never-closed paren is kicad_pcb at line 1
    (finding,) = by_check(run("(kicad_pcb\n  (segment\n)"), "unbalanced")
    assert finding.line == 1


def test_parens_inside_strings_ignored():
    assert by_check(run('(kicad_pcb (gr_text "(((")\n)'), "unbalanced") == []


def test_unterminated_string_with_line():
    (finding,) = by_check(run('(kicad_pcb\n  (gr_text "oops)\n)'), "unbalanced")
    assert finding.line == 2
    assert "string" in finding.message


# ---------------------------------------------------------- float precision


def test_overprecision_float_reported_as_warning():
    # warning, not error: KiCad-saved files occasionally contain long
    # decimals and load fine (observed in real KiCad 10 boards)
    (finding,) = by_check(
        run("(kicad_pcb\n  (segment (start 0.9314004358267791 0))\n)"),
        "float-precision",
    )
    assert finding.line == 2
    assert finding.severity == "warning"


def test_six_decimals_are_fine():
    assert by_check(run("(kicad_pcb (at 1.123456 2.5))"), "float-precision") == []


def test_float_findings_truncated():
    body = "\n".join(f"  (xy 0.{'1' * 8} {i})" for i in range(30))
    findings = by_check(run(f"(kicad_pcb\n{body}\n)"), "float-precision")
    assert len(findings) == 11  # 10 + "and N more"
    assert "more" in findings[-1].message


# ----------------------------------------------------------------- gr_text


def test_grtext_literal_newline_warned():
    (finding,) = by_check(
        run('(kicad_pcb (gr_text "line1\\\\nline2" (at 0 0)))'.replace("\\\\", "\\")),
        "grtext-newline",
    )
    assert finding.severity == "warning"


def test_grtext_justify_warned_top_level_only():
    text = (
        "(kicad_pcb\n"
        '  (gr_text "hi" (at 0 0) (effects (font (size 1 1)) (justify left)))\n'
        '  (footprint "L:X" (layer "F.Cu") (at 0 0)\n'
        '    (fp_text user "ok" (at 0 0) (effects (justify left)))\n'
        "  )\n"
        ")"
    )
    findings = by_check(run(text), "grtext-justify")
    assert len(findings) == 1  # the footprint's fp_text justify is legal


# ----------------------------------------------------------- pcb tree checks


FP = (
    '  (footprint "L:R" (layer "F.Cu") (at 0 0)\n'
    '    (property "Reference" "{ref}" (at 0 0 0))\n'
    "    {extra}\n"
    '    (pad "1" smd rect (at 0 0) (size 1 1) (net "A"))\n'
    "  )\n"
)


def pcb(*fps: str) -> str:
    return "(kicad_pcb (version 20241229)\n" + "".join(fps) + ")"


def test_duplicate_references_reported():
    text = pcb(FP.format(ref="R1", extra=""), FP.format(ref="R1", extra=""))
    (finding,) = by_check(run(text), "dup-reference")
    assert "'R1'" in finding.message and "2 footprints" in finding.message
    assert "DSN" in finding.message


def test_placeholder_reference_hint():
    text = pcb(FP.format(ref="MH?", extra=""), FP.format(ref="MH?", extra=""))
    (finding,) = by_check(run(text), "dup-reference")
    assert "placeholder" in finding.message


def test_unique_references_clean():
    text = pcb(FP.format(ref="R1", extra=""), FP.format(ref="R2", extra=""))
    assert by_check(run(text), "dup-reference") == []


def test_footprint_library_field_error():
    text = pcb(FP.format(ref="U1", extra="(version 20240101)"))
    (finding,) = by_check(run(text), "fp-library-field")
    assert finding.severity == "error"
    assert "(version ...)" in finding.message


def test_kicad10_native_instance_fields_not_flagged():
    # KiCad 10 writes (embedded_fonts ...) and
    # (duplicate_pad_numbers_are_jumpers ...) into instances itself —
    # verified on real KiCad-10-saved boards. Flagging them would spam
    # every healthy file.
    text = pcb(
        FP.format(ref="U1", extra="(embedded_fonts no)"),
        FP.format(ref="U2", extra="(duplicate_pad_numbers_are_jumpers no)"),
    )
    assert by_check(run(text), "fp-library-field") == []


def test_sheet_path_without_component_uuid_warned():
    text = pcb(FP.format(ref="U1", extra='(path "/abc-123/")'))
    (finding,) = by_check(run(text), "sheet-path")
    assert finding.severity == "warning"


def test_sheet_path_normal_and_root_clean():
    text = pcb(
        FP.format(ref="U1", extra='(path "/abc/def")'),
        FP.format(ref="U2", extra='(path "/")'),
    )
    assert by_check(run(text), "sheet-path") == []


def test_pcb_summary_counts():
    text = pcb(FP.format(ref="R1", extra=""))
    (summary,) = by_check(run(text), "summary")
    assert "1 footprints (1 pads)" in summary.message


# ----------------------------------------------------------- sch tree checks


def sch(lib_defs: str, instances: str) -> str:
    return (
        "(kicad_sch (version 20250114)\n"
        f"  (lib_symbols\n{lib_defs}  )\n{instances})"
    )


def test_missing_lib_symbol_reported():
    text = sch(
        '    (symbol "Device:R" (pin_numbers hide))\n',
        '  (symbol (lib_id "Device:C") (at 0 0 0))\n'
        '  (symbol (lib_id "Device:C") (at 10 0 0))\n',
    )
    (finding,) = by_check(run(text), "missing-lib-symbol")
    assert finding.severity == "error"
    assert "'Device:C'" in finding.message and "2 symbol instance(s)" in finding.message


def test_complete_lib_symbols_clean():
    text = sch(
        '    (symbol "Device:R" (pin_numbers hide))\n',
        '  (symbol (lib_id "Device:R") (at 0 0 0))\n',
    )
    assert by_check(run(text), "missing-lib-symbol") == []


def test_library_fields_in_lib_symbols_not_flagged():
    # Official-library blocks embedded by KiCad 10 itself carry
    # (in_pos_files ...) etc. and load fine — verified on real schematics.
    text = sch(
        '    (symbol "Local:X" (in_pos_files yes))\n',
        '  (symbol (lib_id "Local:X") (at 0 0 0))\n',
    )
    assert errors(run(text)) == []


# ------------------------------------------------------------------- driver


def test_unparseable_file_skips_structural_checks():
    report = diagnose(b"(kicad_pcb (foo")
    assert report["parsed"] is False
    assert any("structural checks skipped" in f.message for f in report["findings"])


def test_ftype_detected():
    assert diagnose(b"(kicad_sch)")["ftype"] == "kicad_sch"
    assert diagnose(b"(kicad_pcb)")["ftype"] == "kicad_pcb"
    assert diagnose(b"hello")["ftype"] == "unknown"
