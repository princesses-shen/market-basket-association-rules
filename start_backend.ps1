param([switch]$Build, [switch]$SmtpTest, [switch]$CheckConfig)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts/account-env.ps1')
if ($CheckConfig) {
    Write-Output ('SMTP configured: ' + [bool]($env:SMTP_HOST -and $env:SMTP_USERNAME -and $env:SMTP_PASSWORD -and $env:SMTP_FROM))
    Write-Output 'JWT configuration loaded.'
    return
}
Push-Location $PSScriptRoot
try {
    if ($SmtpTest) {
        $previousSmtpFlag = $env:RUN_SMTP_INTEGRATION
        try {
            $env:RUN_SMTP_INTEGRATION = 'true'
            & mvn -f day08-backend/pom.xml '-Dtest=QqSmtpIntegrationTest' test
            if ($LASTEXITCODE -ne 0) { throw 'SMTP integration test failed; no successful delivery is claimed.' }
        } finally { $env:RUN_SMTP_INTEGRATION = $previousSmtpFlag }
        return
    }
    $jar = Join-Path $PSScriptRoot 'day08-backend/target/demo-0.0.1-SNAPSHOT.jar'
    if ($Build -or !(Test-Path -LiteralPath $jar)) {
        & mvn -f day08-backend/pom.xml package
        if ($LASTEXITCODE -ne 0) { throw 'Build or tests failed.' }
    }
    & java -jar $jar
    if ($LASTEXITCODE -ne 0) { throw 'Backend exited unsuccessfully. Check the HBase connection and application log.' }
} finally { Pop-Location }
