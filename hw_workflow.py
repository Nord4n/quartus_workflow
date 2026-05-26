#!/usr/bin/env python3
"""
hw_workflow.py — Quartus workflow CLI for Intel DE10-Lite (MAX 10) FPGA projects.

Reads hw_workflow.toml from the repository root for tool paths, board settings,
and active project configuration.

  python3 hw_workflow.py --help

Project scaffold:
  python3 hw_workflow.py setup <name>               # Scaffold .qpf + .qsf + top HDL
  python3 hw_workflow.py setup <name> --pd          # Also add Platform Designer system
  python3 hw_workflow.py setup <name> --pins        # Also apply board pin assignments
  python3 hw_workflow.py setup <name> --sdc         # Also generate SDC constraints file
  python3 hw_workflow.py set-project <name>         # Switch active project in toml
  python3 hw_workflow.py set-top <entity>           # Set TOP_LEVEL_ENTITY in .qsf

Assignments:
  python3 hw_workflow.py apply-pins      # Append board pin assignments to .qsf
  python3 hw_workflow.py sync-top        # Sync component declaration from PD _inst.vhd

Platform Designer:
  python3 hw_workflow.py gen-pd          # Regenerate Platform Designer HDL from .qsys

Build and program:
  python3 hw_workflow.py elab            # HDL elaboration check (fast)
  python3 hw_workflow.py synth           # Analysis & Synthesis only (quartus_map)
  python3 hw_workflow.py build           # Full compilation (map->fit->asm->sta) + summary
  python3 hw_workflow.py report          # Print resource + Fmax summary from existing .rpt files
  python3 hw_workflow.py timing          # Run TimeQuest Timing Analyzer + print Fmax
  python3 hw_workflow.py timing --open-gui  # Also open TimeQuest GUI after analysis
  python3 hw_workflow.py power           # Run Power Analyzer + print power summary
  python3 hw_workflow.py power --open-gui   # Also open Power Analyzer GUI after analysis
  python3 hw_workflow.py program         # Flash .sof to FPGA via USB Blaster (JTAG)
  python3 hw_workflow.py clean           # Delete compilation outputs (output_files/, db/)
  python3 hw_workflow.py clean --keep-sof  # Keep .sof when cleaning
  python3 hw_workflow.py clean --dry-run   # List files to be deleted without deleting

Simulation:
  python3 hw_workflow.py simulate        # Run VUnit tests (sim/run.py)

Nios V software:
  python3 hw_workflow.py gen-bsp         # Generate or update HAL BSP from .sopcinfo
  python3 hw_workflow.py gen-app --srcs path/to/main.c  # Generate CMakeLists.txt
  python3 hw_workflow.py build-app       # cmake + make → app.elf + app.bin
  python3 hw_workflow.py console-scan    # Scan JTAG chain for Avalon masters
  python3 hw_workflow.py console-peek <addr>       # Read 32-bit word via JTAG
  python3 hw_workflow.py console-poke <addr> <val> # Write 32-bit word via JTAG
  python3 hw_workflow.py console-load    # Load app.bin into on-chip memory via JTAG

GUI tools:
  python3 hw_workflow.py open-quartus    # Open Quartus Prime IDE
  python3 hw_workflow.py open-pd         # Open Platform Designer GUI
  python3 hw_workflow.py open-programmer # Open Programmer GUI
  python3 hw_workflow.py open-timing     # Open TimeQuest Timing Analyzer GUI
  python3 hw_workflow.py open-bsp          # Open Nios V BSP Editor GUI
  python3 hw_workflow.py open-niosv-shell  # Open Nios V Command Shell
  python3 hw_workflow.py open-riscfree     # Open Ashling RiscFree IDE
"""

import argparse
import glob
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap

# Add HW/scripts/ to path for standalone lib imports
_HW_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HW_DIR, "scripts"))

from lib.hw_config     import load_config
from lib.quartus_tools import (
    _find_tool, _find_bin64_tool, _quartus_default_dirs, _quartus_sopc_dirs,
    _to_win_path, find_quartus_pgm, find_system_console,
    find_niosv_bsp, find_niosv_app, find_niosv_bsp_editor, find_niosv_shell, find_riscfree,
    find_cmake, find_make, find_objcopy,
)


# ---------------------------------------------------------------------------
# Tool finders
# ---------------------------------------------------------------------------

def find_quartus_sh(config):
    """Find quartus_sh (headless compile/scripting shell)."""
    override = config["tools"].get("quartus_base", "")
    version  = config["tools"].get("quartus_version", "25.1")
    tool = _find_tool("quartus_sh", override, version,
                      ["quartus_sh", "quartus_sh.exe"])
    if not tool:
        _error("quartus_sh not found!")
        print("Solutions:")
        print("  1. Add Quartus bin64/ to your PATH, or")
        print("  2. Set tools.quartus_base in hw_workflow.toml")
        sys.exit(1)
    print(f"[*] Quartus shell : {tool}")
    return tool


def find_quartus_map(config):
    """Find quartus_map (Analysis & Synthesis tool)."""
    override = config["tools"].get("quartus_base", "")
    version  = config["tools"].get("quartus_version", "25.1")
    tool = _find_tool("quartus_map", override, version,
                      ["quartus_map", "quartus_map.exe"])
    if not tool:
        _error("quartus_map not found!")
        print("Solutions:")
        print("  1. Add Quartus bin64/ to your PATH, or")
        print("  2. Set tools.quartus_base in hw_workflow.toml")
        sys.exit(1)
    print(f"[*] Quartus map   : {tool}")
    return tool


def find_quartus_sta(config):
    """Find quartus_sta (TimeQuest Timing Analyzer CLI)."""
    override = config["tools"].get("quartus_base", "")
    version  = config["tools"].get("quartus_version", "25.1")
    tool = _find_tool("quartus_sta", override, version,
                      ["quartus_sta", "quartus_sta.exe"])
    if not tool:
        _error("quartus_sta not found!")
        print("Solutions:")
        print("  1. Add Quartus bin64/ to your PATH, or")
        print("  2. Set tools.quartus_base in hw_workflow.toml")
        sys.exit(1)
    print(f"[*] Quartus STA   : {tool}")
    return tool


def find_quartus_pow(config):
    """Find quartus_pow (Power Analyzer CLI)."""
    override = config["tools"].get("quartus_base", "")
    version  = config["tools"].get("quartus_version", "25.1")
    tool = _find_tool("quartus_pow", override, version,
                      ["quartus_pow", "quartus_pow.exe"])
    if not tool:
        _error("quartus_pow not found!")
        print("Solutions:")
        print("  1. Add Quartus bin64/ to your PATH, or")
        print("  2. Set tools.quartus_base in hw_workflow.toml")
        sys.exit(1)
    print(f"[*] Quartus Power  : {tool}")
    return tool


def find_qsys_edit(config):
    """Find qsys-edit (Platform Designer GUI) — lives in sopc_builder/bin."""
    override  = config["tools"].get("quartus_base", "")
    version   = config["tools"].get("quartus_version", "25.1")
    exe_names = ["qsys-edit", "qsys-edit.exe"]

    if override:
        for name in exe_names:
            candidate = os.path.join(override, name)
            if os.path.isfile(candidate):
                print(f"[*] Quartus PD    : {candidate}")
                return candidate

    for name in exe_names:
        found = shutil.which(name)
        if found:
            print(f"[*] Quartus PD    : {found}")
            return found

    for sopc_dir in _quartus_sopc_dirs(version):
        for name in exe_names:
            candidate = os.path.join(sopc_dir, name)
            if os.path.isfile(candidate):
                print(f"[*] Quartus PD    : {candidate}")
                return candidate

    _error("qsys-edit not found!")
    print("Solutions:")
    print("  1. Add Quartus sopc_builder/bin/ to your PATH, or")
    print("  2. Set tools.quartus_base in hw_workflow.toml")
    sys.exit(1)


def find_qsys_generate(config):
    """Find qsys-generate — lives in sopc_builder/bin, same directory as qsys-edit."""
    override  = config["tools"].get("quartus_base", "")
    version   = config["tools"].get("quartus_version", "25.1")
    exe_names = ["qsys-generate", "qsys-generate.exe"]

    if override:
        for name in exe_names:
            candidate = os.path.join(override, name)
            if os.path.isfile(candidate):
                print(f"[*] qsys-generate  : {candidate}")
                return candidate

    for name in exe_names:
        found = shutil.which(name)
        if found:
            print(f"[*] qsys-generate  : {found}")
            return found

    for sopc_dir in _quartus_sopc_dirs(version):
        for name in exe_names:
            candidate = os.path.join(sopc_dir, name)
            if os.path.isfile(candidate):
                print(f"[*] qsys-generate  : {candidate}")
                return candidate

    _error("qsys-generate not found. Check quartus_version in hw_workflow.toml.")
    print("Solutions:")
    print("  1. Add Quartus sopc_builder/bin/ to your PATH, or")
    print("  2. Set tools.quartus_base in hw_workflow.toml")
    sys.exit(1)


def find_quartus_gui(config):
    """Find quartus (full Quartus Prime IDE)."""
    override = config["tools"].get("quartus_base", "")
    version  = config["tools"].get("quartus_version", "25.1")
    tool = _find_tool("quartus", override, version,
                      ["quartus", "quartus.exe"])
    if not tool:
        _error("quartus IDE not found!")
        print("Solutions:")
        print("  1. Add Quartus bin64/ to your PATH, or")
        print("  2. Set tools.quartus_base in hw_workflow.toml")
        sys.exit(1)
    print(f"[*] Quartus IDE   : {tool}")
    return tool


def find_quartus_staw(config):
    """Find quartus_staw (TimeQuest Timing Analyzer GUI)."""
    override = config["tools"].get("quartus_base", "")
    version  = config["tools"].get("quartus_version", "25.1")
    tool = _find_bin64_tool("quartus_staw",
                            ["quartus_staw", "quartus_staw.exe"],
                            override, version)
    if not tool:
        _error("quartus_staw not found!")
        print("Solutions:")
        print("  1. Add Quartus bin64/ to your PATH, or")
        print("  2. Set tools.quartus_base in hw_workflow.toml")
        sys.exit(1)
    print(f"[*] TimeQuest GUI  : {tool}")
    return tool


def find_quartus_pgmw(config):
    """Find quartus_pgmw (Programmer GUI)."""
    override = config["tools"].get("quartus_base", "")
    version  = config["tools"].get("quartus_version", "25.1")
    tool = _find_bin64_tool("quartus_pgmw",
                            ["quartus_pgmw", "quartus_pgmw.exe"],
                            override, version)
    if not tool:
        _error("quartus_pgmw not found!")
        print("Solutions:")
        print("  1. Add Quartus bin64/ to your PATH, or")
        print("  2. Set tools.quartus_base in hw_workflow.toml")
        sys.exit(1)
    print(f"[*] Quartus Programmer: {tool}")
    return tool


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_open_pd(config, args):
    """Launch Platform Designer (qsys-edit) with the project's .qsys file."""
    qsys = getattr(args, "qsys", None) or config["files"].get("qsys", "")
    qse  = find_qsys_edit(config)
    cmd  = [qse]
    if qsys and os.path.exists(qsys):
        win_qsys = _to_win_path(qsys)
        cmd.append(win_qsys)
        print(f"\nOpening Platform Designer: {win_qsys}")
    elif qsys:
        print(f"\nOpening Platform Designer (new system — {os.path.basename(qsys)} not yet created)")
    else:
        print("\nOpening Platform Designer (no .qsys file configured)")
    subprocess.Popen(cmd)  # non-blocking — GUI app


