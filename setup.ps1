# Windows Setup Script
# Run this in PowerShell: .\setup.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Multi-Tenant Billing Platform Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "Checking Python installation..." -ForegroundColor Yellow
python --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Python is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

# Create virtual environment
Write-Host ""
Write-Host "Creating virtual environment..." -ForegroundColor Yellow
python -m venv venv

# Activate virtual environment
Write-Host ""
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
.\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install --upgrade pip
pip install -r requirements.txt

# Copy .env file
Write-Host ""
Write-Host "Setting up environment variables..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env file created. Please update with your configuration." -ForegroundColor Green
} else {
    Write-Host ".env file already exists." -ForegroundColor Yellow
}

# Database setup prompt
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Database Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Please ensure PostgreSQL is installed and running." -ForegroundColor Yellow
Write-Host "Database: billing_platform_db" -ForegroundColor Yellow
Write-Host ""
$continue = Read-Host "Have you created the database? (y/n)"

if ($continue -eq "y" -or $continue -eq "Y") {
    # Run migrations
    Write-Host ""
    Write-Host "Running migrations..." -ForegroundColor Yellow
    python manage.py makemigrations
    python manage.py migrate
    
    # Create superuser
    Write-Host ""
    Write-Host "Creating superuser for admin access..." -ForegroundColor Yellow
    python manage.py createsuperuser
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Setup Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Update .env file with your configuration" -ForegroundColor White
    Write-Host "2. Start the server: python manage.py runserver" -ForegroundColor White
    Write-Host "3. Visit http://localhost:8000/admin/" -ForegroundColor White
    Write-Host "4. Check QUICKSTART.md for API testing" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "Please create the database first:" -ForegroundColor Yellow
    Write-Host "1. Open psql or pgAdmin" -ForegroundColor White
    Write-Host "2. Run: CREATE DATABASE billing_platform_db;" -ForegroundColor White
    Write-Host "3. Run this setup script again" -ForegroundColor White
    Write-Host ""
}
