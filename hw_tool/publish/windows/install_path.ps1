param(
    [string]$HwToolRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [switch]$CurrentSessionOnly
)

$binPath = (Resolve-Path (Join-Path $HwToolRoot "bin")).Path
if ($CurrentSessionOnly) {
    if (($env:Path -split ";") -notcontains $binPath) {
        $env:Path = "$binPath;$env:Path"
    }
    Write-Host "Added to current session PATH: $binPath"
    exit 0
}

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($userPath -split ";") -notcontains $binPath) {
    [Environment]::SetEnvironmentVariable("Path", "$binPath;$userPath", "User")
    Write-Host "Added to user PATH: $binPath"
}
else {
    Write-Host "User PATH already contains: $binPath"
}
Write-Host "Open a new terminal, then run: hw_tool.cmd list"
