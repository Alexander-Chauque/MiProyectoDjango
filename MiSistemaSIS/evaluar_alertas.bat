@echo off
rem Ejecuta las reglas programadas de notificaciones (comandas demoradas y cajas abiertas)
cd /d "%~dp0"
if not exist logs mkdir logs
"%~dp0venv_311\Scripts\python.exe" manage.py evaluar_alertas >> logs\alertas.log 2>&1
