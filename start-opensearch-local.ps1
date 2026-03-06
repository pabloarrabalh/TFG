Write-Host "Starting OpenSearch locally..." -ForegroundColor Cyan

$OPENSEARCH_VERSION = "3.5.0"
$OPENSEARCH_HOME = "$PSScriptRoot\opensearch-$OPENSEARCH_VERSION"

if (Test-Path $OPENSEARCH_HOME) {
    Write-Host "OpenSearch $OPENSEARCH_VERSION found at $OPENSEARCH_HOME" -ForegroundColor Green
} else {
    Write-Host "OpenSearch $OPENSEARCH_VERSION not found at $OPENSEARCH_HOME" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Configuring OpenSearch..." -ForegroundColor Yellow

$CONFIG_FILE = "$OPENSEARCH_HOME\config\opensearch.yml"
$CONFIG_CONTENT = @"
cluster.name: opensearch-cluster
node.name: opensearch-node
discovery.type: single-node
plugins.security.disabled: true
OPENSEARCH_INITIAL_ADMIN_PASSWORD: admin
path.logs: $OPENSEARCH_HOME\logs
"@

if (-Not (Test-Path $CONFIG_FILE)) {
    Set-Content -Path $CONFIG_FILE -Value $CONFIG_CONTENT
    Write-Host "opensearch.yml created" -ForegroundColor Green
} else {
    Write-Host "opensearch.yml already exists" -ForegroundColor Green
}

Write-Host ""
Write-Host "Starting OpenSearch..." -ForegroundColor Yellow

$STARTUP_SCRIPT = "$OPENSEARCH_HOME\bin\opensearch.bat"

if (Test-Path $STARTUP_SCRIPT) {
    Write-Host "Starting..." -ForegroundColor Cyan
    Write-Host "Endpoint: http://localhost:9200" -ForegroundColor Cyan
    Write-Host "User: admin" -ForegroundColor Cyan
    Write-Host "Password: admin" -ForegroundColor Cyan
    Write-Host ""
    
    Start-Process $STARTUP_SCRIPT -NoNewWindow
    
    Start-Sleep -Seconds 5
    
    Write-Host "Waiting for OpenSearch..." -ForegroundColor Yellow
    
    $maxAttempts = 60
    $attempt = 0
    
    while ($attempt -lt $maxAttempts) {
        try {
            $response = curl.exe -s -u admin:admin http://localhost:9200/_cluster/health 2>$null
            if ($response) {
                Write-Host "OpenSearch is ready!" -ForegroundColor Green
                break
            }
        }
        catch {
            # Retry
        }
        
        $attempt++
        Start-Sleep -Seconds 1
    }
    
    Write-Host ""
    Write-Host "OpenSearch started successfully" -ForegroundColor Green
}
else {
    Write-Host "Not found: $STARTUP_SCRIPT" -ForegroundColor Red
    exit 1
}
