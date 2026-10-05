# Runs on the domain-joined admin server (as SYSTEM, through SSM Run Command).
# Creates \\<file server>\share\finance and locks it to the Finance-Team AD group with NTFS permissions.
$region = '@@REGION@@'
$share  = '\\@@FSXW_IP@@\share'
$dir    = "$share\finance"

# The AD Admin password comes from Secrets Manager through the instance role; it is never displayed.
try   { $pw = (Get-SECSecretValue -SecretId 'kgotla/ad-admin' -Region $region).SecretString }
catch { $pw = (& aws secretsmanager get-secret-value --secret-id kgotla/ad-admin --region $region --query SecretString --output text) }
if (-not $pw) { Write-Output 'could not read kgotla/ad-admin'; exit 1 }

& net use $share /delete /y *> $null
& net use $share "/user:KGOTLA\Admin" $pw *> $null
if ($LASTEXITCODE -ne 0) { Write-Output "net use to $share failed (exit $LASTEXITCODE)"; exit 1 }
Write-Output "connected to $share as KGOTLA\Admin"

if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
Set-Content -Path "$dir\README-finance.txt" -Value 'Kgotla finance working papers - Finance-Team only.'

# 1) explicit grants first: SYSTEM (FSx requires Full control for SYSTEM), the FSx admins, Admin, Finance-Team
& icacls $dir /grant '*S-1-5-18:(OI)(CI)F' 'KGOTLA\AWS Delegated FSx Administrators:(OI)(CI)F' 'KGOTLA\Admin:(OI)(CI)F' 'KGOTLA\Finance-Team:(OI)(CI)M'
if ($LASTEXITCODE -ne 0) { Write-Output 'icacls /grant failed'; exit 1 }
# 2) then remove inherited entries (this is what drops "Authenticated Users" from this folder)
& icacls $dir /inheritance:r
if ($LASTEXITCODE -ne 0) { Write-Output 'icacls /inheritance:r failed'; exit 1 }

Write-Output ''
Write-Output "NTFS permissions on $dir :"
& icacls $dir
& net use $share /delete /y *> $null
