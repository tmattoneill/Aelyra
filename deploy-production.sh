#!/bin/bash

# PlayMaker Production Deployment Script
# Run this on your production server (ubuntu@moneill:~/PlayMaker)

echo "🚀 Starting PlayMaker Multi-User Production Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    print_error "Not in PlayMaker directory. Please cd to ~/PlayMaker first."
    exit 1
fi

print_status "Step 1: Creating backup..."
BACKUP_DIR="../PlayMaker-backup-$(date +%Y%m%d-%H%M%S)"
cp -r . "$BACKUP_DIR"
print_status "Backup created at: $BACKUP_DIR"

print_status "Step 2: Pulling latest code..."
git fetch origin
git checkout main
git pull origin main

print_status "Step 3: Activating virtual environment..."
source .venv/bin/activate

print_status "Step 4: Installing new dependencies..."
pip install -r requirements.txt

print_status "Step 5: Checking current .env configuration..."
if grep -q "DATABASE_URL" .env; then
    print_status "DATABASE_URL already configured"
else
    print_warning "Adding DATABASE_URL to .env..."
    echo "" >> .env
    echo "# Database Configuration" >> .env
    echo "DATABASE_URL=sqlite:///./playmaker.db" >> .env
    print_status "DATABASE_URL added to .env"
fi

print_status "Step 6: Setting up database with Alembic..."
# Initialize database schema
alembic upgrade head

print_status "Step 7: Updating frontend dependencies..."
cd frontend
npm install
print_status "Step 8: Building frontend for production..."
npm run build
cd ..

print_status "Step 9: Verifying installation..."
if [ -f "playmaker.db" ]; then
    print_status "Database created successfully"
else
    print_error "Database not found - check for errors above"
    exit 1
fi

print_status "🎉 Deployment completed successfully!"
echo ""
print_warning "Next steps:"
echo "1. Restart your web service (systemd/supervisor/pm2)"
echo "2. Test the application at https://aelyra.moneill.net"
echo "3. Verify multi-user features work"
echo ""
print_status "Backup location: $BACKUP_DIR"