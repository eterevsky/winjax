@echo off
"@@PYTHON_EXE@@" -B "@@WRAPPER_PY@@" %*
exit /b %ERRORLEVEL%
