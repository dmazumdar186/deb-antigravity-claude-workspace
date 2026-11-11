@echo off
rem LC fail: double-click when a LinkedIn connect day went wrong (or tell Claude "LC fail").
rem Shows what happened, pulls the latest job files, signs in to LinkedIn only if needed,
rem re-registers the scheduled task and starts today's run (a day already emailed stays a no-op).
cd /d "%~dp0"
py -m pip install --quiet --upgrade playwright python-dotenv
py "execution\personal_workflows\linkedin_connect_send.py" fix
echo.
echo Exit code %ERRORLEVEL% (0 = repaired and started). This window can be closed.
pause
