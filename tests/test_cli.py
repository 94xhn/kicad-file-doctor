import json
from pathlib import Path

import pytest

from kicad_file_doctor.cli import main

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_broken_pcb_fails_with_diagnoses(capsys):
    assert main([str(EXAMPLES / "broken.kicad_pcb")]) == 1
    out = capsys.readouterr().out
    assert "float-precision" in out
    assert "dup-reference" in out
    assert "fp-library-field" in out
    assert "sheet-path" in out
    assert "PROBLEMS" in out


def test_broken_sch_reports_missing_lib_symbol(capsys):
    assert main([str(EXAMPLES / "broken.kicad_sch")]) == 1
    out = capsys.readouterr().out
    assert "missing-lib-symbol" in out


def test_good_board_is_ok(capsys):
    assert main([str(EXAMPLES / "good.kicad_pcb")]) == 0
    out = capsys.readouterr().out
    assert "OK: 0 error(s)" in out
    assert "summary" in out  # info stats always printed


def test_strict_promotes_warnings(tmp_path):
    board = tmp_path / "warn_only.kicad_pcb"
    board.write_text(
        '(kicad_pcb (version 20241229)\n'
        '  (footprint "L:R" (layer "F.Cu") (at 0 0)\n'
        '    (property "Reference" "U1" (at 0 0 0))\n'
        '    (path "/abc-123/")\n'
        '    (pad "1" smd rect (at 0 0) (size 1 1) (net "A"))\n'
        "  )\n)",
        encoding="utf-8",
    )
    assert main([str(board)]) == 0
    assert main([str(board), "--strict"]) == 1


def test_json_output(capsys):
    main([str(EXAMPLES / "broken.kicad_pcb"), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["total_errors"] >= 1
    (file_report,) = payload["files"]
    assert file_report["ftype"] == "kicad_pcb"
    assert any(f["check"] == "dup-reference" for f in file_report["findings"])


def test_multiple_files(capsys):
    code = main(
        [str(EXAMPLES / "good.kicad_pcb"), str(EXAMPLES / "broken.kicad_pcb")]
    )
    assert code == 1
    assert "across 2 file(s)" in capsys.readouterr().out


def test_missing_file_exits_2(capsys):
    assert main(["nope.kicad_pcb"]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_unreadable_file_does_not_block_other_files(capsys):
    assert main(["nope.kicad_pcb", str(EXAMPLES / "good.kicad_pcb")]) == 2
    captured = capsys.readouterr()
    assert "cannot read" in captured.err
    assert "good.kicad_pcb" in captured.out  # the readable file was still checked


def test_version_flag():
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
