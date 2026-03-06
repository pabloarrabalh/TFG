#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Usa configuración DOCKER
  
.DESCRIPTION
  Copia .env.docker a .env
  
.EXAMPLE
  .\use-docker-env.ps1
#>

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🐳 CAMBIANDO A CONFIGURACIÓN DOCKER" -ForegroundColor Blue
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

if (-Not (Test-Path ".env.docker")) {
    Write-Host "❌ .env.docker no encontrado" -ForegroundColor Red
    exit 1
}

# Hacer backup del .env actual
if (Test-Path ".env") {
    Copy-Item ".env" ".env.backup" -Force
    Write-Host "📦 Backup anterior guardado en .env.backup" -ForegroundColor Gray
}

# Copiar .env.docker a .env
Copy-Item ".env.docker" ".env" -Force

Write-Host ""
Write-Host "✅ CONFIGURACIÓN DOCKER ACTIVADA" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Configuración:" -ForegroundColor Cyan
Write-Host "   PostgreSQL: db:5432 (en contenedor)" -ForegroundColor White
Write-Host "   OpenSearch: opensearch:9200 (en contenedor)" -ForegroundColor White
Write-Host ""
Write-Host "🚀 Ahora puedes correr:" -ForegroundColor Yellow
Write-Host "   .\run-all.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
