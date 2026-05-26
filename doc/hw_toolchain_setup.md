# HW Module — Toolchain Setup Guide

This guide covers all prerequisites for using `hw_workflow.py` on the DE10-Lite.

**Confirmed working:** Quartus Prime Lite 25.1, Python 3.11, Windows 10/11.

---

## Contents

- [1. Python](#1-python)
- [2. Quartus Prime Lite](#2-quartus-prime-lite)
- [3. USB Blaster Driver](#3-usb-blaster-driver)
- [4. GHDL (simulation — optional)](#4-ghdl-simulation--optional)
- [5. Questa FSE (simulation — optional)](#5-questa-fse-simulation--optional)
- [6. VUnit](#6-vunit)
- [7. Configure hw_workflow.toml](#7-configure-hw_workflowtoml)
- [8. Verify installation](#8-verify-installation)
- [9. Nios V Software Development (optional)](#9-nios-v-software-development-optional)

---

## 1. Python

`hw_workflow.py` requires **Python 3.11+** (for `tomllib` stdlib support).

**Install on Windows:**

1. Download from [python.org/downloads](https://www.python.org/downloads/)
2. Run installer — check **"Add Python to PATH"**
3. Verify:

```powershell
python --version
# Python 3.11.x or higher
```

Python 3.8 and later is supported via the `tomli` backport, but **Python 3.8
reached end of life in October 2024** and is not recommended for new setups.
Upgrade to 3.11+ when possible. If you cannot upgrade immediately:

```powershell
pip install tomli
```

> `setup_env.ps1` will warn with `[WARN]` if it detects Python older than 3.11.

---

## 2. Quartus Prime Lite

Quartus Prime Lite is required for synthesis, programming, and GUI tools.
Confirmed working: **Quartus Prime Lite 25.1**.

**Install:**

1. Download from [Intel FPGA Software Download Center](https://www.intel.com/content/www/us/en/collections/products/fpga/software/downloads.html)
2. Run the installer. Default installation paths:
   - Quartus 18.1: `C:\intelFPGA_lite\18.1\`
   - Quartus 25.1: `C:\altera_lite\25.1std\`
3. During installation, include:
   - **Quartus Prime** (required)
   - **MAX 10 device support** (required for DE10-Lite)
   - **Questa FSE** (optional, for simulation — included in 25.1)

`hw_workflow.py` searches the default installation paths automatically based on
`quartus_version` in `hw_workflow.toml`. No manual PATH setup is required.

---

## 3. USB Blaster Driver

The DE10-Lite uses an onboard **USB Blaster** for JTAG programming and
system-console access. The driver is included with Quartus but may require
manual installation on first use.

**Install / verify:**

1. Connect the DE10-Lite to your PC via USB.
2. Open **Device Manager** — look for "USB Blaster" under *Universal Serial Bus controllers*
   or *Other devices*.
3. If it appears as an unknown device, right-click → **Update Driver** →
   **Browse my computer** → navigate to:

   ```text
   C:\altera_lite\25.1std\quartus\drivers\usb-blaster\
   ```

4. After installation, the device should appear as **"USB-Blaster"**.

**Verify from Quartus:**

Open Quartus → **Tools → Programmer** → click **Hardware Setup** →
the USB-Blaster should appear in the hardware list.

---

## 4. GHDL (simulation — optional)

GHDL is an open-source VHDL simulator used for VUnit simulation.

### WSL (Ubuntu 22.04) — recommended

```bash
sudo apt update && sudo apt install ghdl
ghdl --version
```

### Windows native binary

Download from [github.com/ghdl/ghdl/releases](https://github.com/ghdl/ghdl/releases).
Extract to a directory and add it to PATH.

> **Note:** VUnit simulation with GHDL works from WSL (`VUNIT_SIMULATOR=ghdl python3 HW/sim/run.py`).
> Running GHDL from Windows PowerShell requires the Windows native binary.

---

## 5. Questa FSE (simulation — optional)

Questa FSE is Intel's bundled simulator included with **Quartus 25.1 Lite**.

After installing Quartus 25.1, Questa FSE is available at:

```text
C:\altera_lite\25.1std\questa_fse\win64\
```

**Add to PATH (PowerShell):**

```powershell
$env:PATH = "C:\altera_lite\25.1std\questa_fse\win64;" + $env:PATH
```

For persistent setup, add this to your PowerShell profile (`$PROFILE`).

> Questa FSE does **not** work from WSL — use Windows PowerShell for Questa-based simulation.

---

## 6. VUnit

VUnit is the HDL unit test framework used by `HW/sim/run.py`.

```powershell
pip install vunit-hdl
```

Verify:

```powershell
python -c "import vunit; print(vunit.__version__)"
```

---

## 7. Configure hw_workflow.toml

Edit `hw_workflow.toml` to match your Quartus project:

```toml
[tools]
quartus_version = "25.1"
# Uncomment and set if tool auto-detection fails:
# quartus_base = "C:/altera_lite/25.1std/quartus/bin64"

[files]
qpf  = "quartus_workspace/my_system/my_system.qpf"
qsys = "quartus_workspace/my_system/my_system.qsys"
sof  = "quartus_workspace/my_system/output_files/my_system.sof"
```

All paths in `[files]` are relative to the repo root.

---

## 8. Verify Installation

### One-time PATH setup

Run `setup_env.ps1` from the repo root to add `bin\` and any found
Quartus tools to your user PATH:

```powershell
powershell -ExecutionPolicy Bypass -File setup_env.ps1
```

Open a new terminal (or `$env:PATH` refresh) for the changes to take effect.

### Verify

After setup, `quartus-workflow` is available from any directory:

```powershell
# List all commands
quartus-workflow --help

# Open Quartus Programmer GUI (tests Quartus tool discovery)
quartus-workflow open-programmer

# Open Platform Designer (tests qsys-edit discovery)
quartus-workflow open-pd

# Run VUnit simulation
#   GHDL (Questa FSE also works — set simulator = "modelsim" in hw_workflow.toml)
quartus-workflow simulate
```

Without PATH setup, invoke directly from `HW\`:

```powershell
python hw_workflow.py --help
```

---

## 9. Nios V Software Development (optional)

Required for building Nios V firmware with `gen-bsp`, `gen-app`, and `build-app`.
All tools are bundled with **Quartus Prime Lite 25.x** — no separate installation needed.

### Nios V command-line tools

Located in `C:\altera_lite\25.1std\niosv\bin\`:

| Tool | Purpose |
| ------------------- | -------------------------------------------------- |
| `niosv-bsp` | Create or update a Board Support Package (BSP) |
| `niosv-bsp-editor` | BSP Editor GUI — configure BSP settings graphically |
| `niosv-app` | Generate application `CMakeLists.txt` from an existing BSP |
| `niosv-download` | Download a `.elf` file to the Nios V processor via JTAG |

Run `setup_env.ps1` to add `niosv\bin` to your user PATH automatically.

### cmake and RISC-V toolchain

`build-app` uses the cmake and RISC-V GCC toolchain bundled with RiscFree:

| Component | Path |
| ----------- | ---- |
| cmake | `C:\altera_lite\25.1std\riscfree\build_tools\cmake\bin\cmake.exe` |
| make | `C:\altera_lite\25.1std\riscfree\build_tools\bin\make.exe` |
| RISC-V GCC | `C:\altera_lite\25.1std\riscfree\toolchain\riscv32-unknown-elf\bin\` |

`build-app` adds these to PATH automatically — no manual setup required.

### Ashling RiscFree IDE

Located at `C:\altera_lite\25.1std\riscfree\RiscFree\RiscFree.exe`.

No additional installation is required. Launch with:

```powershell
quartus-workflow open-riscfree [--workspace PATH]
```

### hw_workflow.toml — Nios V fields

Add to `hw_workflow.toml` for a Nios V project:

```toml
[files]
sopcinfo = "quartus_workspace/niosv_system/niosv_system.sopcinfo"
# bsp_dir  = "software/hal_bsp"   # default: <sopcinfo-dir>/software/<type>_bsp
# app_dir  = "software/app"       # default: <sopcinfo-dir>/software/app

[tools]
# niosv_base = "C:/altera_lite/25.1std/niosv/bin"  # optional: override niosv tool search
# riscfree   = "C:/altera_lite/25.1std/riscfree/RiscFree/RiscFree.exe"  # optional
```

### Typical Nios V firmware workflow

```powershell
# 1. Build hardware and program board
quartus-workflow build
quartus-workflow program

# 2. Generate BSP from .sopcinfo
#    Requires: files.sopcinfo set in hw_workflow.toml
#              Platform Designer → Generate HDL run first (produces .sopcinfo)
quartus-workflow gen-bsp

# 3. Optional: inspect and adjust BSP settings in BSP Editor
quartus-workflow open-bsp --settings

# 4. Generate application project
#    SDK samples: C:\altera_lite\25.1std\niosv\examples\software\
quartus-workflow gen-app --srcs <path/to/main.c>

# 5. Build application → app.elf + app.bin
quartus-workflow build-app

# 6. Load application into on-chip memory via JTAG
quartus-workflow console-load

# 7. Apply physical CPU reset to start execution
```

To update after hardware or BSP changes:

```powershell
quartus-workflow build && quartus-workflow gen-bsp && quartus-workflow build-app
quartus-workflow program && quartus-workflow console-load
```

> **Note:** The `.sopcinfo` file is generated by Platform Designer when you run
> **Generate HDL** (Generation tab → Generate). It is placed in the same directory
> as the `.qsys` file.
>
> **DE10-Lite OCM limit:** The MAX10 on-chip memory is limited to 64 KB. Enable
> `hal.enable_reduced_device_drivers` in the BSP and avoid `printf` to fit within
> this constraint. The Nios V/c core does not support interrupts — all peripherals
> must use polled drivers.
