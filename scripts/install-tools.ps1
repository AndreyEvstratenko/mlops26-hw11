$ErrorActionPreference='Stop'
$labRoot=Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $labRoot
New-Item -ItemType Directory -Force .tools,vendor,evidence,.runtime | Out-Null
function Download-Verified([string]$Uri,[string]$ChecksumUri,[string]$Target){
 Invoke-WebRequest -Uri $Uri -OutFile $Target -TimeoutSec 180
 $expected=((Invoke-WebRequest -Uri $ChecksumUri -TimeoutSec 60).Content.Trim() -split '\s+')[0].ToLower()
 $actual=(Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLower()
 if($actual -ne $expected){throw "Checksum mismatch: $Target"}
 "$actual  $Target" | Add-Content evidence/downloads.sha256
}
Download-Verified 'https://kind.sigs.k8s.io/dl/v0.27.0/kind-windows-amd64' 'https://kind.sigs.k8s.io/dl/v0.27.0/kind-windows-amd64.sha256sum' '.tools/kind.exe'
Download-Verified 'https://dl.k8s.io/release/v1.32.2/bin/windows/amd64/kubectl.exe' 'https://dl.k8s.io/release/v1.32.2/bin/windows/amd64/kubectl.exe.sha256' '.tools/kubectl.exe'
Download-Verified 'https://get.helm.sh/helm-v3.17.2-windows-amd64.zip' 'https://get.helm.sh/helm-v3.17.2-windows-amd64.zip.sha256sum' '.tools/helm.zip'
Expand-Archive -LiteralPath '.tools/helm.zip' -DestinationPath '.tools/helm-unpacked' -Force
Copy-Item -LiteralPath '.tools/helm-unpacked/windows-amd64/helm.exe' -Destination '.tools/helm.exe'
Invoke-WebRequest -Uri 'https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.7.2/components.yaml' -OutFile 'vendor/metrics-server.yaml' -TimeoutSec 60
if(-not(Test-Path -LiteralPath '.venv/Scripts/python.exe')){py -3.12 -m venv .venv; if($LASTEXITCODE){throw 'Python 3.12 is required (install from python.org, including the py launcher)'}}
& ./.venv/Scripts/python.exe -m pip install --require-hashes -r requirements.lock
if($LASTEXITCODE){throw 'Dependency installation failed'}
& ./.venv/Scripts/python.exe -m pip install -r requirements-report.lock
if($LASTEXITCODE){throw 'Report dependencies installation failed'}
Write-Host 'Ready. Next: powershell -ExecutionPolicy Bypass -File scripts/lab.ps1 setup'
