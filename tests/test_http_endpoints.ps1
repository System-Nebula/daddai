# PowerShell script to test HTTP endpoints
# Usage: .\test_http_endpoints.ps1

Write-Host "=== Testing HTTP Endpoints ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Note: Start HTTP servers first:" -ForegroundColor Yellow
Write-Host "  python src/api/memory_server_http.py"
Write-Host "  python src/api/chat_server_http.py"
Write-Host ""

# Test Memory Service
Write-Host "1. Testing Memory Service..." -ForegroundColor Green
Write-Host "   Health check:"
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8766/health" -Method Get
    $response | ConvertTo-Json
} catch {
    Write-Host "   Error: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "   Ping:"
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8766/ping" -Method Get
    $response | ConvertTo-Json
} catch {
    Write-Host "   Error: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "   Store memory:"
try {
    $body = @{
        channel_id = "test_123"
        content = "Test memory"
        memory_type = "conversation"
    } | ConvertTo-Json
    
    $response = Invoke-RestMethod -Uri "http://localhost:8766/store" -Method Post -Body $body -ContentType "application/json"
    $response | ConvertTo-Json
} catch {
    Write-Host "   Error: $_" -ForegroundColor Red
}

# Test Chat Service
Write-Host ""
Write-Host "2. Testing Chat Service..." -ForegroundColor Green
Write-Host "   Health check:"
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8767/health" -Method Get
    $response | ConvertTo-Json
} catch {
    Write-Host "   Error: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "   Ping:"
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8767/ping" -Method Get
    $response | ConvertTo-Json
} catch {
    Write-Host "   Error: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "   Chat:"
try {
    $body = @{
        message = "Hello, test!"
    } | ConvertTo-Json
    
    $response = Invoke-RestMethod -Uri "http://localhost:8767/chat" -Method Post -Body $body -ContentType "application/json"
    $response | ConvertTo-Json
} catch {
    Write-Host "   Error: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Test Complete ===" -ForegroundColor Cyan

