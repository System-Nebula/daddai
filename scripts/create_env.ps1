# Create .env file with Neo4j configuration
$envContent = @"
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=default666

# LMStudio Configuration
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_MODEL=local-model

# Embedding Configuration
EMBEDDING_MODEL=all-MiniLM-L6-v2
USE_GPU=auto
EMBEDDING_BATCH_SIZE=64
"@

$envContent | Out-File -FilePath ".env" -Encoding utf8
Write-Host ".env file created successfully!" -ForegroundColor Green
Write-Host "Password set to: default666" -ForegroundColor Yellow

