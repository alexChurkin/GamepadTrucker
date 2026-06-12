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
#   5. create the GitHub release and upload the .zip
#
# Publishing the release uses, in order of preference:
#   - the gh CLI, if installed (run 'gh auth login' once), or
#   - a GitHub token in $env:GITHUB_TOKEN (or a .github_token file next to
#     this script), via the REST API - no install needed. Use a token with
#     Contents: write on the repo.
# If neither is available the tag is still pushed and the manual upload step
# is printed.
#
# Flags:
#   -SkipBuild   reuse the existing dist\GamepadTrucker.exe
#   -NoPush      do everything locally, do not push the tag or touch GitHub
#   -Notes "..." release notes text (default is a one-line note)
#   -Repo "owner/name"  override the target repo (default: parsed from origin)

param(
    [switch]$SkipBuild,
    [switch]$NoPush,
    [string]$Notes,
    [string]$Repo
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

# Resolve target repo (owner/name) from the origin remote if not given.
if (-not $Repo) {
    $origin = (git remote get-url origin)
    if ($origin -match '[:/]([^/:]+)/([^/]+?)(?:\.git)?$') {
        $Repo = "$($matches[1])/$($matches[2])"
    }
}

# Locate gh: PATH first, then the portable install location.
$gh = (Get-Command gh -ErrorAction SilentlyContinue).Source
if (-not $gh) {
    foreach ($p in @("$env:LOCALAPPDATA\Programs\gh\bin\gh.exe",
                     "$env:ProgramFiles\GitHub CLI\gh.exe")) {
        if (Test-Path $p) { $gh = $p; break }
    }
}
if ($gh) {
    Write-Host "[release] Creating GitHub release $tag via gh ($gh)..."
    & $gh release view $tag 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        & $gh release upload $tag $zip --clobber
    } else {
        & $gh release create $tag $zip --title "GamepadTrucker $ver" --notes $Notes
    }
    Write-Host "[release] Done. Release $tag published with $zip." -ForegroundColor Green
    exit 0
}

# No gh - try a token via REST API.
$token = $env:GITHUB_TOKEN
if (-not $token) { $token = $env:GH_TOKEN }
if (-not $token -and (Test-Path ".\.github_token")) {
    $token = (Get-Content ".\.github_token" -Raw).Trim()
}

if ($token -and $Repo) {
    Write-Host "[release] Creating GitHub release $tag via REST API ($Repo)..."
    $headers = @{
        Authorization          = "Bearer $token"
        "Accept"               = "application/vnd.github+json"
        "X-GitHub-Api-Version" = "2022-11-28"
        "User-Agent"           = "GamepadTrucker-release"
    }
    $body = @{ tag_name = $tag; name = "GamepadTrucker $ver"; body = $Notes } | ConvertTo-Json
    try {
        $rel = Invoke-RestMethod -Method Post -Headers $headers `
            -Uri "https://api.github.com/repos/$Repo/releases" -Body $body -ContentType "application/json"
    } catch {
        # Release may already exist - fetch it by tag.
        $rel = Invoke-RestMethod -Headers $headers `
            -Uri "https://api.github.com/repos/$Repo/releases/tags/$tag"
    }
    $name = [IO.Path]::GetFileName($zip)
    $uploadUrl = ($rel.upload_url -replace '\{.*\}', '') + "?name=$name"
    Invoke-RestMethod -Method Post -Headers $headers -Uri $uploadUrl `
        -InFile $zip -ContentType "application/zip" | Out-Null
    Write-Host "[release] Done. Release $tag published with $name -> $($rel.html_url)" -ForegroundColor Green
    exit 0
}

Write-Host ""
Write-Host "[release] Tag pushed, but no gh CLI and no token, so the release was not created." -ForegroundColor Yellow
Write-Host "          Finish it one of these ways:" -ForegroundColor Yellow
Write-Host "  A) Set a token once:  `$env:GITHUB_TOKEN = '<PAT with Contents:write>'" -ForegroundColor Yellow
Write-Host "     then re-run:        release.ps1 -SkipBuild" -ForegroundColor Yellow
Write-Host "  B) Install gh, run 'gh auth login' once, then re-run release.ps1 -SkipBuild." -ForegroundColor Yellow
Write-Host "  C) Open the repo Releases page, draft a release for tag $tag, upload:" -ForegroundColor Yellow
Write-Host "       $zip" -ForegroundColor Yellow
