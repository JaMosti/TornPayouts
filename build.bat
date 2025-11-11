@echo off
@REM Ensure dist exists
git clean -fdx

@REM Building the exe
call pyinstaller --noconsole --clean --onefile --add-data "img;img" --add-data "util;util" --icon="img/icon.ico" get_payout.py

