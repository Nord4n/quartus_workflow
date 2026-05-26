"""
quartus_tools.py — Intel/Quartus-specific tool discovery and path helpers.

Copied from SW/scripts/lib/intel/quartus_tools.py for standalone use in the
HW module (hw_workflow.py). Keep in sync with the SW version when updating.

Exports:
  _to_win_path(p)              Convert WSL /mnt/<drive>/... path to Windows drive path
  find_quartus_pgm(config)     Locate quartus_pgm executable
  find_quartus_asm(config)     Locate quartus_asm executable (Assembler)
  find_system_console(config)  Locate system-console executable
  find_nios2_terminal(config)  Locate nios2-terminal executable
  find_niosv_bsp(config)        Locate niosv-bsp executable (Nios V BSP generator)
  find_niosv_app(config)        Locate niosv-app executable (Nios V app project generator)
  find_niosv_bsp_editor(config) Locate niosv-bsp-editor executable (BSP Editor GUI)
  find_niosv_shell(config)      Locate niosv-shell executable (Nios V Command Shell)
  find_riscfree(config)         Locate Ashling RiscFree IDE executable
  find_cmake(config)            Locate cmake executable (from RiscFree build_tools or PATH)
  find_make(config)             Locate make executable (from RiscFree build_tools or PATH)
  find_objcopy(config)          Locate riscv32-unknown-elf-objcopy (from RiscFree toolchain or PATH)
"""

import os
import shutil
import sys


def _to_win_path(p):
    """Convert a WSL /mnt/<drive>/... path to a Windows drive path.

    Windows executables (quartus_pgm.exe, system-console.exe) invoked from WSL
    cannot resolve /mnt/c/... paths; they need C:\\... style paths.
    """
    if p and p.startswith("/mnt/"):
        parts = p.split("/")   # ['', 'mnt', 'c', ...]
        return parts[2].upper() + ":\\" + "\\".join(parts[3:])
    return p


def _quartus_default_dirs(version):
    """Return candidate Quartus bin64 directories, most likely first.

    Handles directory naming differences across Quartus versions:
      Intel 18.x–21.x: /mnt/c/intelFPGA_lite/{version}/quartus/bin64
      Altera 25.x Lite: /mnt/c/altera_lite/{version}std/quartus/bin64
    """
    return [
        f"/mnt/c/intelFPGA_lite/{version}/quartus/bin64",  # 18.x–21.x Lite
        f"/mnt/c/altera_lite/{version}std/quartus/bin64",  # 25.x Lite
        f"/mnt/c/altera_lite/{version}/quartus/bin64",     # 25.x no-suffix
        f"/mnt/c/intelFPGA/{version}/quartus/bin64",       # Pro/Standard
        f"/mnt/c/altera/{version}std/quartus/bin64",       # 25.x Pro
    ]


def _find_tool(tool_name, config_override, quartus_version, exe_names):
    """Locate a Quartus tool binary.

    Search order:
      1. config_override from workflow.toml (if set)
      2. shutil.which (PATH)
      3. Default install paths based on quartus_version (multiple naming patterns)
    """
    if config_override:
        candidate = os.path.join(config_override, exe_names[0])
        if os.path.isfile(candidate):
            return candidate
        if len(exe_names) > 1:
            candidate = os.path.join(config_override, exe_names[1])
            if os.path.isfile(candidate):
                return candidate

    for name in exe_names:
        found = shutil.which(name)
        if found:
            return found

    for default_dir in _quartus_default_dirs(quartus_version):
        for name in exe_names:
            candidate = os.path.join(default_dir, name)
            if os.path.isfile(candidate):
                return candidate

    return None


def _find_bin64_tool(label, exe_names, override, version):
    """Locate a Quartus bin64 tool, checking version-specific dirs before PATH.

    Search order:
      1. config_override directory from hw_workflow.toml (if set)
      2. Default install dirs derived from quartus_version
      3. shutil.which (PATH) as a last-resort fallback

    Returns the full path string, or None if not found.
    """
    if override:
        for name in exe_names:
            candidate = os.path.join(override, name)
            if os.path.isfile(candidate):
                return candidate

    for default_dir in _quartus_default_dirs(version):
        for name in exe_names:
            candidate = os.path.join(default_dir, name)
            if os.path.isfile(candidate):
                return candidate

    for name in exe_names:
        found = shutil.which(name)
        if found:
            return found

    return None


def find_quartus_pgm(config):
    override = config["tools"].get("quartus_base", "")
    version  = config["tools"].get("quartus_version", "25.1")
    tool = _find_bin64_tool("quartus_pgm", ["quartus_pgm", "quartus_pgm.exe"],
                            override, version)
    if not tool:
        print("ERROR: quartus_pgm not found!")
        print("Solutions:")
        print("  1. Add Quartus bin64/ to your PATH, or")
        print("  2. Set tools.quartus_base in hw_workflow.toml")
        sys.exit(1)
    print(f"[*] Quartus pgm   : {tool}")
    return tool


