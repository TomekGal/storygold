@echo off
REM Windows verifier entry point (Harbor: [environment].os = "windows").
REM Grades via COM against a running, licensed SolidWorks session
REM (pywin32 required): the candidate passed as %1, or the currently
REM active document when no argument is given. Prints the JSON score
REM envelope from common/harness_base.py finalize() to stdout.
python "%~dp0task\harness\harness.py" %*
exit /b %errorlevel%
