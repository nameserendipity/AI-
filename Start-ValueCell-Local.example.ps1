<#
Example local launcher for ValueCell / AI 量化交易.

Copy this file to Start-ValueCell-Local.ps1 and adjust the paths/proxy settings for your machine.
The real Start-ValueCell-Local.ps1 should be ignored by git to avoid leaking personal paths or proxy settings.

Usage:
  .\Start-ValueCell-Local.ps1              # start frontend + backend
  .\Start-ValueCell-Local.ps1 -NoFrontend  # backend only
  .\Start-ValueCell-Local.ps1 -NoBackend   # frontend only
#>

param(
    [switch]$NoFrontend,
    [switch]$NoBackend
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

# Optional: set a custom data/config directory. Leave empty to use the OS default.
# $env:VALUECELL_HOME = "D:\ValueCellData"

# Optional: local development mode. This can make PowerShell/IDE startup more stable.
$env:ENV = "local_dev"

# Optional: enable detailed local debug logs.
$env:AGENT_DEBUG_MODE = "true"

# Optional: proxy settings if your model/data providers need a local proxy.
# $env:HTTP_PROXY = "http://127.0.0.1:7890"
# $env:HTTPS_PROXY = "http://127.0.0.1:7890"

$argsToPass = @()
if ($NoFrontend) { $argsToPass += "-NoFrontend" }
if ($NoBackend) { $argsToPass += "-NoBackend" }

& "$ProjectRoot\start.ps1" @argsToPass
