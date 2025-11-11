@echo off
@REM Ensure dist exists
git clean -fdx

@REM Building the exe
call pyinstaller --noconsole --clean --onefile --add-data "img;img" --icon="img/favicon.ico" get_payout.py

