# Neo4j Desktop Installation Script for Windows
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Neo4j Desktop Installation" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$downloadUrl = "https://dist.neo4j.org/neo4j-desktop/neo4j-desktop-1.5.20-x64-setup.exe"
$installerPath = "$env:USERPROFILE\Downloads\neo4j-desktop-installer.exe"

Write-Host "Downloading Neo4j Desktop..." -ForegroundColor Yellow
try {
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $downloadUrl -OutFile $installerPath -UseBasicParsing
    Write-Host "Download complete!" -ForegroundColor Green
    Write-Host "Installer saved to: $installerPath" -ForegroundColor Green
    Write-Host ""
    Write-Host "To install Neo4j Desktop:" -ForegroundColor Cyan
    Write-Host "1. Navigate to: $installerPath" -ForegroundColor White
    Write-Host "2. Double-click the installer and follow the setup wizard" -ForegroundColor White
    Write-Host "3. After installation, launch Neo4j Desktop" -ForegroundColor White
    Write-Host "4. Create a new project and database" -ForegroundColor White
    Write-Host "5. Set a password (remember it for your .env file)" -ForegroundColor White
    Write-Host "6. Start the database" -ForegroundColor White
    Write-Host ""
    Write-Host "Would you like to run the installer now? (Y/N)" -ForegroundColor Yellow
    $response = Read-Host
    if ($response -eq 'Y' -or $response -eq 'y') {
        Start-Process $installerPath
        Write-Host "Installer launched!" -ForegroundColor Green
    }
} catch {
    Write-Host "Error downloading Neo4j Desktop: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please download manually from:" -ForegroundColor Yellow
    Write-Host "https://neo4j.com/download/" -ForegroundColor Cyan
}

