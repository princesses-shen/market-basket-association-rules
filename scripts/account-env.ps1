# Dot-source this file. Values are parsed as literal text, never executed.
param([string]$ConfigPath = (Join-Path $PSScriptRoot '../config/account-security.env'))
$ErrorActionPreference = 'Stop'
$ConfigPath = [IO.Path]::GetFullPath($ConfigPath)
$configDirectory = Split-Path -Parent $ConfigPath
if (!(Test-Path -LiteralPath $configDirectory)) { New-Item -ItemType Directory -Path $configDirectory | Out-Null }
if (!(Test-Path -LiteralPath $ConfigPath)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot '../config/account-security.env.example') -Destination $ConfigPath
}
$allowed = @('ZK_QUORUM','JWT_SECRET','ADMIN_INITIAL_PASSWORD','SMTP_HOST','SMTP_PORT','SMTP_USERNAME','SMTP_PASSWORD','SMTP_FROM','SMTP_STARTTLS','SMTP_SSL')
foreach ($line in [IO.File]::ReadAllLines($ConfigPath)) {
    if ($line.Trim().Length -eq 0 -or $line.TrimStart().StartsWith('#')) { continue }
    $pair = $line.Split(@('='), 2)
    if ($pair.Length -ne 2 -or $allowed -notcontains $pair[0]) { throw 'Invalid account configuration entry.' }
    if ([string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($pair[0], 'Process'))) {
        [Environment]::SetEnvironmentVariable($pair[0], $pair[1], 'Process')
    }
}
if ([string]::IsNullOrEmpty($env:JWT_SECRET)) {
    $bytes = New-Object byte[] 48
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $random.GetBytes($bytes) } finally { $random.Dispose() }
    $env:JWT_SECRET = [Convert]::ToBase64String($bytes)
    $content = [IO.File]::ReadAllText($ConfigPath)
    if ($content -match '(?m)^JWT_SECRET=') {
        $content = [regex]::Replace($content, '(?m)^JWT_SECRET=[^\r\n]*', 'JWT_SECRET=' + $env:JWT_SECRET)
    } else { $content += "`nJWT_SECRET=$($env:JWT_SECRET)`n" }
    [IO.File]::WriteAllText($ConfigPath, $content, (New-Object Text.UTF8Encoding($false)))
}
if ([Text.Encoding]::UTF8.GetByteCount($env:JWT_SECRET) -lt 32) { throw 'JWT_SECRET must contain at least 32 bytes.' }
