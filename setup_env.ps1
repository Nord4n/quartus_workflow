# setup_env.ps1 - One-time environment setup for hw-workflow (Windows)
#
# Usage (from HW\ in PowerShell):
#   powershell -ExecutionPolicy Bypass -File setup_env.ps1
#   # or, if script execution is already enabled:
#   .\setup_env.ps1
#
# Checks all prerequisites for hw_workflow.py. Any tools found in standard
# locations but not yet on the user PATH are added permanently (User scope).
# Re-running is safe - the script is idempotent.
#
# After running: open a new terminal for PATH changes to take effect.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$HW_DIR      = $PSScriptRoot
$TOML        = Join-Path $HW_DIR "hw_workflow.toml"
$MISSING        = [System.Collections.Generic.List[string]]::new()
$PATHS_ADDED    = [System.Collections.Generic.List[string]]::new()
$ProfileUpdated = $false

# -- Output helpers -----------------------------------------------------------

function Write-OK     { param($msg) Write-Host ("  {0,-12}{1}" -f "[OK]",      $msg) -ForegroundColor Green  }
function Write-Found  { param($msg) Write-Host ("  {0,-12}{1}" -f "[FOUND]",   $msg) -ForegroundColor Cyan   }
function Write-NA     { param($msg) Write-Host ("  {0,-12}{1}" -f "[N/A]",     $msg) -ForegroundColor Gray   }
function Write-Miss   { param($msg) Write-Host ("  {0,-12}{1}" -f "[MISSING]", $msg) -ForegroundColor Red    }
function Write-Warn   { param($msg) Write-Host ("  {0,-12}{1}" -f "[WARN]",    $msg) -ForegroundColor Yellow }

