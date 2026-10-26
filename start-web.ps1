param(
    [switch]$InstallDependencies,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    $savedConfiguration = Join-Path $PSScriptRoot 'runs\run-integration.env.ps1'
    if ((-not $env:JOBSEARCH_LLM_API_KEY) -and (Test-Path -LiteralPath $savedConfiguration)) {
        $null = . $savedConfiguration
    }
    if ($InstallDependencies) {
        py -3.11 -m pip install -r requirements-web.txt
        if ($LASTEXITCODE -ne 0) { throw 'Python 依赖安装失败。' }
    }
    py -3.11 -c "import fastapi, uvicorn, openai, httpx"
    if ($LASTEXITCODE -ne 0) { throw '请运行 .\start-web.ps1 -InstallDependencies 安装依赖。' }
    if (-not $SkipBuild) {
        Push-Location -LiteralPath (Join-Path $PSScriptRoot 'frontend')
        try {
            if (-not (Test-Path -LiteralPath 'node_modules')) {
                npm ci --no-audit --no-fund
                if ($LASTEXITCODE -ne 0) { throw 'React 依赖安装失败。' }
            }
            npm run build
            if ($LASTEXITCODE -ne 0) { throw 'React 界面构建失败。' }
        }
        finally { Pop-Location }
    }
    if (-not (Test-Path -LiteralPath 'frontend\dist\index.html')) { throw '缺少前端构建文件，请运行 .\start-web.ps1。' }
    Write-Host '求职 Agent 工作台：http://127.0.0.1:8765'
    py -3.11 -m jobsearch_agents.web
    if ($LASTEXITCODE -ne 0) { throw '求职 Agent 服务已异常终止。' }
}
finally { Pop-Location }
