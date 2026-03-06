#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Inicia OpenSearch en Docker (debajo de Windows)
  
.DESCRIPTION
  Este script levanta OpenSearch usando docker-compose
  
.EXAMPLE
  .\start-opensearch.ps1
#>

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🚀 INICIANDO OPENSEARCH EN DOCKER" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# Verificar si Docker está instalado
Write-Host "📦 Verificando Docker..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version
    Write-Host "✓ Docker instalado: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker NO está instalado" -ForegroundColor Red
    Write-Host "   Descargalo desde: https://www.docker.com/products/docker-desktop" -ForegroundColor Red
    exit 1
}

# Verificar si docker-compose.yml existe
Write-Host ""
Write-Host "📄 Verificando docker-compose.yml..." -ForegroundColor Yellow
if (-Not (Test-Path "docker-compose.yml")) {
    Write-Host "❌ docker-compose.yml no encontrado" -ForegroundColor Red
    exit 1
}
Write-Host "✓ docker-compose.yml encontrado" -ForegroundColor Green

# Verificar si .env existe
Write-Host ""
Write-Host "⚙️  Verificando .env..." -ForegroundColor Yellow
if (-Not (Test-Path ".env")) {
    Write-Host "❌ .env no encontrado" -ForegroundColor Red
    exit 1
}
Write-Host "✓ .env configurado" -ForegroundColor Green

# Iniciar servicios
Write-Host ""
Write-Host "🔧 Iniciando servicios (PostgreSQL + OpenSearch)..." -ForegroundColor Yellow
Write-Host ""
docker-compose up -d

Write-Host ""
Write-Host "⏳ Esperando a que OpenSearch esté listo (esto toma ~15-30 segundos)..." -ForegroundColor Yellow

# Esperar a que OpenSearch esté disponible
$maxAttempts = 60
$attempt = 0
$opensearchReady = $false

while ($attempt -lt $maxAttempts) {
    try {
        $response = curl.exe -s -u admin:Admin_Password1! http://localhost:9200/_cluster/health
        if ($response) {
            $opensearchReady = $true
            break
        }
    } catch {
        # Silencio, reintentar
    }
    
    $attempt++
    Start-Sleep -Seconds 1
}

Write-Host ""
if ($opensearchReady) {
    Write-Host "✅ OpenSearch ESTÁ LISTO EN http://localhost:9200" -ForegroundColor Green
    Write-Host ""
    Write-Host "📊 Info de OpenSearch:" -ForegroundColor Cyan
    Write-Host "   Host: localhost:9200" -ForegroundColor White
    Write-Host "   Usuario: admin" -ForegroundColor White
    Write-Host "   Contraseña: Admin_Password1!" -ForegroundColor White
    Write-Host ""
    Write-Host "✓ Ya puedes iniciar el servidor Django:" -ForegroundColor Green
    Write-Host "   python manage.py runserver" -ForegroundColor Cyan
} else {
    Write-Host "⚠️  OpenSearch tardó en iniciar. Esperando..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Verifica el estado con:" -ForegroundColor Yellow
    Write-Host "   docker-compose ps" -ForegroundColor Cyan
    Write-Host "   curl -u admin:Admin_Password1! http://localhost:9200" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
