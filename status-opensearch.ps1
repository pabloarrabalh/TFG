#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Muestra el estado de los servicios de Docker
  
.EXAMPLE
  .\status-opensearch.ps1
#>

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "📊 ESTADO DE SERVICIOS DOCKER" -ForegroundColor Blue
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

docker-compose ps

Write-Host ""
Write-Host "🔍 Verificando OpenSearch..." -ForegroundColor Yellow
try {
    $response = curl.exe -s -u admin:Admin_Password1! http://localhost:9200/_cluster/health
    if ($response) {
        Write-Host "✅ OpenSearch está ACTIVO" -ForegroundColor Green
        Write-Host ""
        Write-Host "Info:" -ForegroundColor Cyan
        curl.exe -s -u admin:Admin_Password1! http://localhost:9200/_cluster/health | ConvertFrom-Json | Format-Table
    }
} catch {
    Write-Host "❌ OpenSearch no responde" -ForegroundColor Red
    Write-Host "   Asegurate de que docker-compose está corriendo:" -ForegroundColor Yellow
    Write-Host "   .\start-opensearch.ps1" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
