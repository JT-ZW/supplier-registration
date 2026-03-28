# Quick Docker Test Script for Windows PowerShell
# Run this to test your Docker setup locally

Write-Host "================================" -ForegroundColor Cyan
Write-Host "  Docker Setup Test Script" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "Checking Docker..." -ForegroundColor Yellow
$dockerRunning = docker info 2>$null
if (-not $?) {
    Write-Host "❌ Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}
Write-Host "✅ Docker is running" -ForegroundColor Green
Write-Host ""

# Check for .env files
Write-Host "Checking environment files..." -ForegroundColor Yellow

if (-not (Test-Path "backend\.env")) {
    Write-Host "⚠️  backend\.env not found. Creating from example..." -ForegroundColor Yellow
    if (Test-Path "backend\.env.example") {
        Copy-Item "backend\.env.example" "backend\.env"
        Write-Host "   Created backend\.env - PLEASE EDIT IT WITH YOUR ACTUAL VALUES" -ForegroundColor Magenta
    } else {
        Write-Host "❌ backend\.env.example not found" -ForegroundColor Red
    }
} else {
    Write-Host "✅ backend\.env exists" -ForegroundColor Green
}

if (-not (Test-Path "frontend\.env.local")) {
    Write-Host "⚠️  frontend\.env.local not found. Creating from example..." -ForegroundColor Yellow
    if (Test-Path "frontend\.env.example") {
        Copy-Item "frontend\.env.example" "frontend\.env.local"
        Write-Host "   Created frontend\.env.local - PLEASE EDIT IT WITH YOUR ACTUAL VALUES" -ForegroundColor Magenta
    } else {
        Write-Host "❌ frontend\.env.example not found" -ForegroundColor Red
    }
} else {
    Write-Host "✅ frontend\.env.local exists" -ForegroundColor Green
}

Write-Host ""

# Ask user if they want to continue
Write-Host "Ready to build and start containers?" -ForegroundColor Yellow
Write-Host "This will:" -ForegroundColor White
Write-Host "  1. Build Docker images (may take a few minutes)" -ForegroundColor White
Write-Host "  2. Start backend on http://localhost:8000" -ForegroundColor White
Write-Host "  3. Start frontend on http://localhost:3000" -ForegroundColor White
Write-Host ""

$response = Read-Host "Continue? (Y/N)"
if ($response -ne "Y" -and $response -ne "y") {
    Write-Host "Cancelled." -ForegroundColor Yellow
    exit 0
}

# Build and start containers
Write-Host ""
Write-Host "Building and starting containers..." -ForegroundColor Yellow
Write-Host "(This may take 2-5 minutes on first run)" -ForegroundColor Gray
Write-Host ""

docker-compose up -d --build

if ($?) {
    Write-Host ""
    Write-Host "================================" -ForegroundColor Green
    Write-Host "  ✅ Containers Started!" -ForegroundColor Green
    Write-Host "================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "🌐 Access your apps:" -ForegroundColor Cyan
    Write-Host "   Backend API:  http://localhost:8000/docs" -ForegroundColor White
    Write-Host "   Frontend:     http://localhost:3000" -ForegroundColor White
    Write-Host ""
    Write-Host "📊 Useful commands:" -ForegroundColor Cyan
    Write-Host "   View logs:    docker-compose logs -f" -ForegroundColor White
    Write-Host "   Stop:         docker-compose down" -ForegroundColor White
    Write-Host "   Restart:      docker-compose restart" -ForegroundColor White
    Write-Host "   Status:       docker-compose ps" -ForegroundColor White
    Write-Host ""
    
    # Show container status
    Write-Host "Container Status:" -ForegroundColor Cyan
    docker-compose ps
    
} else {
    Write-Host ""
    Write-Host "❌ Failed to start containers" -ForegroundColor Red
    Write-Host "Check the error messages above." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Common issues:" -ForegroundColor Yellow
    Write-Host "  - Missing or invalid .env files" -ForegroundColor White
    Write-Host "  - Ports 3000 or 8000 already in use" -ForegroundColor White
    Write-Host "  - Docker daemon not running" -ForegroundColor White
    exit 1
}
