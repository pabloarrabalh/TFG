#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Usa configuración LOCAL (sin Docker)
  
.DESCRIPTION
  Copia .env.local a .env
  
.EXAMPLE
  .\use-local-env.ps1
#>

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "⚙️  CAMBIANDO A CONFIGURACIÓN LOCAL" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

if (-Not (Test-Path ".env.local")) {
    Write-Host "❌ .env.local no encontrado" -ForegroundColor Red
    exit 1
}

# Hacer backup del .env actual
if (Test-Path ".env") {
    Copy-Item ".env" ".env.backup" -Force
    Write-Host "📦 Backup anterior guardado en .env.backup" -ForegroundColor Gray
}

# Copiar .env.local a .env
Copy-Item ".env.local" ".env" -Force

Write-Host ""
Write-Host "✅ CONFIGURACIÓN LOCAL ACTIVADA" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Configuración:" -ForegroundColor Cyan
Write-Host "   PostgreSQL: localhost:5432" -ForegroundColor White
Write-Host "   OpenSearch: localhost:9200" -ForegroundColor White
Write-Host ""
Write-Host "🚀 Ahora puedes correr:" -ForegroundColor Yellow
Write-Host "   python manage.py runserver" -ForegroundColor Cyan
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
