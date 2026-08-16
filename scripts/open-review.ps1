# Open Feishu-style Review for this skill (sibling switcher included).
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\open-review.ps1
$ErrorActionPreference = 'Stop'
$SkillRoot = Split-Path -Parent $PSScriptRoot
$SkillsRoot = Split-Path -Parent $SkillRoot
$Viewer = Join-Path $SkillsRoot 'skills-check\scripts\skills-check-viewer.py'
if (-not (Test-Path -LiteralPath $Viewer)) {
    throw "找不到 skills-check-viewer.py: $Viewer"
}
python $Viewer --skill $SkillRoot
