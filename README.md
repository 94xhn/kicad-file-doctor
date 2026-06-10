# kicad-file-doctor

[![CI](https://github.com/94xhn/kicad-file-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/94xhn/kicad-file-doctor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](pyproject.toml)

KiCad says **"failed to load"**. This tells you **why — with line numbers.**

KiCad's only feedback on a bad file is a generic error dialog;
`pcbnew.LoadBoard()` returns `None` without raising, `kicad-cli` prints
nothing useful, and some defects load *successfully* and quietly corrupt
behaviour downstream (a missing `lib_symbols` definition, a truncated save, a
duplicate reference that makes DSN export write a 0-byte file). This tool
encodes those failure modes — each one observed in real script-generated
files — as a zero-dependency diagnostic you can run anywhere Python runs.

Built for the growing crowd that **generates KiCad files from scripts** (or
has an AI do it). [中文简介](#中文简介) below. Part of a small family:
[kicad-corner-lint](https://github.com/94xhn/kicad-corner-lint) ·
[kicad-board-lint](https://github.com/94xhn/kicad-board-lint).

```text
$ kicad-file-doctor examples/broken.kicad_pcb
examples/broken.kicad_pcb: kicad_pcb, 28 lines - 2 error(s), 3 warning(s)
  ERROR   dup-reference     reference 'R1' is used by 2 footprints - Specctra DSN export fails silently (0-byte file) on duplicate references
  ERROR   fp-library-field  R1: footprint instance contains library-file field '(version ...)' - KiCad 10 rejects the board; strip it when instantiating from a .kicad_mod
  WARNING sheet-path        R1: sheet path '/4a5b6c7d-...-aabbccddeeff/' ends with '/' (no component UUID) - usually a netlist parsed with the wrong tstamps
  WARNING float-precision   line 14: '-0.8249999999999998' has more than 6 decimal places - script-written full-repr floats are known to break some KiCad 10 loads; prefer '%.6f'
  WARNING float-precision   line 26: '100.0000000001' has more than 6 decimal places ...
  INFO    summary           2 footprints (4 pads), 1 segments, 0 vias, 0 zones - compare against what you expect; a broken save can write a structurally valid but nearly empty board
PROBLEMS: 2 error(s), 3 warning(s) across 1 file(s)
```

## Install & use

```bash
pip install git+https://github.com/94xhn/kicad-file-doctor

kicad-file-doctor MAIN.kicad_pcb MAIN.kicad_sch
kicad-file-doctor broken.kicad_pcb --format json
```

Exit codes: `0` no errors, `1` errors found (warnings too with `--strict`),
`2` file unreadable.

## What it checks

| Check | Severity | Failure mode it explains |
|---|---|---|
| `utf8-bom` | error | UTF-8 BOM — KiCad rejects the file (PowerShell's `Out-File -Encoding utf8` adds one) |
| `encoding` | error | not valid UTF-8, with the offending line |
| `unbalanced` | error | stray `)` / never-closed `(` / unterminated string — **with the line it was opened on** (quote-aware, so parens inside strings don't confuse it) |
| `missing-lib-symbol` | error | a `.kicad_sch` symbol instance references a `lib_id` with no `lib_symbols` definition — **KiCad loads without any error** and the symbol's pins silently fail to connect; ERC then reports confusing `unconnected_wire_endpoint` warnings nearby |
| `dup-reference` | error | duplicate footprint references — Specctra DSN export fails *silently* (0-byte file); unannotated `REF**` / `MH?` placeholders get a hint |
| `fp-library-field` | error | `(version/generator ...)` library-file headers inside a footprint *instance* — KiCad 10 rejects the board |
| `sheet-path` | warning | footprint `path` ending in `/` (no component UUID) — usually a netlist parsed with the wrong `tstamps`; update-from-schematic may not match |
| `float-precision` | warning | numbers with >6 decimals — script-written full-repr floats have broken KiCad 10 loads; prime suspects when a file won't open |
| `grtext-newline` / `grtext-justify` | warning | `\n` escapes and `(justify ...)` in top-level `gr_text` — observed to break some KiCad 10 builds |
| `summary` | info | footprint/pad/segment/via/zone counts — catch the "save succeeded but wrote a nearly-empty board" failure by comparing against what you expect |

### Severity philosophy (and why you can trust it)

Every check was **calibrated against real KiCad-10-saved boards**, not just
written from folklore:

- `error` = will reject the file or silently break a workflow, reproducibly.
- `warning` = known to break *some* KiCad builds / specific contexts; on a
  healthy board you should see few or none.
- Checks that folklore says are fatal but real KiCad-saved files contain
  routinely — `(embedded_fonts ...)` and
  `(duplicate_pad_numbers_are_jumpers ...)` inside footprint instances,
  library fields inside embedded `lib_symbols` — are **deliberately not
  flagged**. A diagnostic that cries wolf on every healthy file is worse
  than none.

### CI

```yaml
- name: KiCad file sanity
  run: |
    pip install git+https://github.com/94xhn/kicad-file-doctor
    kicad-file-doctor hardware/*.kicad_pcb hardware/*.kicad_sch
```

### Python API

```python
from kicad_file_doctor import diagnose

report = diagnose(open("MAIN.kicad_pcb", "rb").read())
for f in report["findings"]:
    print(f.severity, f.check, f.message)
```

## Known limitations (v0.1)

- The check list encodes failure modes met in practice on KiCad 9/10; it is
  **not** a complete format validator — a file can pass and still be
  rejected for a reason not yet catalogued (issues with a sample file are
  very welcome).
- `.kicad_mod` and worksheet files only get the generic checks (encoding,
  balance, floats).

## Related tools

- [kicad-board-lint](https://github.com/94xhn/kicad-board-lint) — electrical
  problems DRC silently accepts (ghost pads, thin power tracks).
- [kicad-corner-lint](https://github.com/94xhn/kicad-corner-lint) —
  right-angle / acute track corners.

## 中文简介

KiCad 说"加载失败"，但从不告诉你为什么——`pcbnew.LoadBoard()` 静默返回
`None`，`kicad-cli` 也没有任何细节。本工具是给"脚本/AI 生成 KiCad 文件"
人群的诊断器：零依赖直接分析 `.kicad_pcb` / `.kicad_sch` 文本，把实战中
踩过的拒收/静默损坏模式逐条报出，**带行号**。

- error 级：括号不平衡（带开括号行号、引号感知）、UTF-8 BOM、
  `lib_symbols` 缺定义（KiCad 不报错但引脚全部静默失连）、重复位号
  （DSN 导出静默写 0 字节）、footprint 实例混入库文件头字段。
- warning 级：超精度浮点（脚本 full-repr 浮点炸过 KiCad 10）、`path` 缺
  元件 UUID、`gr_text` 的 `\n`/`justify`。
- info：元件/焊盘/走线计数对账——抓"保存成功但写出近空板"。
- 所有检查在真实 KiCad 10 保存的板上做过反误报校准：`embedded_fonts`、
  `duplicate_pad_numbers_are_jumpers` 这类传言致命、实际 KiCad 自己就写的
  字段，**刻意不报**。

```bash
pip install git+https://github.com/94xhn/kicad-file-doctor
kicad-file-doctor 你的文件.kicad_pcb
```

## License

[MIT](LICENSE)
