param(
 [ValidateSet('setup','check','a','b','control','c','all','inventory','report','cleanup')]
 [string]$Action='report',
 [double]$Rps=6, [double]$HpaRps=24
)
$ErrorActionPreference='Stop'
$labRoot=Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $labRoot
$env:PATH=(Join-Path $labRoot '.tools')+';'+$env:PATH
$env:KUBECONFIG=Join-Path $labRoot '.runtime/kubeconfig'
$env:HELM_CACHE_HOME=Join-Path $labRoot '.runtime/helm/cache'
$env:HELM_CONFIG_HOME=Join-Path $labRoot '.runtime/helm/config'
$env:HELM_DATA_HOME=Join-Path $labRoot '.runtime/helm/data'
$env:NO_PROXY='localhost,127.0.0.1,::1'
$env:PYTHONUTF8='1'
$env:MPLCONFIGDIR=Join-Path $labRoot '.runtime/matplotlib'
& (Join-Path $labRoot '.venv/Scripts/python.exe') -u -m tools.lab $Action --rps $Rps --hpa-rps $HpaRps
exit $LASTEXITCODE
