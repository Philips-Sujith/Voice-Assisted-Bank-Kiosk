@echo off
setlocal
pushd "%~dp0"
call "%~dp0scripts\STOP_DEMO.bat" %*
popd
