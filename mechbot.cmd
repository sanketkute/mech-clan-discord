@echo off
rem Short command for the laptop (owner's request, 2026-11-02). The repo folder is on the user's PATH, so in any
rem new terminal: "mechbot" (is it working?), "mechbot restart" or "mechbot log". See bot\status.py.
"%~dp0.venv\Scripts\python.exe" "%~dp0bot\status.py" %*