def cmd_gen_pd(config, args):
    """Regenerate Platform Designer HDL from .qsys file (qsys-generate)."""
    qsys = getattr(args, "qsys", None) or config["files"].get("qsys", "")
    if not qsys:
        _error("No QSYS file specified. Set files.qsys in hw_workflow.toml or pass --qsys")
        sys.exit(1)
    if not os.path.exists(qsys):
        _error(f"QSYS file not found: {qsys}")
        print("Run 'open-pd' to create the Platform Designer system first.")
        sys.exit(1)
    hdl_lang  = config["project"].get("hdl_lang", "vhdl").upper()
    synthesis = "VHDL" if hdl_lang == "VHDL" else "Verilog"
    gen       = find_qsys_generate(config)
    win_qsys  = _to_win_path(qsys)
    print(f"\nRegenerating Platform Designer HDL: {win_qsys}")
    subprocess.run([gen, win_qsys, f"--synthesis={synthesis}"], check=True)
    _success("\n[+] Platform Designer HDL regenerated successfully!\n")


def cmd_open_quartus(config, args):
    """Launch Quartus Prime IDE with the project's .qpf file."""
    qpf  = getattr(args, "qpf", None) or config["files"].get("qpf", "")
    qgui = find_quartus_gui(config)
    cmd  = [qgui]
    if qpf:
        win_qpf = _to_win_path(qpf)
        cmd.append(win_qpf)
        print(f"\nOpening Quartus IDE: {win_qpf}")
    else:
        print("\nOpening Quartus IDE (no .qpf file configured)")
    subprocess.Popen(cmd)  # non-blocking — GUI app


def cmd_open_programmer(config, args):
    """Launch Quartus Programmer GUI."""
    pgmw = find_quartus_pgmw(config)
    print("\nOpening Quartus Programmer")
    subprocess.Popen([pgmw])  # non-blocking — GUI app


def cmd_open_timing(config, args):
    """Launch TimeQuest Timing Analyzer GUI with the project pre-loaded."""
    staw = find_quartus_staw(config)
    qpf  = config["files"].get("qpf", "")
    print("\nOpening TimeQuest Timing Analyzer")
    cmd = [staw]
    if qpf and os.path.exists(qpf):
        cmd.append(_to_win_path(qpf))
    subprocess.Popen(cmd)  # non-blocking — GUI app



def cmd_program(config, args):
    """Flash .sof to FPGA via quartus_pgm (JTAG mode)."""
    sof = getattr(args, "sof", None) or config["files"].get("sof", "")
    if not sof:
        _error("No SOF file specified. Set files.sof in hw_workflow.toml or pass --sof")
        sys.exit(1)
    if not os.path.exists(sof):
        _error(f"SOF file not found: {sof}")
        print("Run 'build' first, or update files.sof in hw_workflow.toml")
        sys.exit(1)
    pgm     = find_quartus_pgm(config)
    win_sof = _to_win_path(sof)
    print(f"\nProgramming FPGA: {win_sof}")
    subprocess.run([pgm, "-m", "jtag", "-o", f"p;{win_sof}"], check=True)
    _success("\n[+] FPGA programmed successfully!\n")


def cmd_simulate(config, args):
    """Run VUnit simulation via sim/run.py."""
    run_py    = os.path.join(_HW_DIR, "sim", "run.py")
    simulator = (getattr(args, "simulator", None)
                 or config["tools"].get("simulator", "ghdl"))
    extra     = getattr(args, "extra", [])

    if not os.path.exists(run_py):
        _error(f"sim/run.py not found at {run_py}")
        sys.exit(1)

    env                   = os.environ.copy()
    env["VUNIT_SIMULATOR"] = simulator
    sim_dir               = os.path.dirname(run_py)   # HW/sim/ — vunit_out lands here
    print(f"\nSimulating with {simulator.upper()}...")
    subprocess.run([sys.executable, run_py] + extra, env=env, cwd=sim_dir, check=True)


def cmd_build(config, args):
    """Full Quartus compilation: map -> fit -> asm -> sta, then print summary."""
    qpf = getattr(args, "qpf", None) or config["files"].get("qpf", "")
    if not qpf:
        _error("No QPF file specified. Set files.qpf in hw_workflow.toml or pass --qpf")
        sys.exit(1)
    if not os.path.exists(qpf):
        _error(f"QPF file not found: {qpf}")
        print("Update files.qpf in hw_workflow.toml or pass --qpf <path>")
        sys.exit(1)
    qsh     = find_quartus_sh(config)
    win_qpf = _to_win_path(qpf)
    print(f"\nBuilding: {win_qpf}")
    subprocess.run([qsh, "--flow", "compile", win_qpf], check=True)
    _success("\n[+] Build complete!")
    _print_build_summary(qpf)


def cmd_timing(config, args):
    """Run TimeQuest Timing Analyzer standalone and print Fmax summary."""
    qpf = getattr(args, "qpf", None) or config["files"].get("qpf", "")
    if not qpf:
        _error("No QPF file specified. Set files.qpf in hw_workflow.toml or pass --qpf")
        sys.exit(1)
    if not os.path.exists(qpf):
        _error(f"QPF file not found: {qpf}")
        print("Run 'build' first to generate the timing database.")
        sys.exit(1)
    sta     = find_quartus_sta(config)
    win_qpf = _to_win_path(qpf)
    print(f"\nRunning timing analysis: {win_qpf}")
    subprocess.run([sta, win_qpf], check=True)
    _success("\n[+] Timing analysis complete!")
    _print_build_summary(qpf)

    # Point user to the full timing report
    project_dir  = os.path.dirname(os.path.abspath(qpf))
    project_name = os.path.splitext(os.path.basename(qpf))[0]
    sta_rpt = os.path.join(project_dir, "output_files", f"{project_name}.sta.rpt")
    if os.path.exists(sta_rpt):
        print(f"  Timing report    : {sta_rpt}")

    # Open TimeQuest GUI if requested
    if getattr(args, "open_gui", False):
        staw = find_quartus_staw(config)
        print("\n[*] Opening TimeQuest Timing Analyzer...")
        cmd = [staw]
        if os.path.exists(qpf):
            cmd.append(_to_win_path(qpf))
        subprocess.Popen(cmd)


def cmd_power(config, args):
    """Run Power Analyzer (quartus_pow) and print power summary."""
    qpf = getattr(args, "qpf", None) or config["files"].get("qpf", "")
    if not qpf:
        _error("No QPF file specified. Set files.qpf in hw_workflow.toml or pass --qpf")
        sys.exit(1)
    if not os.path.exists(qpf):
        _error(f"QPF file not found: {qpf}")
        print("Run 'build' first to generate the fit database.")
        sys.exit(1)
    pow_tool = find_quartus_pow(config)
    win_qpf  = _to_win_path(qpf)
    print(f"\nRunning power analysis: {win_qpf}")
    subprocess.run([pow_tool, win_qpf], check=True)
    _success("\n[+] Power analysis complete!")
    _print_power_summary(qpf)

    if getattr(args, "open_gui", False):
        cmd_open_quartus(config, args)


def cmd_report(config, args):
    """Print build summary (resources + Fmax) from existing .rpt files."""
    qpf = getattr(args, "qpf", None) or config["files"].get("qpf", "")
    if not qpf:
        _error("No QPF file specified. Set files.qpf in hw_workflow.toml or pass --qpf")
        sys.exit(1)
    project_dir  = os.path.dirname(os.path.abspath(qpf))
    project_name = os.path.splitext(os.path.basename(qpf))[0]
    fit_rpt = os.path.join(project_dir, "output_files", f"{project_name}.fit.rpt")
    if not os.path.exists(fit_rpt):
        _error("No build reports found. Run 'build' first.")
        sys.exit(1)
    _print_build_summary(qpf)


def cmd_synth(config, args):
    """Run Analysis & Synthesis only via quartus_map."""
    qpf = getattr(args, "qpf", None) or config["files"].get("qpf", "")
    if not qpf:
        _error("No QPF file specified. Set files.qpf in hw_workflow.toml or pass --qpf")
        sys.exit(1)
    if not os.path.exists(qpf):
        _error(f"QPF file not found: {qpf}")
        print("Update files.qpf in hw_workflow.toml or pass --qpf <path>")
        sys.exit(1)
    qmap    = find_quartus_map(config)
    win_qpf = _to_win_path(qpf)
    print(f"\nSynthesising: {win_qpf}")
    subprocess.run([qmap, win_qpf], check=True)
    _success("\n[+] Synthesis complete!\n")


def cmd_elab(config, args):
    """Check HDL for errors via quartus_map --analysis_and_elaboration (no full synthesis)."""
    qpf = getattr(args, "qpf", None) or config["files"].get("qpf", "")
    if not qpf:
        _error("No QPF file specified. Set files.qpf in hw_workflow.toml or pass --qpf")
        sys.exit(1)
    if not os.path.exists(qpf):
        _error(f"QPF file not found: {qpf}")
        print("Update files.qpf in hw_workflow.toml or pass --qpf <path>")
        sys.exit(1)
    qmap    = find_quartus_map(config)
    win_qpf = _to_win_path(qpf)
    print(f"\nElaborating: {win_qpf}")
    subprocess.run([qmap, "--analysis_and_elaboration", win_qpf], check=True)
    _success("\n[+] Elaboration complete!\n")


def _write_skeleton_qpf(path, name, version):
    """Write a minimal Quartus Project File (.qpf). Skips if file already exists."""
    if os.path.exists(path):
        print(f"  [skip] {os.path.basename(path)} already exists")
        return
    content = f"""\
QUARTUS_VERSION = "{version}"
DATE = "00:00:00  January 01, 2026"

# Revisions

PROJECT_REVISION = "{name}"
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [create] {os.path.basename(path)}")


def _write_skeleton_qsf(path, name, hdl_lang, device="10M50DAF484C7G", with_pd=False):
    """Write a Quartus Settings File (.qsf) for DE10-Lite. Skips if file already exists."""
    if os.path.exists(path):
        print(f"  [skip] {os.path.basename(path)} already exists")
        return
    ext       = "vhd" if hdl_lang == "vhdl" else "v"
    file_type = "VHDL_FILE" if hdl_lang == "vhdl" else "VERILOG_FILE"
    qip_line  = f"set_global_assignment -name QIP_FILE {name}/synthesis/{name}.qip\n" if with_pd else ""
    content = f"""\
