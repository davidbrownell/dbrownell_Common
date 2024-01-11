@REM ----------------------------------------------------------------------
@REM |
@REM |  This script downloads and invokes BoostrapImpl.cmd from the PythonBootstrapper
@REM |  repository (https://github.com/davidbrownell/PythonBootstrapper).
@REM |
@REM |  Arguments:
@REM |
@REM |      --debug                         Display additional debugging information.
@REM |
@REM |      --force                         Ensure that a new python environment is installed, even if it already exists.
@REM |
@REM |      --python-version <version>      Specify the python version to install; the default python version is installed if not specified.
@REM |
@REM ----------------------------------------------------------------------
@setlocal EnableDelayedExpansion
@pushd %~dp0

@REM ----------------------------------------------------------------------
@REM |
@REM |  Download BootstrapImpl.cmd
@REM |
@REM ----------------------------------------------------------------------
@echo Downloading Bootstrap code...

@call :_CreateTempFileName

@curl --header "Cache-Control: no-cache, no-store" --header "Pragma: no-cache" --location https://raw.githubusercontent.com/davidbrownell/PythonBootstrapper/main/src/BootstrapImpl.cmd --output BootstrapImpl.cmd --no-progress-meter --fail-with-body > "%_BOOTSTRAP_TEMP_FILENAME%" 2>&1
@set _ERRORLEVEL=%ERRORLEVEL%

@if %_ERRORLEVEL% NEQ 0 (
    @echo [1ADownloading Bootstrap code...[31m[1mFAILED[0m.
    @echo.

    @type "%_BOOTSTRAP_TEMP_FILENAME%"
    @goto :Exit
)

@call :_DeleteTempFile
@echo [1ADownloading Bootstrap code...[32m[1mDONE[0m.

@REM ----------------------------------------------------------------------
@REM |
@REM |  Invoke BootstrapImpl.cmd
@REM |
@REM ----------------------------------------------------------------------
@call BootstrapImpl.cmd %*
@set _ERRORLEVEL=%ERRORLEVEL%

@REM ----------------------------------------------------------------------
@REM |
@REM |  Exit
@REM |
@REM ----------------------------------------------------------------------
:Exit
@if exist BootstrapImpl.cmd del BootstrapImpl.cmd
@call :_DeleteTempFile

@popd

@endlocal & @exit /B %_ERRORLEVEL%

@REM ----------------------------------------------------------------------
@REM ----------------------------------------------------------------------
@REM ----------------------------------------------------------------------
:_CreateTempFileName
@set _BOOTSTRAP_TEMP_FILENAME=%CD%\Bootstrap-!RANDOM!-!Time:~6,5!
@goto :EOF

@REM ----------------------------------------------------------------------
:_DeleteTempFile
@if "%_BOOTSTRAP_TEMP_FILENAME%" NEQ "" (
    @if exist "%_BOOTSTRAP_TEMP_FILENAME%" (
        @del "%_BOOTSTRAP_TEMP_FILENAME%"
    )
)
@goto :EOF