def find_quartus_asm(config):
    """Locate the Quartus Assembler (quartus_asm) executable."""
    override = config["tools"].get("quartus_base", "")
    version  = config["tools"].get("quartus_version", "25.1")
    tool = _find_bin64_tool("quartus_asm", ["quartus_asm", "quartus_asm.exe"],
                            override, version)
    if not tool:
        print("ERROR: quartus_asm not found!")
        print("Solutions:")
        print("  1. Add Quartus bin64/ to your PATH, or")
        print("  2. Set tools.quartus_base in hw_workflow.toml")
        sys.exit(1)
    print(f"[*] Quartus asm   : {tool}")
    return tool


def _quartus_sopc_dirs(version):
    """Return candidate quartus/sopc_builder/bin directories for system-console and qsys-edit."""
    return [
        # Windows-native paths (primary on Windows)
        f"C:\\altera_lite\\{version}std\\quartus\\sopc_builder\\bin",
        f"C:\\intelFPGA_lite\\{version}\\quartus\\sopc_builder\\bin",
        f"C:\\altera_lite\\{version}\\quartus\\sopc_builder\\bin",
        f"C:\\intelFPGA\\{version}\\quartus\\sopc_builder\\bin",
        # WSL paths
        f"/mnt/c/intelFPGA_lite/{version}/quartus/sopc_builder/bin",
        f"/mnt/c/altera_lite/{version}std/quartus/sopc_builder/bin",
        f"/mnt/c/altera_lite/{version}/quartus/sopc_builder/bin",
        f"/mnt/c/intelFPGA/{version}/quartus/sopc_builder/bin",
    ]


def find_system_console(config):
    override = config["tools"].get("system_console", "")
    version  = config["tools"].get("quartus_version", "25.1")

    if override:
        for name in ["system-console", "system-console.exe"]:
            candidate = os.path.join(override, name)
            if os.path.isfile(candidate):
                print(f"[*] System console: {candidate}")
                return candidate

    for default_dir in _quartus_sopc_dirs(version):
        for name in ["system-console", "system-console.exe"]:
            candidate = os.path.join(default_dir, name)
            if os.path.isfile(candidate):
                print(f"[*] System console: {candidate}")
                return candidate

    for name in ["system-console", "system-console.exe"]:
        found = shutil.which(name)
        if found:
            print(f"[*] System console: {found}")
            return found

    print("ERROR: system-console not found!")
    print("Solutions:")
    print("  1. Add quartus/sopc_builder/bin/ to your PATH, or")
    print("  2. Set tools.system_console in hw_workflow.toml")
    sys.exit(1)


def find_nios2_terminal(config):
    override = config["tools"].get("nios2_terminal", "")
    if override and os.path.exists(override):
        return override
    found = shutil.which("nios2-terminal.exe")
    if found:
        return found
    version = config["tools"].get("quartus_version", "25.1")
    for default in [
        f"/mnt/c/intelFPGA_lite/{version}/nios2eds/bin/nios2-terminal.exe",
        f"/mnt/c/altera_lite/{version}std/nios2eds/bin/nios2-terminal.exe",
        f"/mnt/c/altera_lite/{version}/nios2eds/bin/nios2-terminal.exe",
    ]:
        if os.path.exists(default):
            return default
    return None


def _niosv_default_dirs(version):
    """Return candidate niosv/bin directories for Nios V command-line tools.

    Nios V tools (niosv-bsp, niosv-app, niosv-download) are installed under
    <Quartus root>/niosv/bin/, separate from the Quartus bin64/ directory.
    """
    return [
        f"C:\\altera_lite\\{version}std\\niosv\\bin",
        f"C:\\altera_lite\\{version}\\niosv\\bin",
        f"C:\\intelFPGA_lite\\{version}\\niosv\\bin",
    ]


def find_niosv_bsp(config):
    """Locate the niosv-bsp executable (Nios V BSP generator)."""
    override  = config["tools"].get("niosv_base", "")
    version   = config["tools"].get("quartus_version", "25.1")
    exe_names = ["niosv-bsp", "niosv-bsp.exe"]

    if override:
        for name in exe_names:
            candidate = os.path.join(override, name)
            if os.path.isfile(candidate):
                print(f"[*] niosv-bsp      : {candidate}")
                return candidate

    for default_dir in _niosv_default_dirs(version):
        for name in exe_names:
            candidate = os.path.join(default_dir, name)
            if os.path.isfile(candidate):
                print(f"[*] niosv-bsp      : {candidate}")
                return candidate

    for name in exe_names:
        found = shutil.which(name)
        if found:
            print(f"[*] niosv-bsp      : {found}")
            return found

    print("ERROR: niosv-bsp not found!")
    print("Solutions:")
    print("  1. Install Quartus Prime Lite 25.x (includes Nios V tools in niosv/bin), or")
    print("  2. Set tools.niosv_base in hw_workflow.toml")
    sys.exit(1)


