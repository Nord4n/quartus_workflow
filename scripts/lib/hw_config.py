"""
hw_config.py — Load and validate hw_workflow.toml for the HW module.

Locates hw_workflow.toml relative to this file's location (HW/scripts/lib/ →
HW/). Falls back to workflow.toml in the parent directory (repo root) for
backwards compatibility while transitioning.

Part of the HW module (hw_workflow.py).

Author  : Erik Nordahl
Date    : 2026-03-18
Version : 1.0
"""

import os
import sys


def _print_warn(msg):
    """Print msg in magenta when stdout is a TTY, plain otherwise."""
    if sys.stdout.isatty():
        print(f"\033[35m{msg}\033[0m")
    else:
        print(msg)

_LIB_DIR    = os.path.dirname(os.path.abspath(__file__))   # HW/scripts/lib/
_SCRIPTS_DIR = os.path.dirname(_LIB_DIR)                   # HW/scripts/
HW_DIR      = os.path.dirname(_SCRIPTS_DIR)                # HW/
REPO_ROOT   = os.path.dirname(HW_DIR)                      # repo root

HW_TOML     = os.path.join(HW_DIR,   "hw_workflow.toml")
SW_TOML     = os.path.join(REPO_ROOT, "workflow.toml")     # fallback

try:
    import tomllib                      # Python 3.11+ stdlib
except ImportError:
    try:
        import tomli as tomllib         # pip install tomli
    except ImportError:
        tomllib = None


def load_config(path=None):
    """Load hw_workflow.toml and return a config dict with defaults applied.

    Search order:
      1. Explicit path argument (if provided)
      2. hw_workflow.toml next to hw_workflow.py (HW/)
      3. workflow.toml in repo root (backwards-compat fallback)

    If no config is found, or tomllib is unavailable, returns built-in defaults.
    """
    if tomllib is None:
        _print_warn("[!] WARNING: tomllib not available (requires Python 3.11+ or 'pip install tomli')")
        _print_warn("[!] Using built-in defaults.")
        return _defaults()

    if path is None:
        if os.path.exists(HW_TOML):
            path = HW_TOML
        elif os.path.exists(SW_TOML):
            _print_warn(f"[!] hw_workflow.toml not found — falling back to {SW_TOML}")
            path = SW_TOML
        else:
            _print_warn(f"[!] No config found (tried {HW_TOML} and {SW_TOML})")
            _print_warn("[!] Using built-in defaults.")
            return _defaults()

    with open(path, "rb") as f:
        raw = tomllib.load(f)

    return _apply_defaults(raw)


def _defaults():
    """Return a complete config dict with sensible defaults."""
    return {
        "tools": {
            "quartus_version": "25.1",
            "device":          "10M50DAF484C7G",
            "board":           "de10-lite",
            "quartus_base":    "",
            "system_console":  "",
            "nios2_terminal":  "",
            "niosv_base":      "",
            "riscfree":        "",
        },
        "project": {
            "name":     "",
            "hdl_lang": "vhdl",
        },
        "files": {
            "qpf":      "",
            "qsys":     "",
            "sof":      "",
            "sopcinfo": "",
            "bsp_dir":  "",
            "app_dir":  "",
        },
    }


def _apply_defaults(raw):
    """Fill in any missing keys from defaults."""
    defaults = _defaults()
    for section, values in defaults.items():
        if section not in raw:
            raw[section] = values
        else:
            for key, val in values.items():
                if key not in raw[section]:
                    raw[section][key] = val

    # Resolve [files] paths relative to HW_DIR
    for key in ("qpf", "qsys", "sof", "sopcinfo", "bsp_dir", "app_dir"):
        val = raw["files"].get(key, "")
        if val and not os.path.isabs(val):
            raw["files"][key] = os.path.join(HW_DIR, val)

    return raw
