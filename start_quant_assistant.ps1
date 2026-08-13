[CmdletBinding()]
param(
  [int]$FrontendPort = 3001,
  [int]$BackendPort = 8765,
  [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $Root "work"
$BackendOutLog = Join-Path $LogDir "quant-backend.out.log"
$BackendErrLog = Join-Path $LogDir "quant-backend.err.log"
$FrontendOutLog = Join-Path $LogDir "quant-frontend.out.log"
$FrontendErrLog = Join-Path $LogDir "quant-frontend.err.log"
$OwnedProcessIds = @()

Set-Location $Root
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Test-HttpEndpoint {
  param([Parameter(Mandatory = $true)][string]$Url)
  try {
    $request = [System.Net.WebRequest]::Create($Url)
    $request.Timeout = 1500
    $response = $request.GetResponse()
    $response.Close()
    return $true
  } catch {
    return $false
  }
}

function Wait-HttpEndpoint {
  param(
    [Parameter(Mandatory = $true)][string]$Url,
    [int]$TimeoutSeconds = 30
  )
  for ($index = 0; $index -lt $TimeoutSeconds; $index++) {
    if (Test-HttpEndpoint -Url $Url) { return $true }
    Start-Sleep -Seconds 1
  }
  return $false
}

function Get-ChildProcessIds {
  param([Parameter(Mandatory = $true)][int]$ParentId)
  $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $ParentId" -ErrorAction SilentlyContinue)
  foreach ($child in $children) {
    $childId = [int]$child.ProcessId
    Get-ChildProcessIds -ParentId $childId
    $childId
  }
}

function Stop-ProcessTree {
  param([Parameter(Mandatory = $true)][int]$ProcessId)
  $descendants = @(Get-ChildProcessIds -ParentId $ProcessId)
  foreach ($descendant in ($descendants | Sort-Object -Descending)) {
    Stop-Process -Id $descendant -Force -ErrorAction SilentlyContinue
  }
  Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

function Fail-WithHint {
  param([Parameter(Mandatory = $true)][string]$Message)
  Write-Host "Startup failed: $Message" -ForegroundColor Red
  Write-Host "Backend log: $BackendErrLog" -ForegroundColor DarkGray
  Write-Host "Frontend log: $FrontendErrLog" -ForegroundColor DarkGray
  throw $Message
}

try {
  $pythonPath = "C:\Python27\python.exe"
  if (!(Test-Path -LiteralPath $pythonPath)) {
    Fail-WithHint "C:\Python27\python.exe was not found. Install the WindPy Python 2.7 environment first."
  }

  & $pythonPath -c "import WindPy" 2>$null
  if ($LASTEXITCODE -ne 0) {
    Fail-WithHint "Python 2.7 cannot import WindPy. Repair the Wind client WindPy environment first."
  }

  $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
  if (!$npmCommand) {
    Fail-WithHint "npm was not found. Install Node.js 22.13 or newer."
  }
  $npmPath = $npmCommand.Source

  if (!(Test-Path -LiteralPath (Join-Path $Root "node_modules"))) {
    Write-Host "First run: installing frontend dependencies..." -ForegroundColor Yellow
    & $npmPath install 2>&1 | Tee-Object -FilePath (Join-Path $LogDir "npm-install.log")
    if ($LASTEXITCODE -ne 0) {
      Fail-WithHint "npm install failed. Check work\npm-install.log."
    }
  }

  $backendUrl = "http://127.0.0.1:$BackendPort/api/health"
  if (Test-HttpEndpoint -Url $backendUrl) {
    Write-Host "Reusing existing backend at http://127.0.0.1:$BackendPort" -ForegroundColor DarkGray
  } else {
    $backendProcess = Start-Process -FilePath $pythonPath `
      -ArgumentList @("backend\server.py") `
      -WorkingDirectory $Root `
      -RedirectStandardOutput $BackendOutLog `
      -RedirectStandardError $BackendErrLog `
      -WindowStyle Hidden `
      -PassThru
    $OwnedProcessIds += [int]$backendProcess.Id
    Write-Host "Starting WindPy backend..." -ForegroundColor Cyan
  }

  if (!(Wait-HttpEndpoint -Url $backendUrl -TimeoutSeconds 30)) {
    Fail-WithHint "Backend did not become ready within 30 seconds."
  }

  $frontendUrl = "http://localhost:$FrontendPort"
  if (Test-HttpEndpoint -Url $frontendUrl) {
    Write-Host "Reusing existing frontend at $frontendUrl" -ForegroundColor DarkGray
  } else {
    $frontendProcess = Start-Process -FilePath $npmPath `
      -ArgumentList @("run", "dev", "--", "--port", "$FrontendPort") `
      -WorkingDirectory $Root `
      -RedirectStandardOutput $FrontendOutLog `
      -RedirectStandardError $FrontendErrLog `
      -WindowStyle Hidden `
      -PassThru
    $OwnedProcessIds += [int]$frontendProcess.Id
    Write-Host "Starting frontend..." -ForegroundColor Cyan
  }

  if (!(Wait-HttpEndpoint -Url $frontendUrl -TimeoutSeconds 30)) {
    Fail-WithHint "Frontend did not become ready within 30 seconds."
  }

  if (!$NoBrowser) {
    Start-Process $frontendUrl | Out-Null
  }

  Write-Host ""
  Write-Host "feels-quanty is ready." -ForegroundColor Green
  Write-Host "Frontend: $frontendUrl"
  Write-Host "Backend: http://127.0.0.1:$BackendPort"
  Write-Host "Keep the Wind client open, then add WindCodes and start monitoring in the browser."
  Write-Host "Press Ctrl+C to exit. Only services started by this script will be stopped." -ForegroundColor Yellow

  while ($true) {
    $serviceExited = $false
    foreach ($processId in @($OwnedProcessIds)) {
      if (!(Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
        $serviceExited = $true
        break
      }
    }
    if ($serviceExited) {
      throw "A child service exited. Check the work logs for details."
    }
    Start-Sleep -Seconds 2
  }
} catch {
  if ($_.Exception.Message -ne "") {
    Write-Host $_.Exception.Message -ForegroundColor Red
  }
  exit 1
} finally {
  foreach ($processId in @($OwnedProcessIds | Sort-Object -Descending)) {
    Stop-ProcessTree -ProcessId $processId
  }
}
