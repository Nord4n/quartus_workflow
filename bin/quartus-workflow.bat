@echo off
:: quartus-workflow.bat -- thin wrapper that invokes hw_workflow.py from any directory.
set PYTHONUTF8=1
::
:: Added to PATH by setup_env.ps1. After running setup_env.ps1 and opening a
:: new terminal, 'quartus-workflow <command>' is equivalent to
:: 'python hw_workflow.py <command>' and can be called from any directory.
for %%I in ("%~dp0..") do set "HW_DIR=%%~fI"
python "%HW_DIR%\hw_workflow.py" %*
