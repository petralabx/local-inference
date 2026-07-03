@echo off
REM install-boot-durability.cmd
REM ---------------------------------------------------------------------------
REM Makes the Dell local-inference stack survive reboots:
REM   1. The vLLM backend is a Docker container with --restart=unless-stopped
REM      (started via scripts\start_dell_vllm_qwen3_32b_awq_durable.sh). Docker
REM      Desktop must be set to start at login (its default) for this to work.
REM   2. The LiteLLM proxy is NOT a container, so we register a Windows Scheduled
REM      Task that launches it at user logon via Git Bash.
REM
REM Run this ONCE from an elevated (Administrator) Command Prompt:
REM   cd %USERPROFILE%\local-inference\scripts
REM   install-boot-durability.cmd
REM
REM To remove:  schtasks /Delete /TN "LocalInferenceProxy" /F
REM ---------------------------------------------------------------------------
setlocal

set "BASH=C:\Program Files\Git\bin\bash.exe"
set "PROXY=%USERPROFILE%\local-inference\scripts\start_proxy.sh"

if not exist "%BASH%" (
  echo ERROR: Git Bash not found at "%BASH%". Adjust BASH path in this script.
  exit /b 1
)
if not exist "%PROXY%" (
  echo ERROR: proxy script not found at "%PROXY%".
  exit /b 1
)

echo Registering Scheduled Task "LocalInferenceProxy" (runs at logon)...
schtasks /Create /TN "LocalInferenceProxy" /SC ONLOGON /RL HIGHEST /F ^
  /TR "\"%BASH%\" -lc 'cd ~/local-inference && ./scripts/start_proxy.sh >> /tmp/litellm_proxy.log 2>&1'"

if %ERRORLEVEL% NEQ 0 (
  echo Failed to register task. Run this prompt as Administrator.
  exit /b 1
)

echo.
echo Done. On next logon the LiteLLM proxy auto-starts.
echo The vLLM backend container auto-restarts via Docker (run the *_durable.sh
echo script once to create the named, restart-policy container).
echo.
echo Verify after a reboot:  curl http://127.0.0.1:4000/v1/models
endlocal
