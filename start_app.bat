@echo off
cd /d "%~dp0"
call new_env\Scripts\activate
start /b python app.py
start http://127.0.0.1:5000