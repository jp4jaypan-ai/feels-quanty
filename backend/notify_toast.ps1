param(
  [Parameter(Mandatory=$true)][string]$Title,
  [Parameter(Mandatory=$true)][string]$Message,
  [ValidateSet('Candidate','Confirmed')][string]$Level = 'Confirmed'
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$notifyIcon = New-Object System.Windows.Forms.NotifyIcon
if ($Level -eq 'Candidate') {
  $notifyIcon.Icon = [System.Drawing.SystemIcons]::Information
  $notifyIcon.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
  $duration = 3000
  $lingerSeconds = 4
} else {
  $notifyIcon.Icon = [System.Drawing.SystemIcons]::Warning
  $notifyIcon.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Warning
  $duration = 8000
  $lingerSeconds = 9
}
$notifyIcon.BalloonTipTitle = $Title
$notifyIcon.BalloonTipText = $Message
$notifyIcon.Visible = $true
$notifyIcon.ShowBalloonTip($duration)
Start-Sleep -Seconds $lingerSeconds
$notifyIcon.Visible = $false
$notifyIcon.Dispose()
