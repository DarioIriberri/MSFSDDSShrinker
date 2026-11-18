@echo off
set "SKIP_EXCLUDES=True"
if not "%~1"=="" set "SKIP_EXCLUDES=%~1"
python DDSShrinkerOK.py %SKIP_EXCLUDES%