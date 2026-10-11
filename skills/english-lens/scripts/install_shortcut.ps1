# English Lens: put one double-clickable launcher on the Desktop. No admin, no autostart.
param([string]$Name = 'English Lens')
$ErrorActionPreference = 'Stop'
$lens = Join-Path $PSScriptRoot 'lens.py'
$py = (Get-Command python -ErrorAction Stop).Source
$pyw = Join-Path (Split-Path $py) 'pythonw.exe'
if (-not (Test-Path $pyw)) { $pyw = $py }
$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) "$Name.lnk"
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = $pyw
$s.Arguments = '"' + $lens + '"'
$s.WorkingDirectory = $PSScriptRoot
$s.IconLocation = "$pyw,0"
$s.Description = 'Select English text on screen -> Chinese learning panel (Ctrl+Alt+S)'
$s.Save()
Write-Output "shortcut : $lnk"
Write-Output "runs     : $pyw `"$lens`""
