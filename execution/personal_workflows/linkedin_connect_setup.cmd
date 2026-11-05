@echo off
rem One-time setup for the LinkedIn connect job (directive: directives/personal_workflows/linkedin_connect_send.md).
rem Double-click. Installs the two packages, asks you to sign in to LinkedIn once (window closes by itself),
rem registers the "LinkedIn connect send" task (Mon Tue Thu Fri Sat 10:00) and starts today's run.
cd /d "%~dp0..\.."
py -m pip install --quiet --upgrade playwright python-dotenv
py "execution\personal_workflows\linkedin_connect_send.py" setup --start
echo.
echo Exit code %ERRORLEVEL% (0 = registered and started). This window can be closed.
pause
