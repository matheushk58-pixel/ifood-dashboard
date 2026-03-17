# Dashboard iFood - Allury Perfumaria
# Execute com: .\run_server.ps1

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $dir

Write-Host ""
Write-Host "  ====================================" -ForegroundColor Red
Write-Host "   Dashboard iFood - Allury Perfumaria" -ForegroundColor Red
Write-Host "  ====================================" -ForegroundColor Red
Write-Host ""

# Verifica Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[ERRO] Python nao encontrado. Instale em https://python.org" -ForegroundColor Red
    Read-Host "Pressione Enter para sair"
    exit 1
}

# Instala dependencias se necessario
$fastapi = python -c "import fastapi" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Instalando dependencias..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

Write-Host "Servidor iniciado em http://localhost:9000" -ForegroundColor Green
Write-Host "Pressione Ctrl+C para parar." -ForegroundColor Gray
Write-Host ""

# Abre o navegador
Start-Process "http://localhost:9000"

# Inicia o servidor
python ifood_server.py
