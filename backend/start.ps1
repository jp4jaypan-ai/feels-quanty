$scriptPath = Join-Path $PSScriptRoot "server.py"
$pythonPath = "C:\Python27\python.exe"
if (Test-Path -LiteralPath $pythonPath) {
  & $pythonPath $scriptPath
  exit $LASTEXITCODE
}
$pyLauncher = Get-Command py.exe -ErrorAction Stop
& $pyLauncher.Source -2.7 $scriptPath
exit $LASTEXITCODE