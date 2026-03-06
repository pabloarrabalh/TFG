#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Inicia TUTTO: OpenSearch + PostgreSQL + Django
  
.DESCRIPTION
  Este es el script all-in-one que inicia todo lo necesario
  
.EXAMPLE
  .\run-all.ps1
#>

Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                                                           ║" -ForegroundColor Cyan
Write-Host "║         🚀 INICIANDO APLICACIÓN COMPLETA 🚀              ║" -ForegroundColor Cyan
Write-Host "║     (OpenSearch + PostgreSQL + Django)                   ║" -ForegroundColor Cyan
Write-Host "║                                                           ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Verificar Docker
Write-Host "📦 Verificando Docker..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version 2>$null
    if ($dockerVersion) {
        Write-Host "✓ Docker disponible" -ForegroundColor Green
    } else {
        throw "Docker no responde"
    }
} catch {
    Write-Host "❌ Docker NO está disponible" -ForegroundColor Red
    Write-Host "   Descargalo: https://www.docker.com/products/docker-desktop" -ForegroundColor Red
    exit 1
}

# Iniciar Docker en background
Write-Host ""
Write-Host "🐳 Iniciando OpenSearch + PostgreSQL en Docker..." -ForegroundColor Yellow
docker-compose up -d

# Esperar a que OpenSearch esté listo
Write-Host ""
Write-Host "⏳ Esperando a que OpenSearch esté listo..." -ForegroundColor Yellow

$maxAttempts = 60
$attempt = 0
$opensearchReady = $false

while ($attempt -lt $maxAttempts) {
    try {
        $response = curl.exe -s -u admin:Admin_Password1! http://localhost:9200/_cluster/health 2>$null
        if ($response) {
            $opensearchReady = $true
            break
        }
    } catch {
        # Silencio
    }
    
    $attempt++
    Start-Sleep -Seconds 1
    
    if ($attempt % 10 -eq 0) {
        Write-Host "   Intentando... $attempt/60" -ForegroundColor DarkYellow
    }
}

Write-Host ""
if ($opensearchReady) {
    Write-Host "✅ OpenSearch LISTO" -ForegroundColor Green
} else {
    Write-Host "⚠️  OpenSearch tardó mucho. Continuando..." -ForegroundColor Yellow
}

# Activar venv
Write-Host ""
Write-Host "🐍 Activando Python venv..." -ForegroundColor Yellow
& .\.venv311\Scripts\Activate.ps1
Write-Host "✓ venv activado" -ForegroundColor Green

# Mostrar info
Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║              ✅ SERVICIOS INICIADOS                       ║" -ForegroundColor Cyan
Write-Host "╠═══════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║                                                           ║" -ForegroundColor Cyan
Write-Host "║  🗄️  PostgreSQL:                                          ║" -ForegroundColor Cyan
Write-Host "║     Host: localhost:5432                                  ║" -ForegroundColor Cyan
Write-Host "║     DB: laliga | User: user1 | Pass: user1              ║" -ForegroundColor Cyan
Write-Host "║                                                           ║" -ForegroundColor Cyan
Write-Host "║  🔍 OpenSearch:                                           ║" -ForegroundColor Cyan
Write-Host "║     Host: http://localhost:9200                          ║" -ForegroundColor Cyan
Write-Host "║     User: admin | Pass: Admin_Password1!                ║" -ForegroundColor Cyan
Write-Host "║                                                           ║" -ForegroundColor Cyan
Write-Host "║  🚀 Iniciando Django...                                   ║" -ForegroundColor Cyan
Write-Host "║                                                           ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Iniciar Django
Write-Host "Django starting at http://127.0.0.1:8000" -ForegroundColor Yellow
Write-Host "" 
Write-Host "⏹️  Para detener: Presiona CTRL+C (aquí)" -ForegroundColor DarkYellow
Write-Host "    Y en otra terminal: .\stop-opensearch.ps1" -ForegroundColor DarkYellow
Write-Host ""

python manage.py runserver