set_global_assignment -name FAMILY "MAX 10"
set_global_assignment -name DEVICE {device}
set_global_assignment -name TOP_LEVEL_ENTITY {name}_top
set_global_assignment -name ORIGINAL_QUARTUS_VERSION 25.1.0
set_global_assignment -name LAST_QUARTUS_VERSION "25.1.0 Standard Edition"
set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files
set_global_assignment -name MIN_CORE_JUNCTION_TEMP 0
set_global_assignment -name MAX_CORE_JUNCTION_TEMP 85
set_global_assignment -name DEVICE_FILTER_PACKAGE FBGA
set_global_assignment -name DEVICE_FILTER_PIN_COUNT 484
set_global_assignment -name DEVICE_FILTER_SPEED_GRADE 7
set_global_assignment -name ERROR_CHECK_FREQUENCY_DIVISOR 256
set_global_assignment -name {file_type} {name}_top.{ext}
{qip_line}"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [create] {os.path.basename(path)}")


def _ensure_qip_in_qsf(path, name):
    """Ensure QIP_FILE assignment exists in .qsf. Appends the line if missing.

    Called when --pd is given, even if the .qsf was not freshly created, so that
    re-running 'setup --pd' on an existing project always registers the PD system.
    """
    if not os.path.exists(path):
        return  # will be handled by _write_skeleton_qsf
    qip_line = f"set_global_assignment -name QIP_FILE {name}/synthesis/{name}.qip"
    text = open(path, encoding="utf-8").read()
    if qip_line in text:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n{qip_line}\n")
    print(f"  [patch] {os.path.basename(path)} — QIP_FILE added")


def _warn(msg):
    """Print a warning line in magenta when stdout is a TTY, plain otherwise."""
    if sys.stdout.isatty():
        print(f"\033[35m  [warn] {msg}\033[0m")
    else:
        print(f"  [warn] {msg}")


def _error(msg):
    """Print an error line in red when stdout is a TTY, plain otherwise."""
    if sys.stdout.isatty():
        print(f"\033[31mERROR: {msg}\033[0m")
    else:
        print(f"ERROR: {msg}")


def _success(msg):
    """Print a success line in bright green when stdout is a TTY, plain otherwise."""
    if sys.stdout.isatty():
        print(f"\033[1;32m{msg}\033[0m")
    else:
        print(msg)


def _find_inst_file(proj_dir, name, hdl_lang):
    """Return path to PD-generated _inst file, or None if not found."""
    ext  = "vhd" if hdl_lang == "vhdl" else "v"
    path = os.path.join(proj_dir, name, f"{name}_inst.{ext}")
    return path if os.path.exists(path) else None


def _extract_component_block_vhd(inst_text, name):
    """Extract and clean the component block from a PD _inst.vhd file.

    Strips := 'X' defaults, trailing inline '-- word' interface-label comments,
    and normalises tab indentation to 4 spaces.
    """
    pat = (rf"component\s+{re.escape(name)}\s+is\s+port\s*\(.*?\)\s*;"
           rf"\s*end\s+component\s+{re.escape(name)}\s*;")
    m = re.search(pat, inst_text, re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    block = m.group(0)

    cleaned = []
    for line in block.splitlines():
        # Normalise tab indentation (PD uses tabs; top files use 4 spaces)
        n_tabs = len(line) - len(line.lstrip("\t"))
        line   = "    " * n_tabs + line.lstrip("\t")
        # Strip := 'X' default values
        line   = re.sub(r"\s*:=\s*'X'", "", line)
        # Strip trailing -- <single-word> interface-label comments
        line   = re.sub(r"\s*--\s*\w+\s*$", "", line)
        cleaned.append(line)
    return "\n".join(cleaned)


def _replace_component_block_vhd(top_text, name, new_block):
    """Replace the component declaration in top_text. Returns (new_text, changed)."""
    pat = (rf"component\s+{re.escape(name)}\s+is\s+port\s*\(.*?\)\s*;"
           rf"\s*end\s+component\s+{re.escape(name)}\s*;")
    new_text, n = re.subn(pat, new_block, top_text, flags=re.DOTALL | re.IGNORECASE)
    return new_text, n > 0


def _warn_unconnected_ports(top_text, component_block, name):
    """Print a warning for each component port not found in the port map."""
    begin_match   = re.search(r"\bbegin\b", top_text, re.IGNORECASE)
    port_map_text = top_text[begin_match.start():] if begin_match else top_text
    port_names    = re.findall(r"^\s{8}(\w+)\s*:", component_block, re.MULTILINE)
    for port in port_names:
        if port.lower() == "port":
            continue
        if port not in port_map_text:
            _warn(f"port '{port}' not connected in port map — update manually")


def _warn_type_changes_vhd(old_block, new_block):
    """Warn when an existing port's type or width has changed in the new component block."""
    def _parse_ports(block):
        ports = {}
        for m in re.finditer(
            r"^\s+(\w+)\s*:\s*(?:in|out|inout)\s+(.+?)\s*[;)]?\s*$",
            block, re.MULTILINE | re.IGNORECASE
        ):
            ports[m.group(1).lower()] = m.group(2).strip().rstrip(";")
        return ports

    old_ports = _parse_ports(old_block)
    new_ports = _parse_ports(new_block)
    for port_name, new_type in new_ports.items():
        if port_name in old_ports and old_ports[port_name] != new_type:
            _warn(f"port '{port_name}' type changed: "
                  f"{old_ports[port_name]} -> {new_type} — update port map manually")


def _write_skeleton_qsys(path, version, hdl_lang, device="10M50DAF484C7G"):
    """Write a minimal Platform Designer .qsys skeleton (DE10-Lite, 50 MHz clock).

    Uses $${FILENAME} so Platform Designer substitutes the system name automatically.
    Skips writing if the file already exists.
    """
    if os.path.exists(path):
        print(f"  [skip] {os.path.basename(path)} already exists")
        return
    hdl_tag = "VHDL" if hdl_lang == "vhdl" else "VERILOG"
    content = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<system name="${{FILENAME}}">
 <component
   name="${{FILENAME}}"
   displayName="${{FILENAME}}"
   version="1.0"
   description=""
   tags=""
   categories="" />
 <parameter name="bonusData"><![CDATA[bonusData
{{
   element clk_0
   {{
      datum _sortIndex
      {{
         value = "0";
         type = "int";
      }}
   }}
}}
]]></parameter>
 <parameter name="clockCrossingAdapter" value="HANDSHAKE" />
 <parameter name="device" value="{device}" />
 <parameter name="deviceFamily" value="MAX 10" />
 <parameter name="deviceSpeedGrade" value="7" />
 <parameter name="fabricMode" value="QSYS" />
 <parameter name="generateLegacySim" value="false" />
 <parameter name="generationId" value="0" />
 <parameter name="globalResetBus" value="false" />
 <parameter name="hdlLanguage" value="{hdl_tag}" />
 <parameter name="hideFromIPCatalog" value="false" />
 <parameter name="lockedInterfaceDefinition" value="" />
 <parameter name="maxAdditionalLatency" value="1" />
 <parameter name="projectName" value="" />
 <parameter name="sopcBorderPoints" value="false" />
 <parameter name="systemHash" value="0" />
 <parameter name="testBenchDutName" value="" />
 <parameter name="timeStamp" value="0" />
 <parameter name="useTestBenchNamingPattern" value="false" />
 <instanceScript></instanceScript>
 <interface name="clk" internal="clk_0.clk_in" type="clock" dir="end" />
 <interface name="reset" internal="clk_0.clk_in_reset" type="reset" dir="end" />
 <module name="clk_0" kind="clock_source" version="{version}" enabled="1">
  <parameter name="clockFrequency" value="50000000" />
  <parameter name="clockFrequencyKnown" value="true" />
  <parameter name="inputClockFrequency" value="0" />
  <parameter name="resetSynchronousEdges" value="NONE" />
 </module>
 <interconnectRequirement for="$system" name="qsys_mm.clockCrossingAdapter" value="HANDSHAKE" />
 <interconnectRequirement for="$system" name="qsys_mm.enableEccProtection" value="FALSE" />
 <interconnectRequirement for="$system" name="qsys_mm.insertDefaultSlave" value="FALSE" />
 <interconnectRequirement for="$system" name="qsys_mm.maxAdditionalLatency" value="1" />
</system>
"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [create] {os.path.basename(path)}")


