#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Detiene todos los servicios de Docker
  
.DESCRIPTION
  Este script detiene y elimina los contenedores
  
.EXAMPLE
  .\stop-opensearch.ps1
#>

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "⛔ DETENIENDO SERVICIOS DE DOCKER" -ForegroundColor Red
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

Write-Host "🛑 Deteniendo contenedores..." -ForegroundColor Yellow
docker-compose down

Write-Host ""
Write-Host "✅ Servicios detenidos" -ForegroundColor Green
Write-Host ""
