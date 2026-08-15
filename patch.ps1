param(
    [Parameter(Mandatory=$true)][string]$Acc,
    [Parameter(Mandatory=$true)][string]$Firmware,
    [string]$Output = ""
)

$ErrorActionPreference = "Stop"
$script = Join-Path $PSScriptRoot "patcher.py"

$python = Get-Command py -ErrorAction SilentlyContinue
if ($python) {
    $cmd = @("-3", $script, "--acc", $Acc, "--firmware", $Firmware)
    if ($Output) { $cmd += @("--output", $Output) }
    & py @cmd
    exit $LASTEXITCODE
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error "Python 3 was not found. Install Python 3, then run this script again."
}

$cmd = @($script, "--acc", $Acc, "--firmware", $Firmware)
if ($Output) { $cmd += @("--output", $Output) }
& python @cmd
exit $LASTEXITCODE
