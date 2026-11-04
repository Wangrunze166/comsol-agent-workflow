param(
    [Parameter(Mandatory=$true)][string]$Case,
    [Parameter(Mandatory=$true)][string]$ComsolRoot,
    [Parameter(Mandatory=$true)][string]$RunDir,
    [Parameter(Mandatory=$true)][string]$KeyDir,
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
# Run this yourself in a trusted interactive console, never through an Agent's
# terminal. Read docs/approval-security.md before provisioning the trust anchor.
function Invoke-Workflow {
    param([string[]]$WorkflowArgs)
    & $Python -m comsol_workflow @WorkflowArgs
    if ($LASTEXITCODE -ne 0) { throw 'Workflow stopped. Inspect the displayed error; no automatic retry.' }
}
$caseFile = (Resolve-Path -LiteralPath $Case).Path
$keyRoot = [IO.Path]::GetFullPath($KeyDir)
$runRoot = [IO.Path]::GetFullPath($RunDir)
$privateKey = Join-Path $keyRoot 'user-private.pem'
$publicKey = Join-Path $keyRoot 'user-public.pem'
Write-Host 'User-owned signing session. Keep your passphrase out of chat, scripts and environment variables.'
Write-Host 'TTY is not a security boundary. Protect the signer, private key and trusted public key from Agent modification.'
if (!(Test-Path -LiteralPath $privateKey) -and !(Test-Path -LiteralPath $publicKey)) {
    Invoke-Workflow -WorkflowArgs @('approval-keygen', '--private-key', $privateKey, '--public-key', $publicKey)
}
if (!(Test-Path -LiteralPath $privateKey) -or !(Test-Path -LiteralPath $publicKey)) {
    throw 'Key pair is incomplete; do not overwrite an existing key.'
}
if (!(Test-Path -LiteralPath (Join-Path $runRoot 'plan.json'))) {
    Invoke-Workflow -WorkflowArgs @('plan', $caseFile, '--out', $runRoot, '--comsol-root', $ComsolRoot, '--public-key', $publicKey)
}
Invoke-Workflow -WorkflowArgs @('smoke', $runRoot)
Get-Content -LiteralPath (Join-Path $runRoot 'REVIEW.md') -Encoding UTF8
Write-Host "Full case and generated drivers are in: $runRoot"
$assumptions = Join-Path $runRoot 'assumptions.receipt.json'
$solve = Join-Path $runRoot 'solve.receipt.json'
if (!(Test-Path -LiteralPath $assumptions)) {
    Invoke-Workflow -WorkflowArgs @('approve', $runRoot, '--stage', 'assumptions', '--private-key', $privateKey, '--public-key', $publicKey, '--out', $assumptions)
}
if (!(Test-Path -LiteralPath $solve)) {
    Invoke-Workflow -WorkflowArgs @('approve', $runRoot, '--stage', 'solve', '--private-key', $privateKey, '--public-key', $publicKey, '--out', $solve, '--assumptions', $assumptions)
}
Invoke-Workflow -WorkflowArgs @('run', $runRoot, '--assumptions', $assumptions, '--approval', $solve)
Write-Host "Execution record: $runRoot\run-state.json"
Write-Host "Report: $runRoot\report.md"