def _write_skeleton_top(path, name, hdl_lang, with_pd=False, board=""):
    """Write a top-level HDL file for the project.

    If a board-specific template exists in lib/board/<board>/templates/, it is
    used (with {name} substituted).  Otherwise falls back to the built-in
    generic skeleton.  Skips writing if the file already exists.
    """
    if os.path.exists(path):
        print(f"  [skip] {os.path.basename(path)} already exists")
        return

    # Board-specific template (preferred)
    if board:
        suffix    = "_pd" if with_pd else ""
        ext       = "vhd" if hdl_lang == "vhdl" else "v"
        tmpl_path = os.path.join(_HW_DIR, "lib", "board",
                                 board.replace("-", "_"),
                                 "templates", f"top_template{suffix}.{ext}")
        if os.path.exists(tmpl_path):
            content = open(tmpl_path, encoding="utf-8").read().format(name=name)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  [create] {os.path.basename(path)}")
            return

    # Generic fallback
    if hdl_lang == "vhdl":
        if with_pd:
            content = f"""\
-- {name}_top.vhd  Top-level entity for {name} project (DE10-Lite)
-- Generated by quartus-workflow setup. Edit as needed.

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity {name}_top is
    port (
        CLOCK_50 : in  std_logic;
        KEY      : in  std_logic_vector(1 downto 0);
        SW       : in  std_logic_vector(9 downto 0);
        LEDR     : out std_logic_vector(9 downto 0)
    );
end entity {name}_top;

architecture rtl of {name}_top is

    component {name} is
        port (
            clk_clk       : in std_logic;
            reset_reset_n : in std_logic
        );
    end component {name};

begin

    u0 : {name}
        port map (
            clk_clk       => CLOCK_50,
            reset_reset_n => KEY(0)
        );

end architecture rtl;
"""
        else:
            content = f"""\
-- {name}_top.vhd  Top-level entity for {name} project (DE10-Lite)
-- Generated by quartus-workflow setup. Edit as needed.

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity {name}_top is
    port (
        CLOCK_50 : in  std_logic;
        KEY      : in  std_logic_vector(1 downto 0);
        SW       : in  std_logic_vector(9 downto 0);
        LEDR     : out std_logic_vector(9 downto 0)
    );
end entity {name}_top;

architecture rtl of {name}_top is
begin

    -- Add your design here

end architecture rtl;
"""
    else:
        if with_pd:
            content = f"""\
// {name}_top.v  Top-level module for {name} project (DE10-Lite)
// Generated by quartus-workflow setup. Edit as needed.

module {name}_top (
    input  wire        CLOCK_50,
    input  wire [1:0]  KEY,
    input  wire [9:0]  SW,
    output wire [9:0]  LEDR
);

// Platform Designer system instantiation
{name} u0 (
    .clk_clk       (CLOCK_50),
    .reset_reset_n (KEY[0])
);

endmodule
"""
        else:
            content = f"""\
// {name}_top.v  Top-level module for {name} project (DE10-Lite)
// Generated by quartus-workflow setup. Edit as needed.

module {name}_top (
    input  wire        CLOCK_50,
    input  wire [1:0]  KEY,
    input  wire [9:0]  SW,
    output wire [9:0]  LEDR
);

// Add your design here

endmodule
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [create] {os.path.basename(path)}")


def _get_board_pins_file(config):
    """Return the pin-assignment QSF path for the configured board, or None.

    Looks for any *.qsf in lib/board/<board>/assignments/.  The board name from
    hw_workflow.toml uses hyphens (e.g. 'de10-lite'); the directory name uses
    underscores ('de10_lite').
    """
    board = config["tools"].get("board", "").replace("-", "_")
    if not board:
        return None
    asgn_dir  = os.path.join(_HW_DIR, "lib", "board", board, "assignments")
    qsf_files = glob.glob(os.path.join(asgn_dir, "*.qsf"))
    return qsf_files[0] if qsf_files else None


def _apply_pin_assignments(qsf_path, pins_file):
    """Append DE10-Lite pin assignments to a project .qsf.

    Reads pins_file and copies only set_instance_assignment and
    set_location_assignment lines (skips set_global_assignment to avoid
    conflicts with the skeleton header).  Idempotent: skips if the marker
    comment is already present in the target .qsf.
    """
    if not os.path.exists(pins_file):
        _warn(f"Pins file not found: {pins_file}")
        return
    marker = "# DE10-Lite pin assignments"
    text   = open(qsf_path, encoding="utf-8").read()
    if marker in text:
        print(f"  [skip] {os.path.basename(qsf_path)} — pin assignments already present")
        return
    lines = []
    for line in open(pins_file, encoding="utf-8"):
        s = line.strip()
        if s.startswith("set_instance_assignment") or s.startswith("set_location_assignment"):
            lines.append(line.rstrip())
    with open(qsf_path, "a", encoding="utf-8") as f:
        f.write(f"\n{marker}\n")
        f.write("\n".join(lines) + "\n")
    print(f"  [patch] {os.path.basename(qsf_path)} — {len(lines)} pin assignments added")


def _write_skeleton_sdc(path, name, board=""):
    """Write a minimal SDC timing-constraints file. Skips if file already exists.

    Loads lib/board/<board>/templates/sdc_template.sdc when board is set,
    substituting {name}. Falls back to an inline DE10-Lite template.
    """
    if os.path.exists(path):
        print(f"  [skip] {os.path.basename(path)} already exists")
        return
    content = None
    if board:
        tpl = os.path.join(_HW_DIR, "lib", "board", board, "templates", "sdc_template.sdc")
        if os.path.exists(tpl):
            with open(tpl, encoding="utf-8") as f:
                content = f.read().replace("{name}", name)
    if content is None:
        content = (
            f"# {name}.sdc -- Timing constraints for DE10-Lite (MAX10)\n"
            f"# Generated by quartus-workflow setup. Edit as needed.\n\n"
            f"# 50 MHz system clock on MAX10_CLK1_50 (PIN_P11)\n"
            f"create_clock -period 20.000 -name clk [get_ports {{MAX10_CLK1_50}}]\n\n"
            f"# Allow TimeQuest to derive clock uncertainty automatically\n"
            f"derive_clock_uncertainty\n"
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [create] {os.path.basename(path)}")


def _apply_sdc_to_qsf(qsf_path, sdc_rel_path):
    """Add an SDC_FILE assignment to the project .qsf. Idempotent.

    Checks whether the exact SDC_FILE line is already present before appending,
    so it is safe to call multiple times or on an existing project.
    """
    line = f"set_global_assignment -name SDC_FILE {sdc_rel_path}"
    with open(qsf_path, encoding="utf-8") as f:
        text = f.read()
    if line in text:
        print(f"  [skip] SDC already referenced: {sdc_rel_path}")
        return
    with open(qsf_path, "a", encoding="utf-8") as f:
        f.write(f"\n{line}\n")
    print(f"  [patch] {os.path.basename(qsf_path)} — SDC_FILE {sdc_rel_path}")


def _update_toml_project(toml_path, name, hdl_lang):
    """Update or append [project] section in hw_workflow.toml."""
    text = open(toml_path, encoding="utf-8").read()
    if "[project]" in text:
        text = re.sub(r'^(name\s*=\s*).*',     rf'\1"{name}"',     text, flags=re.MULTILINE)
        text = re.sub(r'^(hdl_lang\s*=\s*).*', rf'\1"{hdl_lang}"', text, flags=re.MULTILINE)
    else:
        text += f'\n[project]\nname     = "{name}"\nhdl_lang = "{hdl_lang}"  # verilog | vhdl\n'
    with open(toml_path, "w", encoding="utf-8") as f:
        f.write(text)


def cmd_setup(config, args):
    """Scaffold a new Quartus project under quartus_workspace/."""
    name     = args.name
    version  = config["tools"].get("quartus_version", "25.1")
    device   = config["tools"].get("device", "10M50DAF484C7G")
    hdl_lang = getattr(args, "lang", None) or config.get("project", {}).get("hdl_lang", "verilog")
    with_pd   = getattr(args, "pd", False)
    with_pins = getattr(args, "pins", False)
    with_sdc  = getattr(args, "sdc", False)
    board     = config["tools"].get("board", "")
    ws_dir    = os.path.join(_HW_DIR, "quartus_workspace")
    proj_dir = os.path.join(ws_dir, name)

    print(f"Setting up project: {name}")
    os.makedirs(proj_dir, exist_ok=True)

    _write_skeleton_qpf(os.path.join(proj_dir, f"{name}.qpf"), name, version)
    _write_skeleton_qsf(os.path.join(proj_dir, f"{name}.qsf"), name, hdl_lang, device, with_pd)
    if with_pd:
        _ensure_qip_in_qsf(os.path.join(proj_dir, f"{name}.qsf"), name)
        _write_skeleton_qsys(os.path.join(proj_dir, f"{name}.qsys"), version, hdl_lang, device)
        # Auto-reference the PD-generated SDC (created by Generate HDL in Platform Designer)
        _apply_sdc_to_qsf(os.path.join(proj_dir, f"{name}.qsf"), f"{name}/synthesis/{name}.sdc")
    if with_sdc:
        _write_skeleton_sdc(os.path.join(proj_dir, f"{name}.sdc"), name, board)
        _apply_sdc_to_qsf(os.path.join(proj_dir, f"{name}.qsf"), f"{name}.sdc")
    if with_pins:
        pins_file = _get_board_pins_file(config)
        if pins_file:
            _apply_pin_assignments(os.path.join(proj_dir, f"{name}.qsf"), pins_file)
        else:
            _warn(f"No pin assignments found for board '{board}' — skipping --pins")

    ext = ".vhd" if hdl_lang == "vhdl" else ".v"
    _write_skeleton_top(os.path.join(proj_dir, f"{name}_top{ext}"), name, hdl_lang, with_pd, board)

    toml_path = os.path.join(_HW_DIR, "hw_workflow.toml")
    qpf  = f"quartus_workspace/{name}/{name}.qpf"
    qsys = f"quartus_workspace/{name}/{name}.qsys"
    sof  = f"quartus_workspace/{name}/output_files/{name}.sof"
    _update_toml_files(toml_path, qpf, qsys, sof)
    _update_toml_project(toml_path, name, hdl_lang)
    print(f"  [update] hw_workflow.toml — [project] and [files] updated")

    _success(f"\n[+] Project scaffold ready: quartus_workspace/{name}/")
    print(f"    {name}.qpf       — Quartus project  : quartus-workflow open-quartus")
    if with_pd:
        print(f"    {name}.qsys      — Platform Designer : quartus-workflow open-pd")
    print(f"    {name}_top{ext}  — top-level HDL template")
    if with_sdc:
        print(f"    {name}.sdc       — timing constraints (edit for your design)")
    print(f"    Next: quartus-workflow set-top {name}_top{ext}")

    if getattr(args, "quartus", False):
        qpf_abs = os.path.join(proj_dir, f"{name}.qpf")
        qgui    = find_quartus_gui(config)
        print(f"\nOpening Quartus IDE: {qpf_abs}")
        subprocess.Popen([qgui, _to_win_path(qpf_abs)])


def _update_toml_files(toml_path, qpf, qsys, sof):
    """Update the [files] section of hw_workflow.toml in-place using regex substitution."""
    text = open(toml_path, encoding="utf-8").read()
    text = re.sub(r'^(qpf\s*=\s*).*',  rf'\1"{qpf}"',  text, flags=re.MULTILINE)
    text = re.sub(r'^(qsys\s*=\s*).*', rf'\1"{qsys}"', text, flags=re.MULTILINE)
    text = re.sub(r'^(sof\s*=\s*).*',  rf'\1"{sof}"',  text, flags=re.MULTILINE)
    with open(toml_path, "w", encoding="utf-8") as f:
        f.write(text)


def cmd_set_top(config, args):
    """Set TOP_LEVEL_ENTITY in the project .qsf file."""
    qpf = config["files"].get("qpf", "")
    if not qpf:
        _error("No QPF configured. Run: quartus-workflow setup <name>")
        sys.exit(1)
    qsf = os.path.splitext(qpf)[0] + ".qsf"
    if not os.path.exists(qsf):
        _error(f"QSF not found: {qsf}")
        print("Create the Quartus project first: quartus-workflow open-quartus")
        sys.exit(1)

    entity = os.path.splitext(os.path.basename(args.top))[0]
    line   = f"set_global_assignment -name TOP_LEVEL_ENTITY {entity}"
    text   = open(qsf, encoding="utf-8").read()
    pat    = r'^set_global_assignment\s+-name\s+TOP_LEVEL_ENTITY\s+\S+'
    if re.search(pat, text, flags=re.MULTILINE):
        text = re.sub(pat, line, text, flags=re.MULTILINE)
    else:
        text += f"\n{line}\n"
    with open(qsf, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[*] Top-level entity : {entity}")
    print(f"    in: {os.path.basename(qsf)}")


def cmd_set_project(config, args):
    """Update hw_workflow.toml [files] to point at the named project under quartus_workspace/."""
    name        = args.name
    ws_dir      = os.path.join(_HW_DIR, "quartus_workspace")
    project_dir = os.path.join(ws_dir, name)

    if not os.path.isdir(project_dir):
        print(f"Project '{name}' not found in quartus_workspace/.")
        if os.path.isdir(ws_dir):
            available = sorted(
                d for d in os.listdir(ws_dir)
                if os.path.isdir(os.path.join(ws_dir, d)) and not d.startswith(".")
            )
            if available:
                print(f"Available projects: {', '.join(available)}")
        sys.exit(1)

    qpf_files = glob.glob(os.path.join(project_dir, "*.qpf"))
    qpf_stem  = os.path.splitext(os.path.basename(qpf_files[0]))[0] if qpf_files else name

    qpf  = f"quartus_workspace/{name}/{qpf_stem}.qpf"
    qsys = f"quartus_workspace/{name}/{qpf_stem}.qsys"
    sof  = f"quartus_workspace/{name}/output_files/{qpf_stem}.sof"

    toml_path = os.path.join(_HW_DIR, "hw_workflow.toml")
    _update_toml_files(toml_path, qpf, qsys, sof)

    print(f"[*] Project set to: {name}")
    print(f"    qpf  = {qpf}")
    print(f"    qsys = {qsys}")
    print(f"    sof  = {sof}")


def cmd_sync_top(config, args):
    """Sync component declaration in top-level HDL from PD-generated _inst file.

    Reads <name>/<name>_inst.vhd (generated by Platform Designer 'Generate HDL'),
    extracts and cleans the component declaration, and replaces the stale
    declaration in <name>_top.vhd.  The port map is left untouched; warnings
    are printed for any new ports that are not yet connected.
    """
    qpf = config["files"].get("qpf", "")
    if not qpf:
        _error("No QPF configured. Run: quartus-workflow setup <name> --pd")
        sys.exit(1)

    name     = os.path.splitext(os.path.basename(qpf))[0]
    proj_dir = os.path.dirname(qpf)
    hdl_lang = config["project"].get("hdl_lang", "vhdl")

    inst_path = _find_inst_file(proj_dir, name, hdl_lang)
    if not inst_path:
        ext = "vhd" if hdl_lang == "vhdl" else "v"
        _error(f"PD instantiation file not found: {name}/{name}_inst.{ext}")
        print("Run 'Generate HDL' in Platform Designer first.")
        sys.exit(1)

    ext      = "vhd" if hdl_lang == "vhdl" else "v"
    top_path = os.path.join(proj_dir, f"{name}_top.{ext}")
    if not os.path.exists(top_path):
        _error(f"Top-level file not found: {top_path}")
        sys.exit(1)

    inst_text = open(inst_path, encoding="utf-8").read()
    top_text  = open(top_path,  encoding="utf-8").read()

    if hdl_lang == "vhdl":
        old_block = _extract_component_block_vhd(top_text,  name)
        new_block = _extract_component_block_vhd(inst_text, name)
    else:
        _error("sync-top for Verilog is not yet implemented.")
        sys.exit(1)

    if not new_block:
        _error(f"Could not parse component block for '{name}' in {inst_path}")
        sys.exit(1)

    new_top, changed = _replace_component_block_vhd(top_text, name, new_block)
    if not changed:
        print(f"  [skip] No component declaration for '{name}' found in "
              f"{os.path.basename(top_path)}")
        print("         Add the component block manually, then re-run sync-top.")
        sys.exit(1)

    with open(top_path, "w", encoding="utf-8") as f:
        f.write(new_top)
    print(f"  [sync] {os.path.basename(top_path)} — component declaration updated")
    if old_block:
        _warn_type_changes_vhd(old_block, new_block)
    _warn_unconnected_ports(new_top, new_block, name)


def cmd_apply_pins(config, args):
    """Append board pin assignments to the project .qsf.

    Reads the pin-assignment QSF from lib/board/<board>/assignments/ based on
    tools.board in hw_workflow.toml and patches it into the project .qsf.
    Idempotent: skips if the marker comment is already present.
    """
    qpf = config["files"].get("qpf", "")
    if not qpf:
        _error("No QPF configured. Run: quartus-workflow setup <name>")
        sys.exit(1)
    qsf = os.path.splitext(qpf)[0] + ".qsf"
    if not os.path.exists(qsf):
        _error(f"QSF not found: {qsf}")
        sys.exit(1)
    pins_file = _get_board_pins_file(config)
    if not pins_file:
        board = config["tools"].get("board", "(not set)")
        _error(f"No pin-assignment file found for board '{board}'.")
        print("Check tools.board in hw_workflow.toml and lib/board/<board>/assignments/")
        sys.exit(1)
    _apply_pin_assignments(qsf, pins_file)


def cmd_clean(config, args):
    """Delete Quartus compilation outputs (output_files/, db/, incremental_db/).

    Use --keep-sof to preserve the .sof file so 'program' still works without
    a full rebuild. Use --dry-run to preview what would be deleted.
    """
    qpf = config["files"].get("qpf", "")
    if not qpf:
        _error("No QPF configured. Run: quartus-workflow setup <name>")
        sys.exit(1)
    project_dir  = os.path.dirname(os.path.abspath(qpf))
    project_name = os.path.splitext(os.path.basename(qpf))[0]

    targets = [
        os.path.join(project_dir, "output_files"),
        os.path.join(project_dir, "db"),
        os.path.join(project_dir, "incremental_db"),
    ]
    sof_path = os.path.abspath(
        os.path.join(project_dir, "output_files", f"{project_name}.sof")
    )
    dry      = getattr(args, "dry_run",  False)
    keep_sof = getattr(args, "keep_sof", False)

    removed = 0
    for target in targets:
        if not os.path.exists(target):
            print(f"[skip] Not found: {target}")
            continue
        for root, dirs, files in os.walk(target, topdown=False):
            for fname in files:
                fpath = os.path.join(root, fname)
                if keep_sof and os.path.abspath(fpath) == sof_path:
                    print(f"[keep] {fpath}")
                    continue
                if dry:
                    print(f"[dry]  {fpath}")
                else:
                    os.remove(fpath)
                    print(f"[rm]   {fpath}")
                removed += 1
            if not dry:
                for dname in dirs:
                    try:
                        os.rmdir(os.path.join(root, dname))
                    except OSError:
                        pass
        if not dry:
            try:
                os.rmdir(target)
            except OSError:
                pass  # non-empty (kept .sof) — leave the directory

    if dry:
        print(f"\n[dry-run] {removed} file(s) would be removed.")
    else:
        _success(f"\n[+] Clean complete — {removed} file(s) removed.")


def _print_build_summary(qpf):
    """Parse .fit.rpt and .sta.rpt to print a brief resource + timing summary."""
    project_dir  = os.path.dirname(qpf)
    project_name = os.path.splitext(os.path.basename(qpf))[0]
    out_dir = os.path.join(project_dir, "output_files")

    fit_rpt = os.path.join(out_dir, f"{project_name}.fit.rpt")
    sta_rpt = os.path.join(out_dir, f"{project_name}.sta.rpt")

    print("\n--- Build Summary " + "-" * 42)

    # Logic utilisation from fit report
    if os.path.exists(fit_rpt):
        with open(fit_rpt, encoding="latin-1") as f:
            text = f.read()
        for pattern, label in [
            (r"Total logic elements\s*;\s*([\d,]+)\s*/\s*([\d,]+)", "Logic elements"),
            (r"Total registers\s*;\s*([\d,]+)",                      "Registers"),
            (r"Total pins\s*;\s*([\d,]+)\s*/\s*([\d,]+)",            "Pins"),
            (r"Total memory bits\s*;\s*([\d,]+)\s*/\s*([\d,]+)",     "Memory bits"),
        ]:
            m = re.search(pattern, text)
            if m:
                print(f"  {label:<20} {' / '.join(m.groups())}")
    else:
        print(f"  (fit report not found: {fit_rpt})")

    # Timing from sta report
    if os.path.exists(sta_rpt):
        with open(sta_rpt, encoding="latin-1") as f:
            text = f.read()

        # Fmax — rows with two consecutive MHz columns exist only in Fmax Summary
        # tables (Fmax + Restricted Fmax). The Clocks table has a single MHz column
        # so it is never matched. Filter altera_reserved_* (JTAG clock); report min.
        user_fmax = [
            float(m.group(1))
            for m in re.finditer(
                r";\s*([\d.]+)\s*MHz\s*;\s*[\d.]+\s*MHz\s*;\s*([^;]+?)\s*;",
                text
            )
            if "altera_reserved" not in m.group(2).lower()
        ]
        if user_fmax:
            print(f"  {'Fmax':<20} {min(user_fmax):.2f} MHz")
        else:
            fmax = re.search(r"Fmax\s*=\s*([\d.]+\s*MHz)", text)
            if fmax:
                print(f"  {'Fmax':<20} {fmax.group(1)}")

        # Worst slack
        slack = re.search(
            r"Worst-?case\s+Slack\s*[=:;]\s*([-\d.]+\s*ns)",
            text, re.IGNORECASE
        )
        if slack:
            val  = slack.group(1).strip()
            flag = "  [!] TIMING VIOLATION" if val.startswith("-") else ""
            print(f"  {'Worst slack':<20} {val}{flag}")
    else:
        print(f"  (sta report not found: {sta_rpt})")

    print("-" * 60 + "\n")


def _print_power_summary(qpf):
    """Parse .pow.rpt to print a brief power summary."""
    project_dir  = os.path.dirname(os.path.abspath(qpf))
    project_name = os.path.splitext(os.path.basename(qpf))[0]
    pow_rpt = os.path.join(project_dir, "output_files", f"{project_name}.pow.rpt")
    print("-" * 60)
    print("  Power Summary")
    print("-" * 60)
    if os.path.exists(pow_rpt):
        text = open(pow_rpt, encoding="latin-1").read()
        fields = [
            ("Total power",   r"Total Thermal Power Dissipation\s+;\s+([\d.]+\s*mW)"),
            ("Dynamic power", r"Core Dynamic Thermal Power Dissipation\s+;\s+([\d.]+\s*mW)"),
            ("Static power",  r"Core Static Thermal Power Dissipation\s+;\s+([\d.]+\s*mW)"),
            ("I/O power",     r"I/O Thermal Power Dissipation\s+;\s+([\d.]+\s*mW)"),
        ]
        for label, pattern in fields:
            m = re.search(pattern, text)
            if m:
                print(f"  {label:<20} {m.group(1)}")
    else:
        print(f"  (pow report not found: {pow_rpt})")
    print("-" * 60 + "\n")


# ---------------------------------------------------------------------------
# Console diagnostics (system-console Tcl wrappers)
# ---------------------------------------------------------------------------

def _run_tcl(sc, tcl):
    """Write *tcl* to a temp file and run system-console --script=<file>."""
    tmp = tempfile.NamedTemporaryFile(suffix=".tcl", mode="w", delete=False,
                                     encoding="utf-8")
    try:
        tmp.write(tcl)
        tmp.close()
        # system-console needs QUARTUS_ROOTDIR pointing at its own Quartus install.
        # Derive it from the binary: sopc_builder/bin/../../.. = quartus root.
        # Always override — environment may contain a stale path from another version.
        quartus_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(sc))))
        env = os.environ.copy()
        env["QUARTUS_ROOTDIR"] = quartus_root
        result = subprocess.run([sc, f"--script={tmp.name}"],
                                env=env,
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace")
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, result.args)
    finally:
        os.unlink(tmp.name)


def _parse_ocm_base(system_h):
    """Parse the on-chip memory base address from a niosv-bsp-generated system.h.

    Scans for the first ``#define <NAME>MEMORY<...>_BASE 0x...`` macro.
    """
    if not os.path.isfile(system_h):
        return None
    pat = re.compile(r'#define\s+(\w+)\s+(0x[0-9a-fA-F]+)')
    with open(system_h, encoding="utf-8") as f:
        for line in f:
            m = pat.match(line.strip())
            if m:
                name, addr = m.group(1), m.group(2)
                if "MEMORY" in name and name.endswith("_BASE"):
                    return addr
    return None


def _console_scan(sc):
    """Print JTAG masters and Avalon devices available via system-console."""
    # get_hardware_names is not in the Quartus 25.1 system-console API.
    # Use get_service_paths to enumerate master and device services instead.
    tcl = textwrap.dedent("""\
        puts "=== JTAG Masters ==="
        set masters [get_service_paths master]
        if {[llength $masters] == 0} {
            puts "  (none - add 'JTAG Avalon Master Bridge' IP in Platform Designer)"
        } else {
            foreach m $masters { puts "  $m" }
        }
        puts ""
        puts "=== Devices ==="
        set devices [get_service_paths device]
        if {[llength $devices] == 0} {
            puts "  (none found)"
        } else {
            foreach d $devices { puts "  $d" }
        }
    """)
    _run_tcl(sc, tcl)


# Tcl snippet: open master service with claim_service (Quartus 20.x+) and
# fall back to open_service (Quartus 18.x).  Binds $handle to the service handle.
_TCL_OPEN_MASTER = textwrap.dedent("""\
    set _masters [get_service_paths master]
    if {[llength $_masters] == 0} { error "No JTAG master found. Ensure FPGA is programmed and USB Blaster is connected." }
    set _path [lindex $_masters 0]
    if {[catch {set handle [claim_service master $_path "" -timeout_ms 5000]} _err]} {
        open_service master $_path
        set handle $_path
    }