# Appends a PATH-refresh snippet to $PROFILE.CurrentUserAllHosts if not already present.
# This ensures all future PowerShell terminals (including VSCode) pick up registry PATH changes.
function Update-PowerShellProfile {
    $prof   = $PROFILE.CurrentUserAllHosts
    $marker = "[hw-workflow]"
    $snippet = @"

# $marker Refresh PATH from Windows registry on shell startup
`$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" +
             [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
"@
    $existing = if (Test-Path $prof) { Get-Content $prof -Raw } else { "" }
    if ($existing -notlike "*$marker*") {
        $profDir = Split-Path $prof
        if (-not (Test-Path $profDir)) { New-Item -ItemType Directory -Path $profDir | Out-Null }
        Add-Content -Path $prof -Value $snippet -Encoding UTF8
        $script:ProfileUpdated = $true
        Write-Found "PowerShell profile  ->  $prof"
    } else {
        Write-OK "PowerShell profile  (PATH refresh already present)"
    }
}

# Adds $dir to the user PATH if not already present. Prints status.
function Add-ToUserPath {
    param([string]$Dir, [string]$Label)
    $userPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
    if ($null -eq $userPath) { $userPath = "" }
    $syspath  = [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
    if ($null -eq $syspath)  { $syspath  = "" }
    $combined = "$userPath;$syspath"
    if ($combined -split ";" -contains $Dir) {
        Write-OK "$Label"
        return
    }
    $newPath = ($userPath.TrimEnd(";") + ";" + $Dir).TrimStart(";")
    [System.Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
    $PATHS_ADDED.Add($Dir)
    Write-Found "$Label  ->  $Dir"
}

# -- Banner -------------------------------------------------------------------

Write-Host "================================================"
Write-Host "  hw-workflow - Environment Setup"
Write-Host "================================================"

# -- Read quartus_version from hw_workflow.toml -------------------------------

$QUARTUS_VER = "25.1"
if (Test-Path $TOML) {
    $match = Select-String -Path $TOML -Pattern 'quartus_version\s*=\s*"([^"]+)"'
    if ($match) { $QUARTUS_VER = $match.Matches[0].Groups[1].Value }
}
Write-Host "Quartus version : $QUARTUS_VER"
Write-Host ""
Write-Host "Checking prerequisites..."

# -- Python 3.11+ -------------------------------------------------------------

$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    $pyVer = & python -c "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>$null
    $pyMin = & python -c "import sys; print(1 if sys.version_info >= (3,11) else (0 if sys.version_info < (3,8) else 2))" 2>$null
    if ($pyMin -eq "1") {
        Write-OK "python $pyVer"
    } elseif ($pyMin -eq "2") {
        Write-Warn "python $pyVer  (3.11+ recommended; run: pip install tomli)"
    } else {
        Write-Miss "python $pyVer  (3.8+ required)"
        $MISSING.Add("python >= 3.8  (python.org/downloads)")
    }
} else {
    Write-Miss "python  (not found)"
    $MISSING.Add("python >= 3.8  (python.org/downloads)")
}

# -- Quartus bin64  (quartus_pgm / quartus_sh) --------------------------------

$BIN64_DIRS = @(
    "C:\intelFPGA_lite\$QUARTUS_VER\quartus\bin64",
    "C:\altera_lite\${QUARTUS_VER}std\quartus\bin64",
    "C:\altera_lite\$QUARTUS_VER\quartus\bin64",
    "C:\intelFPGA\$QUARTUS_VER\quartus\bin64",
    "C:\altera\${QUARTUS_VER}std\quartus\bin64"
)

$pgm = Get-Command quartus_pgm.exe -ErrorAction SilentlyContinue
if ($pgm) {
    Write-OK "quartus_pgm"
} else {
    $found = $BIN64_DIRS | Where-Object { Test-Path "$_\quartus_pgm.exe" } | Select-Object -First 1
    if ($found) {
        Add-ToUserPath $found "quartus_pgm"
    } else {
        Write-Miss "quartus_pgm  (Quartus $QUARTUS_VER not found)"
        $MISSING.Add("Quartus Prime Lite $QUARTUS_VER  (intel.com -> FPGA Software)")
    }
}

# -- Nios V tools (niosv-bsp / niosv-app / niosv-download) -------------------

$NIOSV_DIRS = @(
    "C:\altera_lite\${QUARTUS_VER}std\niosv\bin",
    "C:\altera_lite\$QUARTUS_VER\niosv\bin",
    "C:\intelFPGA_lite\$QUARTUS_VER\niosv\bin"
)

$niosvBsp = Get-Command niosv-bsp.exe -ErrorAction SilentlyContinue
if ($niosvBsp) {
    Write-OK "niosv-bsp"
} else {
    $found = $NIOSV_DIRS | Where-Object { Test-Path "$_\niosv-bsp.exe" } | Select-Object -First 1
    if ($found) {
        Add-ToUserPath $found "niosv-bsp"
    } else {
        Write-NA "niosv-bsp  (optional; requires Quartus $QUARTUS_VER with Nios V support)"
    }
}

# -- RiscFree cmake and make (optional - Nios V app build) --------------------

$RISCFREE_BASE = @(
    "C:\altera_lite\${QUARTUS_VER}std\riscfree",
    "C:\altera_lite\$QUARTUS_VER\riscfree",
    "C:\intelFPGA_lite\$QUARTUS_VER\riscfree"
)

$cmake = Get-Command cmake.exe -ErrorAction SilentlyContinue
if ($cmake) {
    Write-OK "cmake"
} else {
    $found = $RISCFREE_BASE | ForEach-Object { "$_\build_tools\cmake\bin" } |
             Where-Object { Test-Path "$_\cmake.exe" } | Select-Object -First 1
    if ($found) { Add-ToUserPath $found "cmake" }
    else { Write-NA "cmake  (optional; install cmake.org or Quartus $QUARTUS_VER with RiscFree)" }
}

$make = Get-Command make.exe -ErrorAction SilentlyContinue
if ($make) {
    Write-OK "make"
} else {
    $found = $RISCFREE_BASE | ForEach-Object { "$_\build_tools\bin" } |
             Where-Object { Test-Path "$_\make.exe" } | Select-Object -First 1
    if ($found) { Add-ToUserPath $found "make" }
    else { Write-NA "make  (optional; install via RiscFree build_tools or mingw32-make)" }
}

# -- GHDL  (optional - WSL simulation) ----------------------------------------

$ghdl = Get-Command ghdl.exe -ErrorAction SilentlyContinue
if ($ghdl) {
    $ghdlVer = (& ghdl.exe --version 2>$null | Select-Object -First 1) -replace ".*?(\d+\.\d+[\d.]*).*", '$1'
    Write-OK "ghdl $ghdlVer"
} else {
    Write-NA "ghdl  (optional; install for simulation: github.com/ghdl/ghdl/releases)"
}

# -- VUnit  (optional - HDL testbench framework) ------------------------------

$vuCheck = $null
try { $vuCheck = & python -c "import vunit; print(vunit.__version__)" 2>$null } catch { }
if ($LASTEXITCODE -eq 0 -and $vuCheck) {
    Write-OK "vunit $vuCheck"
} else {
    Write-NA "vunit  (optional; install: pip install vunit-hdl)"
}

# -- quartus-workflow CLI wrapper ---------------------------------------------

$BIN_DIR = Join-Path $HW_DIR "bin"
if (Test-Path "$BIN_DIR\quartus-workflow.bat") {
    Add-ToUserPath $BIN_DIR "quartus-workflow"
}

# -- PowerShell execution policy ----------------------------------------------

$userPolicy = Get-ExecutionPolicy -Scope CurrentUser
if ($userPolicy -in @("Restricted", "AllSigned", "Undefined")) {
    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force -ErrorAction SilentlyContinue
    $setPolicy = Get-ExecutionPolicy -Scope CurrentUser
    Write-Found "Execution policy  ->  $setPolicy  (was: $userPolicy)"
} else {
    Write-OK "Execution policy  ($userPolicy)"
}

# -- PowerShell profile -------------------------------------------------------

Update-PowerShellProfile

# -- Summary ------------------------------------------------------------------

Write-Host ""

if ($PATHS_ADDED.Count -gt 0) {
    Write-Host "Added $($PATHS_ADDED.Count) path(s) to user PATH."
    Write-Host ""
    Write-Host "  Open a new terminal for PATH changes to take effect."
} else {
    Write-Host "All found tools are already on PATH - no changes made."
}

$profHasMarker = (Test-Path $PROFILE.CurrentUserAllHosts) -and
                 ((Get-Content $PROFILE.CurrentUserAllHosts -Raw) -like "*[hw-workflow]*")
if ($profHasMarker) {
    Write-Host ""
    Write-Host "  -> Open a new terminal window for PATH changes to take effect."
    Write-Host "  -> Restart VSCode to apply profile changes to its integrated terminal."
}

if ($MISSING.Count -gt 0) {
    Write-Host ""
    Write-Host "The following tools must be installed manually:"
    foreach ($t in $MISSING) { Write-Host "  - $t" }
}

Write-Host ""
Write-Host "================================================"
