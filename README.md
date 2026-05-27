# Quartus HW Workflow

Write HDL in **any editor**, drive Quartus from the terminal — a `hw_workflow.py`-based
Intel FPGA development environment, developed and tested on the DE10-Lite (MAX10).
Build, simulate, program, and develop Nios V software from a single Windows-native script.

> Runs natively on **Windows** (PowerShell or CMD).

---

> **Note:** This module pairs with
> [riscv_de10_workflow](https://github.com/Nord4n/riscv_de10_workflow) — a companion
> repository for open-source RISC-V soft-core development on the DE10-Lite. It can serve as a
> drop-in replacement for the `HW/` directory in that workflow; the `.sopcinfo` and
> `.sof` outputs land at the paths it already expects.

## What it does

The goal is an editor-agnostic workflow: write HDL in **VSCode** (or any editor) with
full extension support, automate the build pipeline from the terminal, and open Quartus
GUIs on demand when needed.

- **Single-command build** — `quartus-workflow build` runs the full Quartus compilation
  pipeline (synthesis → fit → assemble → timing) and prints an Fmax and resource summary.
- **FPGA programming** — `quartus-workflow program` flashes `.sof` via the onboard USB Blaster.
- **Nios V software** — generate BSP, build application, and load binary to on-chip memory
  over JTAG with `gen-bsp` / `build-app` / `console-load`.
- **HDL simulation** — run VUnit testbenches with GHDL or Questa FSE.
- **GUI when you need it** — open Platform Designer, Programmer, TimeQuest, or the
  full Quartus IDE from the terminal when the CLI isn't enough.

---

## Usage

Configure once in `hw_workflow.toml` (Quartus version, project paths, simulator), then:

```powershell
quartus-workflow build          # synthesise, fit, assemble, run timing
quartus-workflow program        # flash .sof to FPGA via USB Blaster
quartus-workflow simulate       # run VUnit testbenches
```

Nios V software loop:

```powershell
quartus-workflow gen-bsp        # generate HAL BSP from .sopcinfo (once per HW change)
quartus-workflow gen-app --srcs path\to\main.c
quartus-workflow build-app      # cmake + make → app.elf + app.bin
quartus-workflow console-load   # load app.bin into on-chip memory via JTAG
```

> **Note:** The CLI-based Nios V workflow above has been tested against physical
> hardware. The Ashling RiscFree IDE (`open-riscfree`) and Eclipse-based debug
> workflow have not been validated.

---

## Getting Started

### Hardware

- Any Intel/Altera FPGA board with Quartus Prime support + USB cable (USB Blaster)
- Developed and tested on the **DE10-Lite** (MAX10) — DE10-Lite board files and example project included

### Software

| Tool | Required for |
| ---- | ------------ |
| Python 3.11+ | All commands |
| Quartus Prime Lite 25.1 | All commands |
| GHDL or Questa FSE | `simulate` |
| Ashling RiscFree (bundled with Quartus 25.x) | Nios V software commands |

### One-time setup

```powershell
.\setup_env.ps1                 # adds quartus-workflow and Quartus bin64 to user PATH
# Edit hw_workflow.toml — set quartus_version, qpf, qsys, sof paths
```

`setup_env.ps1` appends paths to the user environment permanently.
`quartus-workflow <command>` is available from any directory afterwards.
`python hw_workflow.py <command>` also works from the repo root without setup.

See [doc/hw_toolchain_setup.md](doc/hw_toolchain_setup.md) for Quartus installation,
RiscFree setup, and a step-by-step Nios V software workflow.

---

## Commands

| Command | What it does |
| ------- | ------------ |
| `build` | Full compilation: synthesis → fit → assemble → timing |
| `synth` | Analysis & Synthesis only |
| `elab` | Analysis & Elaboration — fast HDL syntax check |
| `timing` | Run TimeQuest standalone |
| `power` | Run Power Analyzer (quartus_pow) and print power summary |
| `program` | Flash `.sof` to FPGA via USB Blaster |
| `simulate` | Run VUnit testbenches (GHDL or Questa FSE) |
| `report` | Print Fmax and resource utilisation from existing reports |
| `gen-pd` | Regenerate Platform Designer HDL from `.qsys` |
| `clean` | Remove compilation outputs |
| `setup` | Create a new Quartus project from template |
| `apply-pins` | Apply DE10-Lite pin assignments to `.qsf` |
| `gen-bsp` | Generate or update Nios V HAL BSP from `.sopcinfo` |
| `gen-app` | Generate `CMakeLists.txt` for a Nios V application |
| `build-app` | Compile Nios V app to `.elf` / `.bin` (RiscFree toolchain) |
| `console-scan` | Scan JTAG chain via system-console |
| `console-peek <addr>` | Read 32-bit word via JTAG Avalon Master |
| `console-poke <addr> <val>` | Write 32-bit word via JTAG Avalon Master |
| `console-load [bin] [baseaddr]` | Load `.bin` into memory; auto-detects path and OCM base |
| `open-pd` | Open Platform Designer GUI |
| `open-quartus` | Open Quartus Prime IDE |
| `open-programmer` | Open Programmer GUI |
| `open-timing` | Open TimeQuest Timing Analyzer GUI |
| `open-bsp` | Open Nios V BSP Editor GUI |
| `open-niosv-shell` | Open Nios V Command Shell (toolchain environment) |
| `open-riscfree` | Open Ashling RiscFree IDE |

```powershell
quartus-workflow <command> --help   # options for any command
```

---

## Documentation

| Document | Contents |
| -------- | -------- |
| [doc/hw_workflow.md](doc/hw_workflow.md) | Full reference — all commands, configuration, timing closure, Nios V workflow, design decisions |
| [doc/hw_toolchain_setup.md](doc/hw_toolchain_setup.md) | Toolchain installation and Nios V software setup guide |
