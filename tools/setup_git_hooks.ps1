# Active les hooks Git du dépôt (.githooks/pre-commit → sync ROADMAP métriques).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
git config core.hooksPath .githooks
Write-Host "[OK] core.hooksPath = .githooks"
Write-Host "Le pre-commit mettra à jour ROADMAP.md (section auto-sync) avant chaque commit."