def find_niosv_app(config):
    """Locate the niosv-app executable (Nios V application project generator)."""
    override  = config["tools"].get("niosv_base", "")
    version   = config["tools"].get("quartus_version", "25.1")
    exe_names = ["niosv-app", "niosv-app.exe"]

    if override:
        for name in exe_names:
            candidate = os.path.join(override, name)
            if os.path.isfile(candidate):
                print(f"[*] niosv-app      : {candidate}")
                return candidate

    for default_dir in _niosv_default_dirs(version):
        for name in exe_names:
            candidate = os.path.join(default_dir, name)
            if os.path.isfile(candidate):
                print(f"[*] niosv-app      : {candidate}")
                return candidate

    for name in exe_names:
        found = shutil.which(name)
        if found:
            print(f"[*] niosv-app      : {found}")
            return found

    print("ERROR: niosv-app not found!")
    print("  Install Quartus Prime Lite 25.x or set tools.niosv_base in hw_workflow.toml")
    sys.exit(1)


def find_niosv_bsp_editor(config):
    """Locate the niosv-bsp-editor executable (Nios V BSP Editor GUI).

    Returns the full path string, or None if not found (caller decides).
    """
    override  = config["tools"].get("niosv_base", "")
    version   = config["tools"].get("quartus_version", "25.1")
    exe_names = ["niosv-bsp-editor", "niosv-bsp-editor.exe"]

    if override:
        for name in exe_names:
            candidate = os.path.join(override, name)
            if os.path.isfile(candidate):
                return candidate

    for default_dir in _niosv_default_dirs(version):
        for name in exe_names:
            candidate = os.path.join(default_dir, name)
            if os.path.isfile(candidate):
                return candidate

    for name in exe_names:
        found = shutil.which(name)
        if found:
            return found

    return None


def find_niosv_shell(config):
    """Locate the niosv-shell executable (Nios V Command Shell).

    Returns the full path string, or None if not found (caller decides).
    """
    override  = config["tools"].get("niosv_base", "")
    version   = config["tools"].get("quartus_version", "25.1")
    exe_names = ["niosv-shell", "niosv-shell.exe"]

    if override:
        for name in exe_names:
            candidate = os.path.join(override, name)
            if os.path.isfile(candidate):
                return candidate

    for default_dir in _niosv_default_dirs(version):
        for name in exe_names:
            candidate = os.path.join(default_dir, name)
            if os.path.isfile(candidate):
                return candidate

    for name in exe_names:
        found = shutil.which(name)
        if found:
            return found

    return None


def find_riscfree(config):
    """Locate the Ashling RiscFree IDE executable.

    Returns the full path string, or None if not found (caller decides whether
    to error or warn — IDE is optional).
    """
    override  = config["tools"].get("riscfree", "")
    version   = config["tools"].get("quartus_version", "25.1")
    candidates = [
        f"C:\\altera_lite\\{version}std\\riscfree\\RiscFree\\RiscFree.exe",
        f"C:\\altera_lite\\{version}\\riscfree\\RiscFree\\RiscFree.exe",
        f"C:\\intelFPGA_lite\\{version}\\riscfree\\RiscFree\\RiscFree.exe",
    ]
    if override:
        candidates.insert(0, override)

    for path in candidates:
        if os.path.isfile(path):
            print(f"[*] RiscFree IDE   : {path}")
            return path

    for name in ["RiscFree", "RiscFree.exe"]:
        found = shutil.which(name)
        if found:
            print(f"[*] RiscFree IDE   : {found}")
            return found

    return None


def _riscfree_build_dirs(version):
    return [
        f"C:\\altera_lite\\{version}std\\riscfree\\build_tools",
        f"C:\\altera_lite\\{version}\\riscfree\\build_tools",
        f"C:\\intelFPGA_lite\\{version}\\riscfree\\build_tools",
    ]


def find_cmake(config):
    """Locate cmake executable (from Ashling RiscFree build_tools or system PATH)."""
    version = config["tools"].get("quartus_version", "25.1")
    for build_tools in _riscfree_build_dirs(version):
        candidate = os.path.join(build_tools, "cmake", "bin", "cmake.exe")
        if os.path.isfile(candidate):
            return candidate
    return shutil.which("cmake") or shutil.which("cmake.exe")


def find_make(config):
    """Locate make executable (from Ashling RiscFree build_tools or system PATH)."""
    version = config["tools"].get("quartus_version", "25.1")
    for build_tools in _riscfree_build_dirs(version):
        candidate = os.path.join(build_tools, "bin", "make.exe")
        if os.path.isfile(candidate):
            return candidate
    return shutil.which("make") or shutil.which("mingw32-make")


def find_objcopy(config):
    """Locate riscv32-unknown-elf-objcopy (from Ashling RiscFree toolchain or system PATH)."""
    version = config["tools"].get("quartus_version", "25.1")
    tc_dirs = [
        f"C:\\altera_lite\\{version}std\\riscfree\\toolchain\\riscv32-unknown-elf\\bin",
        f"C:\\altera_lite\\{version}\\riscfree\\toolchain\\riscv32-unknown-elf\\bin",
        f"C:\\intelFPGA_lite\\{version}\\riscfree\\toolchain\\riscv32-unknown-elf\\bin",
    ]
    for d in tc_dirs:
        candidate = os.path.join(d, "riscv32-unknown-elf-objcopy.exe")
        if os.path.isfile(candidate):
            return candidate
    return shutil.which("riscv32-unknown-elf-objcopy")
