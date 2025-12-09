#!/bin/bash
# Unix/Linux/Mac Setup Script
# Run with: bash setup.sh

echo "========================================"
echo "Multi-Tenant Billing Platform Setup"
echo "========================================"
echo ""

# Check Python
echo "Checking Python installation..."
python3 --version
if [ $? -ne 0 ]; then
    echo "Error: Python 3 is not installed or not in PATH"
    exit 1
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Copy .env file
echo ""
echo "Setting up environment variables..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ".env file created. Please update with your configuration."
else
    echo ".env file already exists."
fi

# Database setup prompt
echo ""
echo "========================================"
echo "Database Setup"
echo "========================================"
echo ""
echo "Please ensure PostgreSQL is installed and running."
echo "Database: billing_platform_db"
echo ""
read -p "Have you created the database? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Run migrations
    echo ""
    echo "Running migrations..."
    python manage.py makemigrations
    python manage.py migrate
    
    # Create superuser
    echo ""
    echo "Creating superuser for admin access..."
    python manage.py createsuperuser
    
    echo ""
    echo "========================================"
    echo "Setup Complete!"
    echo "========================================"
    echo ""
    echo "Next steps:"
    echo "1. Update .env file with your configuration"
    echo "2. Start the server: python manage.py runserver"
    echo "3. Visit http://localhost:8000/admin/"
    echo "4. Check QUICKSTART.md for API testing"
    echo ""
else
    echo ""
    echo "Please create the database first:"
    echo "1. Run: createdb billing_platform_db"
    echo "   Or use psql: CREATE DATABASE billing_platform_db;"
    echo "2. Run this setup script again"
    echo ""
fi
