@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "tools\pipeline_web\start_pipeline_web.ps1"