""")


def _master_open_tcl(master_override):
    """Return Tcl lines that open the master service and bind $handle."""
    if master_override:
        return textwrap.dedent(f"""\
            set _path "{master_override}"
            if {{[catch {{set handle [claim_service master $_path "" -timeout_ms 5000]}} _err]}} {{
                open_service master $_path
                set handle $_path
            }}
        """)
    return _TCL_OPEN_MASTER


def _console_peek(sc, addr, master_override):
    """Read a 32-bit word from Avalon memory at addr and print the result."""
    open_master = _master_open_tcl(master_override)
    tcl = textwrap.dedent(f"""\
        {open_master}
        set bytes [master_read_memory $handle {addr} 4]
        set val [expr {{[lindex $bytes 0] | ([lindex $bytes 1]<<8) | ([lindex $bytes 2]<<16) | ([lindex $bytes 3]<<24)}}]
        puts [format "{addr}: 0x%08X" $val]
        catch {{close_service master $handle}}
    """)
    _run_tcl(sc, tcl)


def _console_poke(sc, addr, val, master_override):
    """Write a 32-bit word val to Avalon memory at addr."""
    open_master = _master_open_tcl(master_override)
    tcl = textwrap.dedent(f"""\
        {open_master}
        set _v {val}
        set _bytes [list [expr {{$_v & 0xFF}}] [expr {{($_v >> 8) & 0xFF}}] [expr {{($_v >> 16) & 0xFF}}] [expr {{($_v >> 24) & 0xFF}}]]
        master_write_memory $handle {addr} $_bytes
        puts "Wrote {val} to {addr}"
        catch {{close_service master $handle}}
    """)
    _run_tcl(sc, tcl)


def _console_load(sc, binpath, baseaddr, master_override):
    """Load a .bin file byte-by-byte into Avalon memory at baseaddr via JTAG."""
    win_bin = _to_win_path(os.path.abspath(binpath)).replace("\\", "/")
    open_master = _master_open_tcl(master_override)
    tcl = textwrap.dedent(f"""\
        set f [open "{win_bin}" rb]
        set raw [read $f]
        close $f
        binary scan $raw cu* byte_list
        {open_master}
        master_write_memory $handle {baseaddr} $byte_list
        puts "Loaded [llength $byte_list] bytes at {baseaddr}"
        catch {{close_service master $handle}}
    """)
    _run_tcl(sc, tcl)


def _validate_hex(value, name):
    """Validate that value is a valid hex literal (e.g. 0x1000); exit on error."""
    try:
        int(value, 16)
    except ValueError:
        _error(f"{name} must be a valid hex value (e.g. 0x1000) — got: {value!r}")
        sys.exit(1)


def cmd_console_scan(config, args):
    """Scan JTAG masters and devices via system-console."""
    _console_scan(find_system_console(config))


def cmd_console_peek(config, args):
    """Read a 32-bit word from Avalon memory via JTAG."""
    _validate_hex(args.addr, "addr")
    _console_peek(find_system_console(config), args.addr,
                  getattr(args, "master", None))


def cmd_console_poke(config, args):
    """Write a 32-bit word to Avalon memory via JTAG."""
    _validate_hex(args.addr, "addr")
    _validate_hex(args.val, "val")
    _console_poke(find_system_console(config), args.addr, args.val,
                  getattr(args, "master", None))


def cmd_console_load(config, args):
    """Load a .bin file into Avalon memory via JTAG master."""
    sc       = find_system_console(config)
    sopcinfo = config["files"].get("sopcinfo", "")

    binpath = getattr(args, "bin", None)
    if not binpath:
        app_dir = config["files"].get("app_dir", "") or \
                  (os.path.join(os.path.dirname(sopcinfo), "software", "app")
                   if sopcinfo else "")
        if app_dir:
            binpath = os.path.join(os.path.abspath(app_dir), "build", "app.bin")
    if not binpath or not os.path.isfile(binpath):
        _error("bin not found — pass path explicitly or run build-app first")
        sys.exit(1)

    baseaddr = getattr(args, "baseaddr", None)
    if not baseaddr:
        bsp_dir = config["files"].get("bsp_dir", "") or \
                  (os.path.join(os.path.dirname(sopcinfo), "software", "hal_bsp")
                   if sopcinfo else "")
        if bsp_dir:
            baseaddr = _parse_ocm_base(
                os.path.join(os.path.abspath(bsp_dir), "system.h"))
    if not baseaddr:
        _error("baseaddr not found — pass address or run gen-bsp first")
        sys.exit(1)

    print(f"[*] Loading  : {binpath}")
    print(f"[*] Base addr: {baseaddr}")
    _console_load(sc, binpath, baseaddr, getattr(args, "master", None))


# ---------------------------------------------------------------------------
# Nios V software development commands
# ---------------------------------------------------------------------------

def cmd_gen_bsp(config, args):
    """Generate (or update) a Nios V Board Support Package from the .sopcinfo file."""
    sopcinfo = config["files"].get("sopcinfo", "")
    if not sopcinfo:
        _error("sopcinfo not configured in hw_workflow.toml [files]")
        print("  Add:  sopcinfo = \"quartus_workspace/<project>/<system>.sopcinfo\"")
        sys.exit(1)
    if not os.path.isfile(sopcinfo):
        _error(f"sopcinfo not found: {sopcinfo}")
        print("  Generate HDL in Platform Designer first (quartus-workflow open-pd → Generate HDL).")
        sys.exit(1)

    bsp_type = getattr(args, "type", "hal") or "hal"
    bsp_dir  = getattr(args, "bsp_dir", None) or config["files"].get("bsp_dir", "") or \
               os.path.join(os.path.dirname(sopcinfo), "software", f"{bsp_type}_bsp")
    bsp_dir  = os.path.abspath(bsp_dir)
    os.makedirs(bsp_dir, exist_ok=True)
    settings = os.path.join(bsp_dir, "settings.bsp")

    niosv_bsp = find_niosv_bsp(config)

    # niosv-bsp needs its own niosv/bin on PATH to locate its helper scripts.
    # It also requires QUARTUS_ROOTDIR and SOPC_KIT_NIOS2 to find the device DB.
    niosv_bin  = os.path.dirname(os.path.abspath(niosv_bsp))
    acds_root  = os.path.dirname(os.path.dirname(niosv_bin))   # .../25.1std/
    env = os.environ.copy()
    env["PATH"]            = niosv_bin + os.pathsep + env.get("PATH", "")
    env["QUARTUS_ROOTDIR"] = os.path.join(acds_root, "quartus")
    env["SOPC_KIT_NIOS2"]  = os.path.join(acds_root, "nios2eds")

    def _run_bsp(update: bool) -> int:
        if update:
            _cmd = [niosv_bsp, "-u", settings]
            print(f"\nUpdating existing BSP in {bsp_dir}")
        else:
            _cmd = [niosv_bsp, "-c", f"-s={sopcinfo}", f"-t={bsp_type}",
                    f"-b={bsp_dir}", settings]
            print(f"\nCreating {bsp_type.upper()} BSP in {bsp_dir}")
        return subprocess.run(_cmd, env=env).returncode

    if os.path.isfile(settings):
        rc = _run_bsp(update=True)
        if rc != 0:
            # Re-run with captured output to detect stale device references
            probe = subprocess.run(
                [niosv_bsp, "-u", settings], env=env, capture_output=True, text=True
            )
            combined = probe.stdout + probe.stderr
            if "is out of range" in combined or "BSP not valid" in combined:
                print()
                print("[!] BSP update failed — settings.bsp references a device no longer in the system.")
                print(f"    BSP dir: {bsp_dir}")
                ans = input("    Delete old BSP and regenerate from scratch? [Y/n] ").strip().lower()
                if ans in ("", "y"):
                    shutil.rmtree(bsp_dir)
                    os.makedirs(bsp_dir, exist_ok=True)
                    rc = _run_bsp(update=False)
                    if rc != 0:
                        sys.exit(rc)
                else:
                    sys.exit(1)
            else:
                sys.exit(rc)
    else:
        rc = _run_bsp(update=False)
        if rc != 0:
            sys.exit(rc)

    _success(f"\n[+] BSP ready: {bsp_dir}")
    print(f"    Next: cd {bsp_dir} && cmake -G \"Unix Makefiles\" -B build "
          f"-DCMAKE_TOOLCHAIN_FILE=toolchain.cmake && cmake --build build")


def cmd_gen_app(config, args):
    """Generate a Nios V application CMakeLists.txt from an existing BSP (niosv-app)."""
    sopcinfo = config["files"].get("sopcinfo", "")
    # sopcinfo must be an absolute path when used to derive sibling directories;
    # a relative or empty value would place bsp_dir/app_dir at CWD (repo root).
    sopcinfo_abs = sopcinfo if (sopcinfo and os.path.isabs(sopcinfo)) else ""

    bsp_dir = getattr(args, "bsp_dir", None) or config["files"].get("bsp_dir", "") or \
              (os.path.join(os.path.dirname(sopcinfo_abs), "software", "hal_bsp")
               if sopcinfo_abs else "")
    if not bsp_dir:
        _error("bsp_dir not configured and sopcinfo not set — run gen-bsp first")
        sys.exit(1)
    bsp_dir = os.path.abspath(bsp_dir)
    if not os.path.isfile(os.path.join(bsp_dir, "settings.bsp")):
        _error(f"settings.bsp not found in {bsp_dir} — run gen-bsp first")
        sys.exit(1)

    app_dir = getattr(args, "app_dir", None) or config["files"].get("app_dir", "") or \
              (os.path.join(os.path.dirname(sopcinfo_abs), "software", "app")
               if sopcinfo_abs else "")
    if not app_dir:
        _error("app_dir not configured — set files.app_dir in hw_workflow.toml or pass --app-dir")
        sys.exit(1)
    app_dir = os.path.abspath(app_dir)
    os.makedirs(app_dir, exist_ok=True)

    niosv_app  = find_niosv_app(config)

    srcs = getattr(args, "srcs", None)
    if srcs:
        srcs = os.path.abspath(srcs)
    else:
        # Default: scan app_dir for .c files. Fail early with a helpful hint if empty.
        c_files = [f for f in os.listdir(app_dir) if f.endswith(".c")]
        if not c_files:
            _error(f"No .c source files found in {app_dir}")
            print("  Use --srcs to specify a source file, e.g.:")
            niosv_root = os.path.dirname(os.path.dirname(os.path.abspath(niosv_app)))
            example = os.path.join(niosv_root, "examples", "software",
                                   "hello_world", "hello_world.c")
            print(f"    quartus-workflow gen-app --srcs \"{example}\"")
            sys.exit(1)
        srcs = app_dir
    niosv_bin  = os.path.dirname(os.path.abspath(niosv_app))
    acds_root  = os.path.dirname(os.path.dirname(niosv_bin))
    env = os.environ.copy()
    env["PATH"]            = niosv_bin + os.pathsep + env.get("PATH", "")
    env["QUARTUS_ROOTDIR"] = os.path.join(acds_root, "quartus")
    env["SOPC_KIT_NIOS2"]  = os.path.join(acds_root, "nios2eds")

    cmd = [niosv_app,
           f"--bsp-dir={bsp_dir}",
           f"--app-dir={app_dir}",
           f"--srcs={srcs}"]
    print(f"\nGenerating app project in {app_dir}")
    subprocess.run(cmd, env=env, check=True)
    _success(f"[+] App ready: {app_dir}")
    print(f"    Next: cd {app_dir} && cmake -G \"Unix Makefiles\" -B build "
          f"-DCMAKE_TOOLCHAIN_FILE=../hal_bsp/toolchain.cmake && cmake --build build")


def cmd_build_app(config, args):
    """Build the Nios V application: cmake configure + build → .elf, then .bin."""
    sopcinfo     = config["files"].get("sopcinfo", "")
    sopcinfo_abs = sopcinfo if (sopcinfo and os.path.isabs(sopcinfo)) else ""

    bsp_dir = getattr(args, "bsp_dir", None) or config["files"].get("bsp_dir", "") or \
              (os.path.join(os.path.dirname(sopcinfo_abs), "software", "hal_bsp")
               if sopcinfo_abs else "")
    if not bsp_dir:
        _error("bsp_dir not configured — run gen-bsp first or pass --bsp-dir")
        sys.exit(1)
    bsp_dir   = os.path.abspath(bsp_dir)
    toolchain = os.path.join(bsp_dir, "toolchain.cmake")
    if not os.path.isfile(toolchain):
        _error(f"toolchain.cmake not found in {bsp_dir} — run gen-bsp first")
        sys.exit(1)

    app_dir = getattr(args, "app_dir", None) or config["files"].get("app_dir", "") or \
              (os.path.join(os.path.dirname(sopcinfo_abs), "software", "app")
               if sopcinfo_abs else "")
    if not app_dir:
        _error("app_dir not configured — run gen-app first or pass --app-dir")
        sys.exit(1)
    app_dir = os.path.abspath(app_dir)
    if not os.path.isfile(os.path.join(app_dir, "CMakeLists.txt")):
        _error(f"CMakeLists.txt not found in {app_dir} — run gen-app first")
        sys.exit(1)

    cmake = find_cmake(config)
    if not cmake:
        _error("cmake not found — run setup_env.ps1 or install cmake")
        sys.exit(1)

    build_dir     = os.path.join(app_dir, "build")
    toolchain_rel = os.path.relpath(toolchain, app_dir)

    # Offer to clean the build dir when it already exists (stale objects after BSP changes).
    if os.path.isdir(build_dir):
        do_clean = getattr(args, "clean", False)
        if not do_clean:
            ans = input(f"  Build dir exists: {build_dir}\n  Clean before building? [Y/n] ").strip().lower()
            do_clean = ans in ("", "y", "yes")
        if do_clean:
            print("  Cleaning build dir")
            try:
                shutil.rmtree(build_dir)
            except PermissionError:
                _error("Cannot clean build dir — a file is locked by another process.")
                print("  VSCode CMake Tools may have the cache open.")
                print("  Fix: add to .vscode/settings.json:")
                print('    "cmake.configureOnOpen": false')
                print(f"  Then manually delete: {build_dir}")
                sys.exit(1)
        else:
            # Still clear a stale generator cache so cmake does not error out.
            cache = os.path.join(build_dir, "CMakeCache.txt")
            if os.path.isfile(cache):
                with open(cache) as f:
                    if "Unix Makefiles" not in f.read():
                        print("  Stale cmake cache (wrong generator) — clearing")
                        try:
                            shutil.rmtree(build_dir)
                        except PermissionError:
                            _error("Cannot clear build dir — a file is locked by another process.")
                            print(f"  Manually delete: {build_dir}")
                            sys.exit(1)

    # cmake and make need the RiscFree toolchain on PATH to find riscv32-unknown-elf-gcc.
    # Derive riscfree_root from the cmake binary: .../riscfree/build_tools/cmake/bin/cmake.exe
    cmake_abs    = os.path.abspath(cmake)
    riscfree_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(cmake_abs))))
    toolchain_bin = os.path.join(riscfree_root, "toolchain", "riscv32-unknown-elf", "bin")
    make_bin      = os.path.join(riscfree_root, "build_tools", "bin")
    env = os.environ.copy()
    env["PATH"] = toolchain_bin + os.pathsep + make_bin + os.pathsep + env.get("PATH", "")

    print(f"\nConfiguring cmake in {build_dir}")
    subprocess.run([cmake, "-G", "Unix Makefiles", "-B", build_dir,
                    f"-DCMAKE_TOOLCHAIN_FILE={toolchain_rel}"],
                   cwd=app_dir, env=env, check=True)

    print(f"\nBuilding app")
    subprocess.run([cmake, "--build", build_dir], cwd=app_dir, env=env, check=True)

    elf_files = list(Path(build_dir).glob("*.elf"))
    if not elf_files:
        _error(f"No .elf file found in {build_dir} after build")
        sys.exit(1)
    elf = str(elf_files[0])
    _success(f"[+] ELF built  : {elf}")

    objcopy = find_objcopy(config)
    if objcopy:
        bin_file = os.path.splitext(elf)[0] + ".bin"
        subprocess.run([objcopy, "-O", "binary", elf, bin_file], check=True)
        _success(f"[+] BIN ready  : {bin_file}")
        print(f"    Next: quartus-workflow console load \"{bin_file}\" <base_addr>")
    else:
        print("  Note: riscv32-unknown-elf-objcopy not found — skipping .bin conversion")
        print(f"    ELF: {elf}")


def cmd_open_bsp(config, args):
    """Open Nios V BSP Editor GUI with the project settings.bsp."""
    editor = find_niosv_bsp_editor(config)
    if not editor:
        _error("niosv-bsp-editor not found.")
        _ver = config["tools"].get("quartus_version", "25.1")
        print(f"  Expected: C:\\altera_lite\\{_ver}std\\niosv\\bin\\niosv-bsp-editor.exe")
        print("  Set tools.niosv_base in hw_workflow.toml if installed elsewhere.")
        sys.exit(1)

    # niosv-bsp-editor is the same Java stack as niosv-bsp — needs QUARTUS_ROOTDIR
    # and SOPC_KIT_NIOS2 to locate the device DB (same as niosv-shell sets up).
    niosv_bin = os.path.dirname(os.path.abspath(editor))
    acds_root = os.path.dirname(os.path.dirname(niosv_bin))
    env = os.environ.copy()
    env["PATH"]            = niosv_bin + os.pathsep + env.get("PATH", "")
    env["QUARTUS_ROOTDIR"] = os.path.join(acds_root, "quartus")
    env["SOPC_KIT_NIOS2"]  = os.path.join(acds_root, "nios2eds")

    # --settings with no value → auto-detect; with value → use explicit path; absent → no file.
    settings_arg = getattr(args, "settings", None)
    cmd = [editor]
    if settings_arg is not None:
        if settings_arg:
            settings = os.path.abspath(settings_arg)
        else:
            bsp_dir  = config["files"].get("bsp_dir", "")
            sopcinfo = config["files"].get("sopcinfo", "")
            if not bsp_dir and sopcinfo:
                bsp_dir = os.path.join(os.path.dirname(sopcinfo), "software", "hal_bsp")
            settings = os.path.join(os.path.abspath(bsp_dir), "settings.bsp") if bsp_dir else ""
        if settings and os.path.isfile(settings):
            cmd += ["--settings", settings]
            print(f"\nOpening BSP Editor: {settings}")
        else:
            print(f"\nOpening BSP Editor (settings.bsp not found: {settings})")
    else:
        print("\nOpening BSP Editor")
    subprocess.Popen(cmd, env=env)   # non-blocking — GUI app


def cmd_open_niosv_shell(config, args):
    """Open the Nios V Command Shell with the Nios V toolchain environment."""
    shell = find_niosv_shell(config)
    if not shell:
        _error("niosv-shell not found.")
        _ver = config["tools"].get("quartus_version", "25.1")
        print(f"  Expected: C:\\altera_lite\\{_ver}std\\niosv\\bin\\niosv-shell.exe")
        print("  Set tools.niosv_base in hw_workflow.toml if installed elsewhere.")
        sys.exit(1)
    print("\nOpening Nios V Command Shell")
    subprocess.Popen([shell])   # non-blocking — opens interactive shell window


def cmd_open_ide(config, args):
    """Open Ashling RiscFree IDE for Altera FPGAs."""
    rf = find_riscfree(config)
    if not rf:
        _error("RiscFree IDE not found.")
        _ver = config["tools"].get("quartus_version", "25.1")
        print(f"  Expected: C:\\altera_lite\\{_ver}std\\riscfree\\RiscFree\\RiscFree.exe")
        print("  Set tools.riscfree in hw_workflow.toml if installed elsewhere.")
        sys.exit(1)
    ws = getattr(args, "workspace", None)
    cmd = [rf]
    if ws:
        cmd += ["-data", os.path.abspath(ws)]
    print("\nOpening Ashling RiscFree IDE for Altera FPGAs")
    subprocess.Popen(cmd)   # non-blocking — GUI app


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

COMMANDS = {
    "build":           cmd_build,
    "timing":          cmd_timing,
    "power":           cmd_power,
    "report":          cmd_report,
    "gen-pd":          cmd_gen_pd,
    "synth":           cmd_synth,
    "elab":            cmd_elab,
    "program":         cmd_program,
    "simulate":        cmd_simulate,
    "setup":           cmd_setup,
    "set-top":         cmd_set_top,
    "set-project":     cmd_set_project,
    "sync-top":        cmd_sync_top,
    "apply-pins":      cmd_apply_pins,
    "clean":           cmd_clean,
    "open-pd":         cmd_open_pd,
    "open-quartus":    cmd_open_quartus,
    "open-programmer": cmd_open_programmer,
    "open-timing":     cmd_open_timing,
    "console-scan":    cmd_console_scan,
    "console-peek":    cmd_console_peek,
    "console-poke":    cmd_console_poke,
    "console-load":    cmd_console_load,
    "gen-bsp":         cmd_gen_bsp,
    "gen-app":         cmd_gen_app,
    "build-app":       cmd_build_app,
    "open-bsp":          cmd_open_bsp,
    "open-niosv-shell":  cmd_open_niosv_shell,
    "open-riscfree":     cmd_open_ide,
}


def build_parser():
    """Construct and return the argument parser for all CLI subcommands."""
    parser = argparse.ArgumentParser(
        description="DE10-Lite HW workflow — Quartus build, program, simulate, and GUI tools",
        epilog="Paths are read from hw_workflow.toml [files] by default."
    )
    sub = parser.add_subparsers(dest="command", metavar="command")

    # build
    p_b = sub.add_parser("build",         help="Full Quartus compilation (map->fit->asm->sta) + summary")
    p_b.add_argument("--qpf", metavar="PATH",
                     help="Path to .qpf file (default: files.qpf in hw_workflow.toml)")

    # synth
    p_sy = sub.add_parser("synth",        help="Analysis & Synthesis only (quartus_map) — faster than full build")
    p_sy.add_argument("--qpf", metavar="PATH",
                      help="Path to .qpf file (default: files.qpf in hw_workflow.toml)")

    # elab
    p_el = sub.add_parser("elab",         help="HDL elaboration check only (quartus_map --analysis_and_elaboration)")
    p_el.add_argument("--qpf", metavar="PATH",
                      help="Path to .qpf file (default: files.qpf in hw_workflow.toml)")

    # report
    p_rp = sub.add_parser("report",
                          help="Print build summary (resources + Fmax) from existing .rpt files — no Quartus tool required")
    p_rp.add_argument("--qpf", metavar="PATH",
                      help="Path to .qpf file (default: files.qpf in hw_workflow.toml)")

    # power
    p_pw = sub.add_parser("power",
                          help="Run Power Analyzer (quartus_pow) and print total/dynamic/static power summary")
    p_pw.add_argument("--qpf", metavar="PATH",
                      help="Path to .qpf file (default: files.qpf in hw_workflow.toml)")
    p_pw.add_argument("--open-gui", action="store_true",
                      help="Open Quartus IDE Power Analyzer after analysis")

    # timing
    p_t = sub.add_parser("timing",        help="Run TimeQuest Timing Analyzer standalone and print Fmax summary")
    p_t.add_argument("--qpf", metavar="PATH",
                     help="Path to .qpf file (default: files.qpf in hw_workflow.toml)")
    p_t.add_argument("--open-gui", action="store_true",
                     help="Open TimeQuest Timing Analyzer GUI after analysis")

    # program
    p_pr = sub.add_parser("program",      help="Flash .sof to FPGA via quartus_pgm (JTAG)")
    p_pr.add_argument("--sof", metavar="PATH",
                      help="Path to .sof file (default: files.sof in hw_workflow.toml)")

    # simulate
    p_s = sub.add_parser("simulate",      help="Run VUnit tests via sim/run.py")
    p_s.add_argument("--simulator", metavar="SIM",
                     help="Simulator to use: ghdl or modelsim (default: tools.simulator in toml)")
    p_s.add_argument("extra", nargs=argparse.REMAINDER,
                     help="Extra arguments forwarded to run.py")

    # setup
    p_su = sub.add_parser("setup",
                          help="Scaffold a new project: .qpf + .qsf + top HDL + update hw_workflow.toml (add --pd for Platform Designer)")
    p_su.add_argument("name", help="Project name (creates quartus_workspace/<name>/)")
    p_su.add_argument("--lang", choices=["verilog", "vhdl"], default=None,
                      help="HDL language for top-level template (default: project.hdl_lang in toml)")
    p_su.add_argument("--pd", action="store_true",
                      help="Include Platform Designer system (.qsys) and QIP file reference in scaffold")
    p_su.add_argument("--pins", action="store_true",
                      help="Append DE10-Lite pin assignments from lib/board/de10_lite/assignments/")
    p_su.add_argument("--sdc", action="store_true",
                      help="Generate a minimal SDC timing-constraints file and add it to the .qsf")
    p_su.add_argument("--quartus", action="store_true",
                      help="Open Quartus Prime IDE after scaffold creation")

    # set-top
    p_st = sub.add_parser("set-top", help="Set TOP_LEVEL_ENTITY in project .qsf")
    p_st.add_argument("top", help="HDL file or entity name (e.g. my_top.vhd or my_top)")

    # set-project
    p_sp = sub.add_parser("set-project",  help="Set active project in hw_workflow.toml")
    p_sp.add_argument("name", help="Project directory name under quartus_workspace/")

    # sync-top
    sub.add_parser("sync-top",
                   help="Sync component declaration in top-level HDL from PD-generated _inst.vhd")

    # apply-pins
    sub.add_parser("apply-pins",
                   help="Append board pin assignments to project .qsf (board set in hw_workflow.toml)")

    # gen-pd
    p_gp = sub.add_parser("gen-pd",
                           help="Regenerate Platform Designer HDL from .qsys file (qsys-generate)")
    p_gp.add_argument("--qsys", metavar="PATH",
                      help="Path to .qsys file (default: files.qsys in hw_workflow.toml)")

    # clean
    p_cl = sub.add_parser("clean",
                          help="Delete compilation outputs (output_files/, db/, incremental_db/)")
    p_cl.add_argument("--keep-sof", action="store_true",
                      help="Preserve the .sof file so 'program' still works without rebuilding")
    p_cl.add_argument("--dry-run",  action="store_true",
                      help="Print files that would be deleted without removing them")

    # GUI launchers — grouped together
    p_q = sub.add_parser("open-quartus",  help="Open Quartus Prime IDE with project .qpf file")
    p_q.add_argument("--qpf", metavar="PATH",
                     help="Path to .qpf file (default: files.qpf in hw_workflow.toml)")

    p_p = sub.add_parser("open-pd",       help="Open Platform Designer with project .qsys file")
    p_p.add_argument("--qsys", metavar="PATH",
                     help="Path to .qsys file (default: files.qsys in hw_workflow.toml)")

    sub.add_parser("open-programmer",     help="Open Quartus Programmer GUI")
    sub.add_parser("open-timing",         help="Open TimeQuest Timing Analyzer GUI")

    p_bsp_ed = sub.add_parser("open-bsp",
                              help="Open Nios V BSP Editor GUI")
    p_bsp_ed.add_argument("--settings", nargs="?", const="", metavar="PATH",
                          help="Load settings.bsp on open; omit PATH to use default <bsp_dir>/settings.bsp")

    sub.add_parser("open-niosv-shell",
                   help="Open Nios V Command Shell with toolchain environment")

    p_ide = sub.add_parser("open-riscfree",
                           help="Open Ashling RiscFree IDE for Altera FPGAs")
    p_ide.add_argument("--workspace", metavar="PATH",
                       help="Eclipse workspace directory (-data <path>)")

    # console-* JTAG diagnostics
    sub.add_parser("console-scan",
                   help="JTAG: scan Avalon masters and devices")

    p_peek = sub.add_parser("console-peek",
                            help="JTAG: read 32-bit word from Avalon address")
    p_peek.add_argument("addr", help="Address (hex, e.g. 0x1000)")
    p_peek.add_argument("--master", metavar="PATH", default=None,
                        help="Avalon master service path (default: first available)")

    p_poke = sub.add_parser("console-poke",
                            help="JTAG: write 32-bit word to Avalon address")
    p_poke.add_argument("addr", help="Address (hex)")
    p_poke.add_argument("val",  help="Value (hex)")
    p_poke.add_argument("--master", metavar="PATH", default=None,
                        help="Avalon master service path (default: first available)")

    p_load = sub.add_parser("console-load",
                            help="JTAG: load .bin into Avalon memory")
    p_load.add_argument("bin",      nargs="?", default=None,
                        help="Path to .bin file (default: <app_dir>/build/app.bin)")
    p_load.add_argument("baseaddr", nargs="?", default=None,
                        help="Load address hex (default: parsed from bsp/system.h)")
    p_load.add_argument("--master", metavar="PATH", default=None,
                        help="Avalon master service path (default: first available)")

    # gen-bsp
    p_gb = sub.add_parser("gen-bsp",
                          help="Generate (or update) Nios V BSP from .sopcinfo (niosv-bsp)")
    p_gb.add_argument("--type", choices=["hal", "ucosii", "freertos"], default="hal",
                      help="BSP type (default: hal)")
    p_gb.add_argument("--bsp-dir", dest="bsp_dir", metavar="PATH",
                      help="BSP output directory (default: files.bsp_dir in hw_workflow.toml"
                           " or <sopcinfo-dir>/software/<type>_bsp)")

    # gen-app / build-app
    p_ga = sub.add_parser("gen-app",
                          help="Generate Nios V application CMakeLists.txt (niosv-app)")
    p_ga.add_argument("--bsp-dir", dest="bsp_dir", metavar="PATH",
                      help="BSP directory (default: files.bsp_dir or <sopcinfo-dir>/software/hal_bsp)")
    p_ga.add_argument("--app-dir", dest="app_dir", metavar="PATH",
                      help="App output directory (default: files.app_dir or <sopcinfo-dir>/software/app)")
    p_ga.add_argument("--srcs", metavar="PATH",
                      help="Source file or directory to include (default: app_dir)")

    p_ba = sub.add_parser("build-app",
                          help="Build Nios V app: cmake + make → .elf + .bin")
    p_ba.add_argument("--bsp-dir", dest="bsp_dir", metavar="PATH",
                      help="BSP directory (default: <sopcinfo-dir>/software/hal_bsp)")
    p_ba.add_argument("--app-dir", dest="app_dir", metavar="PATH",
                      help="App source directory with CMakeLists.txt (default: <sopcinfo-dir>/software/app)")
    p_ba.add_argument("--clean", action="store_true",
                      help="Delete build dir before building (non-interactive)")

    return parser


def main():
    """Entry point: parse arguments, load config, and dispatch to the command handler."""
    parser = build_parser()
    args   = parser.parse_args()
    config = load_config()
    if not args.command:
        parser.print_help()
        sys.exit(0)
    COMMANDS[args.command](config, args)


if __name__ == "__main__":
    main()
