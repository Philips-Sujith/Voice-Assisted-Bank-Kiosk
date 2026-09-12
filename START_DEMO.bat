@echo off
setlocal
pushd "%~dp0"
call "%~dp0scripts\START_DEMO.bat" %*
popd
