# Back-compat wrapper — prefer ask_local_worker.ps1 with -Model local-glm52
param(
    [Parameter(Mandatory = $true)]
    [string]$Prompt,
    [string]$System = "",
    [string]$Model = "local-glm52",
    [string]$BaseUrl = $(if ($env:LOCAL_INFERENCE_BASE_URL) { $env:LOCAL_INFERENCE_BASE_URL } elseif ($env:LOCAL_PROXY_BASE_URL) { $env:LOCAL_PROXY_BASE_URL } else { "http://100.92.253.61:4000/v1" }),
    [string]$EnvFile = "C:\Users\vince\local-inference\.env.local",
    [int]$MaxTokens = 2048,
    [double]$Temperature = 0.3,
    [int]$TimeoutSec = 300
)
$worker = Join-Path $PSScriptRoot "ask_local_worker.ps1"
& $worker @PSBoundParameters
