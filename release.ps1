# Build, package and publish a GamepadTrucker release in one command.
#
#   powershell -ExecutionPolicy Bypass -File release.ps1
#
# The version is read from the VERSION file - bump that one file, run this,
# and a tagged GitHub release with the packaged .zip is produced.
#
# Steps:
#   1. read VERSION                -> v<version> tag
#   2. build dist\GamepadTrucker.exe (build.ps1, unless -SkipBuild)
#   3. package dist\GamepadTrucker-<version>.zip
#        (GamepadTrucker.exe + setup_vjoy.ps1 + READ_ME_FIRST.txt)
#   4. create + push git tag v<version>
#   5. create the GitHub release and upload the .zip (needs the gh CLI; if gh
#      is missing it prints the manual upload step instead)
#
# Flags:
#   -SkipBuild   reuse the existing dist\GamepadTrucker.exe
#   -NoPush      do everything locally, do not push the tag or touch GitHub
#   -Notes "..." release notes text (default is a one-line note)

param(
    [switch]$SkipBuild,
    [switch]$NoPush,
    [string]$Notes
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$ver = (Get-Content -Path ".\VERSION" -Raw).Trim()
if (-not $ver) { Write-Error "VERSION file is empty."; exit 1 }
$tag = "v$ver"
Write-Host "[release] Version $ver  (tag $tag)" -ForegroundColor Cyan

# --- 1. build --------------------------------------------------------------
if (-not $SkipBuild) {
    Write-Host "[release] Building exe..."
    & powershell -ExecutionPolicy Bypass -File ".\build.ps1"
    if ($LASTEXITCODE -ne 0) { Write-Error "Build failed."; exit 1 }
}
$exe = ".\dist\GamepadTrucker.exe"
if (-not (Test-Path $exe)) { Write-Error "dist\GamepadTrucker.exe not found - run without -SkipBuild."; exit 1 }

# --- 2. package ------------------------------------------------------------
$stage = ".\dist\GamepadTrucker-$ver"
$zip   = ".\dist\GamepadTrucker-$ver.zip"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
if (Test-Path $zip)   { Remove-Item $zip -Force }
New-Item -ItemType Directory -Path $stage | Out-Null

Copy-Item $exe              -Destination $stage
Copy-Item ".\setup_vjoy.ps1" -Destination $stage

$readme = @"
GamepadTrucker $ver
===================

Gyro-steering for ETS2 / ATS using a DualShock 4 or DualSense over Bluetooth.

First-time setup
----------------
1. Run setup_vjoy.ps1 (right-click -> Run with PowerShell, or:
     powershell -ExecutionPolicy Bypass -File setup_vjoy.ps1).
   It installs the vJoy driver and configures vJoy device #1. Approve the
   admin prompt. Reboot if it asks, then run it once more.
2. Pair your gamepad over Bluetooth in Windows settings.
3. Launch GamepadTrucker.exe.

In ETS2 / ATS controls, bind the vJoy device:
   Steering = X,  Throttle = Z,  Brake = RZ,  Look = RX / RY.
The other buttons emulate the game's default keyboard controls.

Notes
-----
- The vJoy driver cannot be bundled into the .exe; setup_vjoy.ps1 installs it.
- Telemetry lightbar (RPM colour) installs its plugin from inside the app.
"@
Set-Content -Path (Join-Path $stage "READ_ME_FIRST.txt") -Value $readme -Encoding UTF8

Write-Host "[release] Zipping -> $zip"
Compress-Archive -Path "$stage\*" -DestinationPath $zip -Force
Remove-Item $stage -Recurse -Force

# --- 3. git tag ------------------------------------------------------------
$existingTag = (git tag --list $tag)
if (-not $existingTag) {
    Write-Host "[release] Tagging $tag"
    git tag -a $tag -m "GamepadTrucker $ver"
} else {
    Write-Host "[release] Tag $tag already exists, reusing it."
}

if ($NoPush) {
    Write-Host "[release] -NoPush set. Package ready: $zip" -ForegroundColor Green
    Write-Host "[release] Skipped tag push and GitHub release."
    exit 0
}

git push origin $tag

# --- 4. GitHub release -----------------------------------------------------
if (-not $Notes) { $Notes = "GamepadTrucker $ver" }

$gh = Get-Command gh -ErrorAction SilentlyContinue
if ($gh) {
    Write-Host "[release] Creating GitHub release $tag via gh..."
    $exists = (gh release view $tag 2>$null)
    if ($LASTEXITCODE -eq 0) {
        gh release upload $tag $zip --clobber
    } else {
        gh release create $tag $zip --title "GamepadTrucker $ver" --notes $Notes
    }
    Write-Host "[release] Done. Release $tag published with $zip." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[release] gh CLI not found - tag pushed, but the release was not created." -ForegroundColor Yellow
    Write-Host "          Finish it one of two ways:" -ForegroundColor Yellow
    Write-Host "  A) Install gh, run 'gh auth login' once, then re-run release.ps1 -SkipBuild." -ForegroundColor Yellow
    Write-Host "  B) Open the repo Releases page, draft a release for tag $tag," -ForegroundColor Yellow
    Write-Host "     and upload $zip as the asset." -ForegroundColor Yellow
}
