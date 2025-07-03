#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🚀 Starting CF0 Local Development Environment${NC}"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo -e "${YELLOW}📋 Checking prerequisites...${NC}"
for cmd in docker docker-compose node python3 nx; do
    if command_exists $cmd; then
        echo -e "${GREEN}✅ $cmd is installed${NC}"
    else
        echo -e "${RED}❌ $cmd is not installed${NC}"
        exit 1
    fi
done

# Create local env files if they don't exist
if [ ! -f apps/api-gateway/.env.local ]; then
    echo -e "${YELLOW}📝 Creating local environment files...${NC}"
    cp .env.example apps/api-gateway/.env.local || echo "No .env.example found"
    cp .env.example apps/frontend/.env.local || echo "No .env.example found"
    cp .env.example apps/workers/.env.local || echo "No .env.example found"
    
    # Update with local values
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' 's|your_supabase_url|http://localhost:9999|g' apps/*/.env.local 2>/dev/null || true
        sed -i '' 's|postgresql://.*|postgresql://postgres:YOUR-DB-PASSWORD@localhost:5432/postgres|g' apps/*/.env.local 2>/dev/null || true
    else
        # Linux
        sed -i 's|your_supabase_url|http://localhost:9999|g' apps/*/.env.local 2>/dev/null || true
        sed -i 's|postgresql://.*|postgresql://postgres:YOUR-DB-PASSWORD@localhost:5432/postgres|g' apps/*/.env.local 2>/dev/null || true
    fi
fi

# Stop any existing containers
echo -e "${YELLOW}🧹 Cleaning up existing containers...${NC}"
docker-compose -f docker-compose.local.yml down 2>/dev/null || true

# Start services
echo -e "${YELLOW}🐳 Starting Docker services...${NC}"
docker-compose -f docker-compose.local.yml up -d

# Wait for postgres to be ready
echo -e "${YELLOW}⏳ Waiting for PostgreSQL to be ready...${NC}"
until docker-compose -f docker-compose.local.yml exec -T postgres pg_isready >/dev/null 2>&1; do
    echo -n "."
    sleep 1
done
echo ""

# Wait a bit more for services to fully initialize
sleep 5

# Run migrations
echo -e "${YELLOW}📊 Running database migrations...${NC}"
for migration in supabase/migrations/*.sql; do
    if [ -f "$migration" ]; then
        echo "Applying $(basename $migration)..."
        docker-compose -f docker-compose.local.yml exec -T postgres \
            psql -U postgres -d postgres -f /docker-entrypoint-initdb.d/$(basename $migration) || true
    fi
done

# Seed test data
if [ -f scripts/seed-test-data.py ]; then
    echo -e "${YELLOW}🌱 Seeding test data...${NC}"
    docker-compose -f docker-compose.local.yml exec -T api-gateway \
        python scripts/seed-test-data.py || echo "Seed script not ready yet"
fi

echo -e "${GREEN}✅ Local environment ready!${NC}"
echo ""
echo "Services available at:"
echo "  Frontend: http://localhost:3000"
echo "  API: http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo "  Supabase Studio: http://localhost:3001"
echo "  Mailhog: http://localhost:8025"
echo "  Prometheus: http://localhost:9090"
echo "  Grafana: http://localhost:3002 (admin/admin)"
echo ""
echo "To view logs: docker-compose -f docker-compose.local.yml logs -f"
echo "To stop: docker-compose -f docker-compose.local.yml down" 