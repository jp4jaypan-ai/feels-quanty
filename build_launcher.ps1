[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Project = Join-Path $Root "launcher\feels-quanty-launcher.csproj"
$Release = Join-Path $Root "release"

if (!(Test-Path -LiteralPath $Project)) {
  throw "Launcher project not found: $Project"
}

New-Item -ItemType Directory -Force -Path $Release | Out-Null
dotnet publish $Project `
  --configuration Release `
  --output $Release

$exe = Join-Path $Release "feels-quanty.exe"
if (!(Test-Path -LiteralPath $exe)) {
  throw "Launcher build did not produce $exe"
}

Write-Host "Launcher ready: $exe" -ForegroundColor Green
