param([switch]$Build, [switch]$BridgeOnly, [switch]$SkipWebBuild)

$ErrorActionPreference = 'Stop'
$settingsPath = Join-Path $PSScriptRoot 'runs\delivery\settings.json'
if (-not (Test-Path -LiteralPath $settingsPath)) { throw '请先运行 tools/setup_delivery.py 配置运行依赖。' }
$settings = Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
$bridgeRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\get_jobs'))
$env:JAVA_HOME = $settings.java_home
$env:Path = "$env:JAVA_HOME\bin;$env:Path"
$env:JOBSEARCH_BRIDGE_TOKEN = $settings.bridge_token
$env:JOBSEARCH_BOSS_ONLY = 'true'
$env:JOBSEARCH_BROWSER_CHANNEL = $settings.browser_channel
$env:SERVER_ADDRESS = '127.0.0.1'
$env:PYTHONUTF8 = '1'
if (-not (Test-Path -LiteralPath (Join-Path $bridgeRoot 'db\getjobs.db'))) { throw 'get_jobs 缺少发行版提供的 db/getjobs.db。' }
Push-Location -LiteralPath $bridgeRoot
try {
    if ($Build) {
        & $settings.gradle bootJar installPatchrightDriver -x buildFrontend --console=plain
        if ($LASTEXITCODE -ne 0) { throw '投递服务构建失败。' }
    }
    $jar = Join-Path $bridgeRoot 'build\libs\get_jobs-2.0.1.jar'
    if (-not (Test-Path -LiteralPath $jar)) { throw '缺少投递服务构建，请运行 start-integrated.ps1 -Build。' }
    $listener = Get-NetTCPConnection -LocalPort 9527 -State Listen -ErrorAction SilentlyContinue
    if (-not $listener) {
        $logDirectory = Join-Path $bridgeRoot '.artifacts\service'
        New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
        $arguments = @('-Dfile.encoding=UTF-8', '-Dsun.stdout.encoding=UTF-8', '-jar', ('"' + $jar + '"'))
        Start-Process -FilePath (Join-Path $env:JAVA_HOME 'bin\java.exe') -ArgumentList $arguments `
            -WorkingDirectory $bridgeRoot -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $logDirectory 'stdout.log') `
            -RedirectStandardError (Join-Path $logDirectory 'stderr.log') | Out-Null
    }
}
finally { Pop-Location }
if ($BridgeOnly) { return }
& (Join-Path $PSScriptRoot 'start-web.ps1') -SkipBuild:$SkipWebBuild
