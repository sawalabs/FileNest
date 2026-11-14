<#
.SYNOPSIS
    Builds the standalone Windows Installer for FileNest.
.PARAMETER Mode
    'lite' (Default: Lightweight installer using Windows Native OCR)
    'full' (Offline bundle with pre-packaged PaddleOCR models)
.PARAMETER SkipBackend
    Skips PyInstaller backend packaging if filenest-backend.exe already exists.
.PARAMETER RunTests
    Runs backend pytest suite before building the installer.
#>
param(
    [ValidateSet("full", "lite")]
    [string]$Mode = "lite",
    [switch]$SkipBackend,
    [switch]$RunTests
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$MainRepoRoot = $env:FILENEST_MAIN_REPO
if (-not $MainRepoRoot) {
    $GitCmd = Get-Command git -ErrorAction SilentlyContinue
    if ($GitCmd) {
        $WorktreeLine = (& git worktree list --porcelain 2>$null | Where-Object { $_ -like "worktree *" } | Select-Object -First 1)
        if ($WorktreeLine) {
            $CandidateRoot = $WorktreeLine.Substring(9).Trim()
            if (Test-Path $CandidateRoot) {
                $MainRepoRoot = (Resolve-Path $CandidateRoot).Path
            }
        }
    }
}
if (-not $MainRepoRoot) {
    $MainRepoRoot = $ProjectRoot
}
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $FallbackPython = Join-Path $MainRepoRoot ".venv\Scripts\python.exe"
    if (Test-Path $FallbackPython) {
        $PythonExe = $FallbackPython
    } else {
        throw "Python virtual environment not found in '$ProjectRoot\.venv' or '$MainRepoRoot\.venv'."
    }
}

