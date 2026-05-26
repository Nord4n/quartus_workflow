#!/usr/bin/env python3
"""
VUnit HDL test runner for HW/lib/IPs modules.

Recommended simulator (WSL):
  GHDL — native Linux, no path-translation issues with WSL.
  Install: sudo apt install ghdl
  Run:     VUNIT_SIMULATOR=ghdl python3 HW/sim/run.py

Note: Questa FSE (Quartus 25.1) is a Windows executable. When called from WSL,
VUnit passes Linux paths that Questa cannot resolve (vlib fails). Use GHDL in
WSL environments; Questa works only when run from a native Windows shell.

Run from repo root or HW/sim/:
  python3 HW/sim/run.py
  python3 HW/sim/run.py --list                        # list all tests
  python3 HW/sim/run.py lib.tb_jtag_reset_pulse       # run one testbench
"""

from pathlib import Path
from vunit import VUnit

ROOT = Path(__file__).parent.parent  # repo root (or HW/ when used as a submodule)

vu = VUnit.from_argv()

lib = vu.add_library("lib")
lib.add_source_files(ROOT / "lib/IPs/jtag_reset_pulse/hdl/*.vhd")
lib.add_source_files(ROOT / "lib/IPs/jtag_reset_pulse/tb/*.vhd")

vu.main()
