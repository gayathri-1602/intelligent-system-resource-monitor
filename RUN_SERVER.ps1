#!/usr/bin/env powershell

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                                                                ║" -ForegroundColor Cyan
Write-Host "║        🚀 Starting Intelligent System Monitor...              ║" -ForegroundColor Cyan
Write-Host "║                                                                ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Activate virtual environment
Write-Host "✅ Activating virtual environment..." -ForegroundColor Green
& ".\.venv\Scripts\Activate.ps1"

# Run the app
Write-Host ""
Write-Host "✅ Starting Flask application..." -ForegroundColor Green
Write-Host ""
Write-Host "📊 Dashboard available at: http://localhost:5000" -ForegroundColor Yellow
Write-Host ""
Write-Host "ℹ️  Press CTRL+C to stop the server" -ForegroundColor Magenta
Write-Host ""

& ".\.venv\Scripts\python.exe" app.py

# Keep window open
Write-Host ""
Write-Host "Server stopped. Press any key to close..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
