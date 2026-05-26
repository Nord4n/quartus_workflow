# DE10-Lite HW Workflow

## HDL Development, Synthesis, and FPGA Programming on Intel DE10-Lite (MAX10)

Erik Nordahl — v0.6 — 2026-04-13

---

## Contents

- [1. Introduction](#1-introduction)
  - [1.1 Purpose and Scope](#11-purpose-and-scope)
  - [1.2 Quartus Version](#12-quartus-version)
  - [1.3 Relation to the RISC-V SW Workflow](#13-relation-to-the-risc-v-sw-workflow)
- [2. Architecture Overview](#2-architecture-overview)
  - [2.1 Directory Layout](#21-directory-layout)
  - [2.2 Data Flow](#22-data-flow)
- [3. Configuration — hw_workflow.toml](#3-configuration--hw_workflowtoml)
- [4. Setting Up a New Project](#4-setting-up-a-new-project)
  - [4.1 Scaffold Command](#41-scaffold-command)
  - [4.2 Typical Setup Workflow](#42-typical-setup-workflow)
  - [4.3 Switching Projects](#43-switching-projects)
  - [4.4 Setting the Top-Level Entity](#44-setting-the-top-level-entity)
- [5. hw_workflow.py Subcommands](#5-hw_workflowpy-subcommands)
  - [5.1 Core Build Flow](#51-core-build-flow)
  - [5.2 HDL / IP](#52-hdl--ip)
  - [5.3 Simulation](#53-simulation)
  - [5.4 Utility](#54-utility)
  - [5.5 system-console Diagnostics](#55-system-console-diagnostics)
  - [5.6 Nios V Software Development](#56-nios-v-software-development)
- [6. Launching GUI Tools from the Terminal](#6-launching-gui-tools-from-the-terminal)
- [7. VUnit Simulation](#7-vunit-simulation)
- [8. Notes on Windows-Native Execution](#8-notes-on-windows-native-execution)
- [9. Timing Closure and Power Optimization](#9-timing-closure-and-power-optimization)
  - [9.1 Reading the Build Summary](#91-reading-the-build-summary)
  - [9.2 Timing Closure — Common Techniques](#92-timing-closure--common-techniques)
  - [9.3 Power Optimization](#93-power-optimization)
- [10. Nios V Software Workflow](#10-nios-v-software-workflow)
  - [10.1 Prerequisites](#101-prerequisites)
  - [10.2 End-to-End Workflow](#102-end-to-end-workflow)
  - [10.3 OCM Size Constraint and Toolchain Notes](#103-ocm-size-constraint-and-toolchain-notes)
- [Appendix A — Quartus CLI Tool Reference](#appendix-a--quartus-cli-tool-reference)
- [Appendix B — Design Decisions](#appendix-b--design-decisions)

---

## 1. Introduction

### 1.1 Purpose and Scope

The HW module provides a `hw_workflow.py` master script and `hw_workflow.toml`
configuration file as a terminal-first interface to the Intel Quartus Prime toolchain
for the DE10-Lite FPGA board.

Goals:

- **Single entry point** — one script covers synthesis, programming, simulation,
  report parsing, and Quartus GUI launch.
- **Windows-native** — Quartus tools require Windows paths; the script runs directly
  in PowerShell or CMD without a WSL layer.
- **Board-agnostic structure** — configurable via `hw_workflow.toml`; the DE10-Lite
  (MAX10) is the primary target, but the patterns apply to any Quartus project.
- **Complementary, not dependent** — the HW module can be used standalone or
  alongside the RISC-V SW workflow (which consumes `.sopcinfo` and `.sof` outputs).

### 1.2 Quartus Version

The module has been verified against **Quartus Prime Lite 25.1** on Windows 10.
Quartus 18.1 is not currently supported — the Nios V toolchain (`niosv-bsp`,
`niosv-app`, RiscFree) ships only with Quartus 25.x, and Platform Designer in
25.1 no longer includes the legacy Nios II IP.

If Quartus 18.1 support is added in the future, Nios II projects would require
the separate **Nios II Eclipse SDK** for software development rather than the
`gen-bsp` / `build-app` commands used by Nios V.

### 1.3 Relation to the RISC-V SW Workflow

This module can be used standalone or alongside the
[riscv_de10_workflow](https://github.com/Nord4n/riscv_de10_workflow)
repository. Two integration patterns are supported:

- **Side-by-side**: `quartus_workflow/` lives next to `riscv_de10_workflow/`.
  Set `sopcinfo` and `sof` paths in `hw_workflow.toml` to point at the
  locations consumed by `riscv_de10_workflow/workflow.toml`.
- **Replacement**: `quartus_workflow/` replaces the `HW/` directory inside
  `riscv_de10_workflow/`. The `.sopcinfo` and `.sof` outputs land at the paths
  the SW workflow already expects.

| Artifact | Produced by | Consumed by |
| -------- | ----------- | ----------- |
| `<name>.sopcinfo` | Platform Designer (`open-pd` → Generate HDL) | `riscv-workflow setup` |
| `<name>.sof`      | Quartus compilation (`build`)                | `riscv-workflow program-hw` |

No other coupling exists between the two modules.

---

## 2. Architecture Overview

### 2.1 Directory Layout

```text
quartus_workflow/
├── hw_workflow.py          # Master script
├── hw_workflow.toml        # Project configuration
├── setup_env.ps1           # One-time environment setup (adds bin/ to PATH)
├── bin/
│   ├── quartus-workflow    # Bash/WSL wrapper
│   └── quartus-workflow.bat  # Windows wrapper
├── quartus_workspace/      # Quartus project files (gitignored)
│   └── <project_name>/
│       ├── <name>.qpf      # Quartus project file
│       ├── <name>.qsf      # Settings and pin assignments
│       ├── <name>.qsys     # Platform Designer system (optional)
│       └── <name>_top.vhd  # Top-level HDL file
├── lib/                    # Shared board support assets
│   ├── IPs/                # Custom Platform Designer IP components
│   ├── packages/           # Reusable VHDL packages (e.g. sync_pkg)
│   └── board/
│       └── de10_lite/
│           ├── assignments/  # DE10-Lite pin assignments (.qsf)
│           ├── presets/      # Platform Designer IP presets (.qprs)
│           ├── templates/    # Board-specific top-level HDL templates
│           └── systems/      # Platform Designer system templates (planned)
├── sim/                    # VUnit simulation
│   ├── run.py              # VUnit entry point
│   └── vunit_out/          # Simulation outputs (gitignored)
└── doc/
    ├── hw_workflow.md      # This document
    └── hw_toolchain_setup.md
```

### 2.2 Data Flow

```text
hw_workflow.toml
      │
      ▼
hw_workflow.py
      │
      ├──▶ quartus_sh --flow compile  (build: map → fit → asm → sta)
      │         └──▶ output_files/<name>.sof  ──▶ program / RISC-V SW workflow
      │
      ├──▶ Platform Designer (open-pd)
      │         └──▶ <name>.sopcinfo ──▶ gen-bsp
      │                                      └──▶ gen-app
      │                                               └──▶ build-app → app.bin ──▶ console-load
      │
      ├──▶ quartus_pgm   (program FPGA via USB Blaster)
      │
      ├──▶ HW/sim/run.py (VUnit simulation)
      │
      └──▶ GUI launchers (open-quartus, open-pd, open-programmer, open-timing)
```

---

## 3. Configuration — hw_workflow.toml

`hw_workflow.toml` is the single source of truth for all paths and tool settings.
It lives in the `quartus_workflow/` root. All `[files]` paths are relative to this
directory and are resolved to absolute paths by `scripts/lib/hw_config.py`.

```toml
[tools]
quartus_version = "25.1"            # Quartus Prime Lite version
device          = "10M50DAF484C7G"  # DE10-Lite MAX 10 FPGA device
board           = "de10-lite"       # selects pin assignments and top-level template
simulator       = "modelsim"        # ghdl | modelsim
# quartus_base = "C:/altera_lite/25.1std/quartus/bin64"  # optional: override tool search path
# niosv_base = "C:/altera_lite/25.1std/niosv/bin"  # optional: override niosv tool search
# riscfree   = "C:/altera_lite/25.1std/riscfree/RiscFree/RiscFree.exe"  # optional: override IDE path

[project]
name     = "my_system"
hdl_lang = "vhdl"                   # vhdl | verilog

[files]
qpf  = "quartus_workspace/my_system/my_system.qpf"
qsys = "quartus_workspace/my_system/my_system.qsys"
sof  = "quartus_workspace/my_system/output_files/my_system.sof"
sopcinfo = "quartus_workspace/my_system/my_system.sopcinfo"
# bsp_dir  = "software/hal_bsp"   # default: <sopcinfo-dir>/software/<type>_bsp
# app_dir  = "software/app"       # default: <sopcinfo-dir>/software/app
```

`[project]` and `[files]` are updated automatically when running
`quartus-workflow setup` or `quartus-workflow set-project`.

---

## 4. Setting Up a New Project

`quartus-workflow setup` creates a complete, ready-to-compile Quartus project scaffold
under `quartus_workspace/` and updates `hw_workflow.toml` to point at the new project.

### 4.1 Scaffold Command

```text
quartus-workflow setup <name> [--lang vhdl|verilog] [--pd] [--pins] [--quartus]
```

| Flag | Default | Description |
| ----------- | ------------------- | -------------------------------------------------- |
| `<name>` | required | Project name; creates `quartus_workspace/<name>/` |
| `--lang` | `project.hdl_lang` | HDL language for the top-level template |
| `--pd` | off | Include Platform Designer system and QIP reference |
| `--pins` | off | Append DE10-Lite pin assignments from `lib/board/de10_lite/assignments/` |
| `--sdc` | off | Generate `<name>.sdc` with DE10-Lite 50 MHz clock constraint and register it in the `.qsf` |
| `--quartus` | off | Open Quartus Prime IDE after scaffold creation |

**Files created by `setup`:**

| File | Created when |
| ----------------------------------------- | ------------ |
| `<name>.qpf` | Always |
| `<name>.qsf` | Always — device, top entity, and HDL source pre-configured |
| `<name>_top.vhd` / `<name>_top.v` | Always — bare top-level template |
| `<name>.qsys` | Only with `--pd` |

`setup` is idempotent: existing files are skipped with a `[skip]` message; only
missing files are created. When `--pd` is given on an existing project, the
`QIP_FILE` assignment is patched into the `.qsf` if not already present.
When `--pins` is given, the DE10-Lite pin block is appended once and
subsequent runs are no-ops.

`hw_workflow.toml` `[project]` and `[files]` sections are updated automatically on
every `setup` run.

### 4.2 Typical Setup Workflow

**Pure HDL project (no Platform Designer):**

```text
quartus-workflow setup my_proj --lang vhdl --pins
quartus-workflow set-top my_proj_top.vhd
quartus-workflow open-quartus     # verify pin assignments, add SDC constraints
quartus-workflow build
```

**Project with a Platform Designer system (e.g., Nios V soft-core):**

```text
quartus-workflow setup my_system --lang vhdl --pd
# Note: the PD-generated SDC (my_system/synthesis/my_system.sdc) is
#       automatically registered in the .qsf by setup --pd.
quartus-workflow open-pd          # add IP, configure, Generate HDL
quartus-workflow sync-top         # update component declaration in top HDL from PD output
quartus-workflow apply-pins       # apply DE10-Lite pin assignments to .qsf
quartus-workflow build
```

### 4.3 Switching Projects

To update `hw_workflow.toml` to point at a different project already present in
`quartus_workspace/` without re-running `setup`:

```text
quartus-workflow set-project <name>
```

Updates `[files]` paths to `quartus_workspace/<name>/`. If a `.qpf` exists in the
directory, its stem is used as the project name; otherwise the directory name is used.

### 4.4 Setting the Top-Level Entity

```text
quartus-workflow set-top <entity>
```

Writes or updates `TOP_LEVEL_ENTITY` in the project `.qsf`. Accepts a filename or a
bare entity/module name — path and extension are stripped automatically:

```text
quartus-workflow set-top my_system_top.vhd   # -> TOP_LEVEL_ENTITY my_system_top
quartus-workflow set-top my_system_top       # -> TOP_LEVEL_ENTITY my_system_top
```

---

## 5. hw_workflow.py Subcommands

> Commands marked *(planned)* are not yet implemented. All others are available
> via `quartus-workflow <command>` or `python hw_workflow.py <command>`.
> Currently planned (not yet implemented): `jic`, `terminal`.

### 5.1 Core Build Flow

| Command | Quartus Executable(s) | Description |
| --------- | ----------------------------- | ------------------------------------------------ |
| `build` | `quartus_sh --flow compile` | Full compilation (map → fit → asm → sta) + resource and timing summary |
| `program` | `quartus_pgm` | Flash `.sof` to FPGA via USB Blaster (JTAG) |
| `synth` | `quartus_map` | Analysis & Synthesis only |
| `elab` | `quartus_map --analysis_and_elaboration` | Check HDL for errors without full synthesis |
| `timing` | `quartus_sta` | Run TimeQuest Timing Analyzer standalone; print Fmax summary |
| `power`  | `quartus_pow` | Run Power Analyzer standalone; print total/dynamic/static power summary |

### 5.2 HDL / IP

| Command | Calls | Description |
| --------- | --------------- | ---------------------------------------------------- |
| `sync-top` | — | Sync component declaration in `<name>_top.vhd` from PD-generated `<name>_inst.vhd`; warns for unconnected new ports |
| `gen-pd` | `qsys-generate` | Regenerate Platform Designer HDL from `.qsys` file |

### 5.3 Simulation

| Command | Calls | Description |
| ---------- | --------------- | ------------------------------------------------- |
| `simulate` | `sim/run.py` | Run VUnit test suite (`--simulator ghdl\|modelsim`) |

### 5.4 Utility

| Command | Description |
| ---------- | ------------------------------------------------------------------ |
| `apply-pins` | Apply DE10-Lite pin assignments to the project `.qsf`; reads board from `tools.board`; idempotent |
| `report` | Parse existing `.rpt` files — print logic utilization, Fmax, worst slack; no Quartus tool required |
| `clean` | Delete `output_files/`, `db/`, `incremental_db/` (`--keep-sof` preserves `.sof`; `--dry-run` previews) |
| `jic` *(planned)* | `quartus_cpf` — convert `.sof` → `.jic` for non-volatile flash |
| `terminal` *(planned)* | `nios2-terminal` — attach to Nios V / Nios II JTAG UART |

### 5.5 system-console Diagnostics

Thin wrappers around Tcl scripts passed to `system-console --script`.
All commands require a JTAG Avalon Master Bridge in the Platform Designer system.

| Command | Description |
| ------------------------------------------- | ---------------------------------------------------- |
| `console-scan` | Scan JTAG chain — print connected Avalon masters and devices |
| `console-peek <addr>` | Read 32-bit word from `<addr>` via JTAG Avalon Master |
| `console-poke <addr> <val>` | Write 32-bit word `<val>` to `<addr>` via JTAG Avalon Master |
| `console-load [bin] [baseaddr] [--master PATH]` | Load `.bin` into Avalon memory; `bin` defaults to `<app_dir>/build/app.bin`; `baseaddr` parsed from `bsp/system.h` |

### 5.6 Nios V Software Development

Commands for generating and building a Nios V application from a Platform Designer system.
Requires `sopcinfo` to be set in `hw_workflow.toml` and **Generate HDL** to have been run
in Platform Designer.

| Command | Calls | Description |
| ---------------------------------------------------- | ----------- | -------------------------------------------------------- |
| `gen-bsp [--type hal\|ucosii\|freertos] [--bsp-dir PATH]` | `niosv-bsp` | Generate or update BSP from `.sopcinfo`. Default `bsp_dir`: `<sopcinfo-dir>/software/<type>_bsp` |
| `gen-app [--bsp-dir PATH] [--app-dir PATH] [--srcs PATH]` | `niosv-app` | Generate application `CMakeLists.txt`. Default `app_dir`: `<sopcinfo-dir>/software/app` |
| `build-app [--bsp-dir PATH] [--app-dir PATH] [--clean]` | cmake | cmake configure + build → `.elf` + `.bin`. Prompts to clean build dir if it exists; `--clean` skips the prompt |

---

## 6. Launching GUI Tools from the Terminal

All Quartus GUI tools can be opened directly from the terminal using
`quartus-workflow` subcommands. Project files from `hw_workflow.toml` are passed
automatically.

| Tool | CLI Command | Notes |
| -------------------- | ------------------------------- | -------------------------------------------- |
| Quartus Prime IDE | `quartus-workflow open-quartus` | Opens with project `.qpf` |
| Platform Designer | `quartus-workflow open-pd` | Opens with project `.qsys` (if it exists) |
| Programmer | `quartus-workflow open-programmer` | Opens Quartus Programmer GUI |
| TimeQuest Timing | `quartus-workflow open-timing` | Opens TimeQuest Timing Analyzer GUI |
| Power Analyzer | `quartus-workflow power --open-gui` | Runs `quartus_pow` and opens PowerPlay Power Analyzer GUI |
| Nios V BSP Editor | `quartus-workflow open-bsp [--settings [PATH]]` | Opens `niosv-bsp-editor`; `--settings` auto-loads `<bsp_dir>/settings.bsp` |
| Nios V Command Shell | `quartus-workflow open-niosv-shell` | Opens `niosv-shell` with `PATH`, `QUARTUS_ROOTDIR`, and `SOPC_KIT_NIOS2` configured |
| Ashling RiscFree IDE | `quartus-workflow open-riscfree [--workspace PATH]` | Eclipse-based IDE for Nios V development; `--workspace` sets the Eclipse workspace path |

All GUI commands are non-blocking — the terminal returns immediately after launching.

**Tools accessible only through the Quartus Prime IDE** (no standalone executable;
open with `quartus-workflow open-quartus` and navigate from there):

| Tool | Menu path |
| ----------------------------- | ----------------------------------------- |
| Pin Planner | **Assignments → Pin Planner** |
| Assignment Editor | **Assignments → Assignment Editor** |
| Project Settings | **Assignments → Settings** (Ctrl+Shift+E) |
| Signal Tap Logic Analyzer | **Tools → Signal Tap Logic Analyzer** |
| Power Analyzer | `quartus-workflow power --open-gui` or **Tools → PowerPlay Power Analyzer** |
| Chip Planner | **Tools → Chip Planner** |
| RTL / Technology Map Viewer | **Tools → Netlist Viewers** |

Pin assignments can also be written directly in the `.qsf` file as
`set_location_assignment` and `set_instance_assignment` directives, or applied in
bulk with `quartus-workflow apply-pins`. Additional `open-*` workflow commands may
be added in the future as tools are actively used.

### 6.1 Accessing GUI Tool Data Without the GUI

For scripting and automation, the underlying data for GUI-only tools is accessible
as plain text:

| GUI Tool           | CLI / File-based Alternative                                             |
| ------------------ | ------------------------------------------------------------------------ |
| Settings dialog    | Edit `.qsf` directly or use `quartus_sh --set`                           |
| Assignment Editor  | `.qsf` `set_location_assignment` / `set_instance_assignment` entries     |
| Pin Planner        | Pin assignments are plain `.qsf` lines; apply in bulk with `apply-pins`  |
| Compilation Report | `.rpt` files under `output_files/` are plain text; `report` parses them  |
| Chip Planner       | No CLI equivalent — floorplanning only                                   |

---

## 7. VUnit Simulation

`sim/run.py` is the VUnit entry point. It discovers and compiles all test benches
in `sim/` and runs them with the configured simulator.

**GHDL (WSL — verified):**

```bash
VUNIT_SIMULATOR=ghdl python3 sim/run.py
```

**Questa FSE (Windows PowerShell — verified):**

```powershell
$env:PATH = "C:\altera_lite\25.1std\questa_fse\win64;" + $env:PATH
$env:VUNIT_SIMULATOR = "modelsim"
python sim\run.py
```

Or via the workflow script:

```text
quartus-workflow simulate
quartus-workflow simulate --simulator ghdl
```

> Questa FSE does **not** work from WSL — VUnit passes Linux paths to the Windows
> executable, causing `NonZeroExitCode`. Use Windows PowerShell for Questa.

`run.py` uses plain `VUnit.from_argv()` — compatible with VUnit 4.6.2 and earlier.

Simulation outputs are written to `sim/vunit_out/` (gitignored).

---

## 8. Notes on Windows-Native Execution

`hw_workflow.py` runs natively on Windows. Key differences from the RISC-V
`workflow.py` (which targets WSL):

- Quartus executables are found automatically by searching default install paths
  (`C:\altera_lite\25.1std\...`, `C:\intelFPGA_lite\...`) or from
  `tools.quartus_base` in `hw_workflow.toml`.
- `quartus_sh`, `quartus_pgm`, and `quartus_staw` live in `bin64\`.
- `qsys-edit.exe` and `system-console.exe` live in `quartus\sopc_builder\bin\`.
- `nios2-terminal.exe` lives in `nios2eds\bin\`.
- WSL path conversion (`_to_win_path`) is applied automatically when invoking
  Windows executables from a WSL shell.

### 8.1 Terminal Output Colour Coding

When stdout is a terminal (TTY), `hw_workflow.py` colour-codes its own output
for readability. Colours are suppressed when output is redirected to a file or pipe.

| Prefix | Colour | Meaning |
| ------ | ------ | ------- |
| `[+]` | Bright green | Command completed successfully |
| `[warn]` / `[!]` | Magenta | Warning — action may be required |
| `ERROR:` | Red | Fatal error — command aborted |

Quartus tools print their own `Info:` lines in standard green. The workflow script
uses bold green (`\033[1;32m`) for `[+]` messages to distinguish them from
Quartus tool output that appears immediately before.

---

## 9. Timing Closure and Power Optimization

### 9.1 Reading the Build Summary

After `build`, `timing`, or `report`, the workflow prints a summary table:

| Field          | Source file  | Meaning                                                                    |
| -------------- | ------------ | -------------------------------------------------------------------------- |
| Logic elements | `.fit.rpt`   | LUT/LE count used / available                                              |
| Registers      | `.fit.rpt`   | Flip-flop count                                                            |
| Fmax           | `.sta.rpt`   | Worst-case Fmax across user-defined clocks (`altera_reserved_*` excluded)  |

An Fmax below your target clock frequency means timing is not met and the
design may fail in hardware. Run `quartus-workflow open-timing` to inspect
the critical path in the TimeQuest GUI.

### 9.2 Timing Closure — Common Techniques

**SDC constraints** (`.sdc` file):

Without an SDC file, Quartus uses relaxed defaults and may not flag failing
paths. Run `setup --sdc` to generate a `<name>.sdc` template and register it
automatically. For Platform Designer projects, `setup --pd` registers the
PD-generated SDC (`<name>/synthesis/<name>.sdc`) automatically.

To add constraints manually, create `<name>.sdc` and register it in the `.qsf`:

```tcl
# Constrain the 50 MHz clock on MAX10_CLK1_50 (DE10-Lite)
create_clock -period 20.000 -name clk [get_ports {MAX10_CLK1_50}]
```

```text
set_global_assignment -name SDC_FILE <name>.sdc
```

**Synthesis optimization goal** — edit the project `.qsf`:

```text
set_global_assignment -name OPTIMIZATION_TECHNIQUE SPEED   # default: BALANCED
```

**Register retiming** — allows Quartus to move registers across combinational
logic to balance pipeline stages:

```text
set_global_assignment -name PHYSICAL_SYNTHESIS_REGISTER_RETIMING ON
```

### 9.3 Power Optimization

The MAX10 on DE10-Lite has a fixed core voltage (1.2 V); I/O standards are
set by the pin assignment QSF and are not easily changed per-signal.
Software-controllable power levers:

**Synthesis power optimization** — edit the project `.qsf`:

```text
set_global_assignment -name OPTIMIZATION_MODE "AGGRESSIVE POWER"
```

**PowerPlay Power Analyzer** — `quartus_pow` generates a `.pow.rpt` with static
and dynamic power estimates. It requires a compiled design and optionally a `.vcd`
or `.saif` switching-activity file for accurate dynamic power.

Run from the terminal:

```text
quartus-workflow power            # run quartus_pow + print total/dynamic/static summary
quartus-workflow power --open-gui # also open the PowerPlay Power Analyzer GUI
```

Or open from the Quartus IDE: **Processing → Power Analyzer**.

---

## 10. Nios V Software Workflow

> **Note:** The CLI-based workflow (`gen-bsp` through `console-load`) has been
> tested against physical hardware. The Ashling RiscFree IDE (`open-riscfree`)
> and Eclipse-based debug workflow have not been validated.

### 10.1 Prerequisites

- `sopcinfo` path set in `hw_workflow.toml [files]`
- **Generate HDL** run in Platform Designer (`quartus-workflow open-pd`) — produces `.sopcinfo`
- Nios V tools installed (part of Quartus Prime 25.x): `niosv/bin/niosv-bsp.exe`, `niosv-app.exe`
- Ashling RiscFree IDE installed: `C:\altera_lite\25.1std\riscfree\` — provides cmake and RISC-V toolchain used by `build-app`
- A C source file for the application; SDK samples are at `C:\altera_lite\25.1std\niosv\examples\software\`

### 10.2 End-to-End Workflow

```text
quartus-workflow build          # compile FPGA bitstream
quartus-workflow program        # flash .sof to FPGA via USB Blaster

quartus-workflow gen-bsp        # generate BSP from .sopcinfo (run after Generate HDL)
quartus-workflow gen-app --srcs <path/to/main.c>   # generate app CMakeLists.txt
quartus-workflow build-app      # cmake configure + build → app.elf + app.bin
quartus-workflow console-load   # load app.bin into on-chip memory via JTAG
# Apply physical CPU reset to start program execution
```

To update the BSP after hardware changes:

```text
quartus-workflow build          # recompile after HDL changes
quartus-workflow gen-bsp        # update BSP memory map and drivers
quartus-workflow build-app      # rebuild application
quartus-workflow program        # reflash FPGA
quartus-workflow console-load   # reload application
```

### 10.3 OCM Size Constraint and Toolchain Notes

The MAX10 on-chip memory (OCM) on the DE10-Lite is limited to **64 KB**. The full HAL
with interrupt-driven drivers and `printf` typically exceeds this. To fit within 64 KB:

- Enable reduced device drivers in the BSP (`hal.enable_reduced_device_drivers = true`
  via BSP Editor or `quartus-workflow open-bsp --settings`)
- Avoid `printf` — use direct MMIO writes to the JTAG UART instead, or `alt_printf`
- Disable C++ support in the BSP if not needed

The Nios V/c core (compact variant) does not have an interrupt input; all peripherals
must use polled drivers.

After `quartus-workflow console-load` completes, a physical CPU reset is required to
begin execution. JTAG-initiated CPU reset is not supported in this configuration.

---

## Appendix A — Quartus CLI Tool Reference

All executables are in `<quartus_rootdir>/quartus/bin64/` unless noted otherwise.
These are the tools invoked internally by `hw_workflow.py`; they can also be called
directly from a terminal for one-off operations.

| Executable           | Location              | Purpose                                                              |
| -------------------- | --------------------- | -------------------------------------------------------------------- |
| `quartus_map`        | `bin64/`              | Analysis & Synthesis; add `--analysis_and_elaboration` for elab-only |
| `quartus_fit`        | `bin64/`              | Fitter — place & route                                               |
| `quartus_asm`        | `bin64/`              | Assembler — generates `.sof`, `.pof`                                 |
| `quartus_sta`        | `bin64/`              | TimeQuest Timing Analyzer                                            |
| `quartus_pow`        | `bin64/`              | PowerPlay Power Analyzer                                             |
| `quartus_pgm`        | `bin64/`              | Programmer — flash `.sof` to FPGA via JTAG                           |
| `quartus_sh`         | `bin64/`              | Shell scripting — Tcl automation, QSF read/write                     |
| `quartus_cpf`        | `bin64/`              | Convert Programming Files — `.sof` → `.jic` for non-volatile flash   |
| `qsys-generate`      | `sopc_builder/bin/`   | Platform Designer — regenerate HDL from `.qsys` (no GUI)             |
| `qsys-edit`          | `sopc_builder/bin/`   | Platform Designer GUI                                                |
| `system-console`     | `sopc_builder/bin/`   | JTAG system access via Tcl scripts                                   |
| `nios2-terminal`     | `nios2eds/bin/`       | Terminal for Nios V / Nios II JTAG UART                              |
| `niosv-bsp`          | `niosv/bin/`          | Nios V BSP generator                                                 |
| `niosv-app`          | `niosv/bin/`          | Nios V application CMakeLists.txt generator                          |
| `niosv-bsp-editor`   | `niosv/bin/`          | Nios V BSP Editor GUI                                                |

---

## Appendix B — Design Decisions

This appendix records the reasoning behind key design choices in the module.
It is intended to help contributors and users understand *why* the tool works
the way it does, not just *what* it does.

### Platform Designer is opt-in (`--pd`), not generated by default

Not every project needs Platform Designer. Creating a `.qsys` stub and a
`QIP_FILE` reference unconditionally causes a confusing "file not found" warning
in Quartus for projects that never use PD. The `--pd` flag on `setup` adds PD
support explicitly; it can be added retroactively to an existing project.

### PD system named `{name}.qsys`, top entity named `{name}_top`

The Platform Designer system file and the top-level HDL entity cannot share
a name — Quartus would see two compilation units with the same identifier and
fail. The convention `foo.qsys` + `foo_top.vhd` avoids the collision while
keeping the relationship obvious.

### `setup` is idempotent — existing files are skipped, not overwritten

Re-running `setup` on an existing project only creates missing files; existing
files are printed as `[skip]`. This makes it safe to re-run after adding `--pd`,
changing `--lang`, or recovering a partial setup. The `hw_workflow.toml`
`[project]` and `[files]` sections are always updated to reflect the current
project name.

### `quartus_workspace/` is fully gitignored

The entire `quartus_workspace/` directory is excluded from version control.
It contains user-specific project files that are not part of the workflow module
itself. Board support assets (pin assignments, templates, presets) live in `lib/`
instead, which is tracked.

### DE10-Lite board support and board-agnostic commands

The core commands (`build`, `program`, `timing`, `report`, `clean`, `gen-pd`,
`simulate`, `console-*`, `gen-bsp`, `gen-app`, `build-app`) work with any
Quartus project and any board. The DE10-Lite-specific features activate when
`board = "de10-lite"` is set in `hw_workflow.toml`:

- `setup --pins` / `apply-pins` — applies DE10-Lite pin assignments from
  `lib/board/de10_lite/assignments/`
- `setup` top-level template — uses board-correct port names (`MAX10_CLK1_50`)
  from `lib/board/de10_lite/templates/`
- `setup --sdc` — 50 MHz clock constraint matching the DE10-Lite oscillator
- Platform Designer presets and system templates in `lib/board/de10_lite/`

The generic HDL assets in `lib/packages/` (`sync_pkg`, `math_pkg`) and
`lib/templates/` (`sync_fifo`, `valid_ready`, `watchdog`) are board-agnostic
and can be used in any project. Adding support for a new board requires only
adding a directory under `lib/board/<board>/` — no changes to `hw_workflow.py`.

The default device string `10M50DAF484C7G` is surfaced in `hw_workflow.toml`
as `device` so it is visible and overridable.

### Core support and Nios V software commands

The `build`, `program`, `simulate`, and GUI launch commands work with any Quartus
project regardless of which soft core (or no soft core) is used. The dedicated
software development commands (`gen-bsp`, `gen-app`, `build-app`, `console-load`)
are additional features that unlock when the project uses a **Nios V** soft core
and Quartus Prime 25.x.

For systems with an open-source RISC-V soft core (e.g. VexRiscv, neorv32),
`quartus_workflow` handles the FPGA side (build, program) while the companion
`riscv_de10_workflow` repository handles HAL generation, firmware compilation,
and loading — see section 1.3 for integration patterns.

### `lib/` name for board support assets

The name `lib/` follows the most common convention in HDL and embedded projects
for shared, reusable assets. Alternatives considered (`board/`, `reusables/`,
`de10_lite/`) were either too narrow or non-standard.

### `board` key gates top template selection and `--pins`

`board = "de10-lite"` in the `[tools]` section of `hw_workflow.toml` is used to
locate the pin assignment QSF and the correct top-level HDL template under
`lib/board/<board>/`. Adding support for a new board requires only adding a
directory — no code changes are needed in `hw_workflow.py`.

### Board-specific templates preferred over a generic skeleton

The generic inline skeleton used `CLOCK_50` as the 50 MHz clock port name. On
the DE10-Lite the correct name is `MAX10_CLK1_50` (pin P11). Using the wrong
name causes a "no pin assignment" warning in Quartus for every project. The
board template in `lib/board/de10_lite/templates/` uses the correct port names,
so a project built with `--pins` compiles cleanly without manual correction.

### Platform Designer system templates live under `lib/board/de10_lite/`

`.qsys` files are board-specific — they encode the clock frequency, SDRAM
controller timing, and pin constraints that are meaningless on a different board.
Storing them under `lib/board/de10_lite/templates/` makes the board dependency
explicit and keeps the generic `lib/templates/` directory for board-agnostic HDL.

### `open-*` commands scoped to the most-used tools

Dedicated `open-*` subcommands exist for the tools used most often in a typical
FPGA workflow: Quartus IDE, Platform Designer, Programmer, TimeQuest, BSP Editor,
and RiscFree. Less-frequently used tools (Signal Tap, Power Analyzer, Design Space
Explorer) are accessible from within the Quartus IDE. New `open-*` commands are
added when a tool is actively used in the workflow — not speculatively — to avoid
feature bloat.
