# PowerShell script to set up Elasticsearch

Write-Host "Setting up Elasticsearch..." -ForegroundColor Green

# Check if .env file exists
if (Test-Path .env) {
    Write-Host "[OK] Found .env file" -ForegroundColor Green
    
    # Check if Elasticsearch is already enabled
    $envContent = Get-Content .env -Raw
    if ($envContent -match "ELASTICSEARCH_ENABLED") {
        Write-Host "[WARN] ELASTICSEARCH_ENABLED already exists in .env" -ForegroundColor Yellow
        Write-Host "   Please set ELASTICSEARCH_ENABLED=true manually" -ForegroundColor Yellow
    } else {
        # Add Elasticsearch config to .env
        Add-Content .env "`n# Elasticsearch Configuration"
        Add-Content .env "ELASTICSEARCH_ENABLED=true"
        Add-Content .env "ELASTICSEARCH_HOST=localhost"
        Add-Content .env "ELASTICSEARCH_PORT=9200"
        Write-Host "[OK] Added Elasticsearch configuration to .env" -ForegroundColor Green
    }
} else {
    Write-Host "Creating .env file..." -ForegroundColor Yellow
    # Create .env file with Elasticsearch config
    @"
# Elasticsearch Configuration
ELASTICSEARCH_ENABLED=true
ELASTICSEARCH_HOST=localhost
ELASTICSEARCH_PORT=9200
"@ | Out-File -FilePath .env -Encoding utf8
    Write-Host "[OK] Created .env file with Elasticsearch configuration" -ForegroundColor Green
}

Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "1. Run migration: python migrate_to_elasticsearch.py" -ForegroundColor White
Write-Host "2. Restart your application" -ForegroundColor White
Write-Host "`nElasticsearch is ready to use!" -ForegroundColor Green

