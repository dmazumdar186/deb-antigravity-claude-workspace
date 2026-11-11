@echo off
rem LC fail: double-click when a LinkedIn connect day went wrong (or tell Claude "LC fail").
rem Shows what happened, pulls the latest job files, signs in to LinkedIn only if needed,
rem re-registers the scheduled task and starts today's run (a day already emailed stays a no-op).
rem Everything is inside one ( ) block: cmd.exe reads the whole block before running it, so the job
rem updating this file while the window is open cannot change what runs.
(
  cd /d "%~dp0"
  py -m pip install --quiet --upgrade playwright python-dotenv
  py "execution\personal_workflows\linkedin_connect_send.py" fix
  if errorlevel 1 (echo. & echo Something still needs you: read the lines above.) else (echo. & echo Repaired; today's run has started.)
  echo This window can be closed.
  pause
  exit /b
)
