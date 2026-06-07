param(
    [ValidateSet("web", "api", "healthcheck", "test")]
    [string]$Mode = "web",
    [switch]$InstallDeps
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

function Load-DotEnv {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return
    }

    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            return
        }
        $idx = $line.IndexOf("=")
        if ($idx -le 0) {
            return
        }
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim()
        if ($key) {
            [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
}

Write-Host "[DeepMemo] Project root: $ProjectRoot"
Load-DotEnv -Path ".env"

if ($InstallDeps) {
    Write-Host "[DeepMemo] Installing dependencies..."
    python -m pip install -r requirements.txt
}

if (($Mode -eq "web" -or $Mode -eq "api") -and -not $env:DEEPSEEK_API_KEY) {
    Write-Warning "DEEPSEEK_API_KEY is empty. Please set it in .env or environment variable."
}

switch ($Mode) {
    "web" {
        Write-Host "[DeepMemo] Starting web app at http://localhost:8501 ..."
        python main.py web
    }
    "api" {
        Write-Host "[DeepMemo] Starting API at http://localhost:8000 ..."
        python main.py api
    }
    "healthcheck" {
        python main.py healthcheck
    }
    "test" {
        python -m pytest
    }
}