$CreatedNodeModulesJunction = $false
$NodeModulesPath = Join-Path $ProjectRoot "node_modules"
$TempTauriConfig = Join-Path $env:TEMP ("filenest-tauri-override-" + [guid]::NewGuid().ToString("N") + ".json")
if (-not (Test-Path $NodeModulesPath)) {
    $FallbackNodeModules = Join-Path $MainRepoRoot "node_modules"
    if (Test-Path $FallbackNodeModules) {
        Write-Host "[setup] Linking temporary node_modules junction from $FallbackNodeModules..." -ForegroundColor DarkGray
        New-Item -ItemType Junction -Path $NodeModulesPath -Target $FallbackNodeModules | Out-Null
        $CreatedNodeModulesJunction = $true
    } else {
        throw "node_modules not found in '$ProjectRoot' or '$MainRepoRoot'."
    }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  FileNest - Standalone Windows Installer Builder" -ForegroundColor Cyan
Write-Host "  Target Mode: $($Mode.ToUpper())" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

try {
    $TscBin = Join-Path $NodeModulesPath ".bin\tsc.cmd"
    $ViteBin = Join-Path $NodeModulesPath ".bin\vite.cmd"
    $TauriBin = Join-Path $NodeModulesPath ".bin\tauri.cmd"

    # Optional pre-build backend verification
    if ($RunTests) {
        Write-Host "`n[0/4] Running backend test suite..." -ForegroundColor Yellow
        & $PythonExe -m pytest backend/tests -q
        if ($LASTEXITCODE -ne 0) { throw "Backend tests failed with exit code $LASTEXITCODE" }
    }

    # 1. Build Frontend
    Write-Host "`n[1/4] Type-checking and building frontend production bundle..." -ForegroundColor Yellow
    & $TscBin --noEmit
    if ($LASTEXITCODE -ne 0) { throw "TypeScript check failed with exit code $LASTEXITCODE" }
    & $ViteBin build
    if ($LASTEXITCODE -ne 0) { throw "Vite build failed with exit code $LASTEXITCODE" }

    # 2. Package Backend with PyInstaller
    $BundledBackendDir = Join-Path $ProjectRoot "src-tauri\resources\backend"
    $BundledBackendExe = Join-Path $BundledBackendDir "filenest-backend.exe"
    $MainRepoBackendDir = Join-Path $MainRepoRoot "src-tauri\resources\backend"
    if ($SkipBackend -and (-not (Test-Path $BundledBackendExe)) -and ($MainRepoRoot -ne $ProjectRoot) -and (Test-Path (Join-Path $MainRepoBackendDir "filenest-backend.exe"))) {
        Write-Host "`n[2/4] Copying existing pre-packaged filenest-backend.exe from main repository..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Force -Path $BundledBackendDir | Out-Null
        Copy-Item -Path (Join-Path $MainRepoBackendDir "*") -Destination $BundledBackendDir -Recurse -Force
    }
    if ($SkipBackend -and (Test-Path $BundledBackendExe)) {
        Write-Host "`n[2/4] Skipping Python backend packaging (-SkipBackend active, reusing existing filenest-backend.exe)..." -ForegroundColor Yellow
    } else {
        Write-Host "`n[2/4] Packaging Python backend (Mode: $Mode)..." -ForegroundColor Yellow
        & $PythonExe scripts/build_backend.py --mode $Mode
        if ($LASTEXITCODE -ne 0) { throw "Backend packaging failed with exit code $LASTEXITCODE" }
    }

    # 3. Build Tauri NSIS & MSI Installers
    Write-Host "`n[3/4] Compiling Tauri 2 Windows installers (NSIS & MSI)..." -ForegroundColor Yellow
    [System.IO.File]::WriteAllText($TempTauriConfig, '{"build":{"beforeBuildCommand":""}}')
    & $TauriBin build --config $TempTauriConfig
    if ($LASTEXITCODE -ne 0) { throw "Tauri build failed with exit code $LASTEXITCODE" }

    # 4. Collect Installer Artifacts
    Write-Host "`n[4/4] Collecting installer artifacts into release/..." -ForegroundColor Yellow
    $ReleaseDirs = @((Join-Path $ProjectRoot "release"))
    if ((Test-Path $MainRepoRoot) -and ($MainRepoRoot -ne $ProjectRoot)) {
        $ReleaseDirs += (Join-Path $MainRepoRoot "release")
    }

    $BundleRoot = Join-Path $ProjectRoot "src-tauri\target\release\bundle"
    $Artifacts = @(
        Get-ChildItem -Path (Join-Path $BundleRoot "nsis") -Filter "*.exe" -ErrorAction SilentlyContinue
        Get-ChildItem -Path (Join-Path $BundleRoot "msi") -Filter "*.msi" -ErrorAction SilentlyContinue
    )

    foreach ($Dir in $ReleaseDirs) {
        New-Item -ItemType Directory -Force -Path $Dir | Out-Null
        foreach ($Artifact in $Artifacts) {
            Copy-Item -Path $Artifact.FullName -Destination (Join-Path $Dir $Artifact.Name) -Force
        }
    }

    Write-Host "`n==========================================================" -ForegroundColor Green
    Write-Host "  BUILD SUCCESSFUL!" -ForegroundColor Green
    foreach ($Artifact in $Artifacts) {
        $SizeMB = [math]::Round($Artifact.Length / 1MB, 2)
        Write-Host "  - $($Artifact.Name) ($SizeMB MB): $($Artifact.FullName)" -ForegroundColor Green
    }
    Write-Host "  Copied to release directory: $(Join-Path $ProjectRoot 'release')" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
} finally {
    if (Test-Path $TempTauriConfig) {
        Remove-Item -Path $TempTauriConfig -Force -ErrorAction SilentlyContinue
    }
    if ($CreatedNodeModulesJunction -and (Test-Path $NodeModulesPath)) {
        Write-Host "[cleanup] Removing temporary node_modules junction..." -ForegroundColor DarkGray
        cmd /c rmdir "$NodeModulesPath" | Out-Null
    }
}
