# Local Testing Guide for CF0 Development

## Overview

This guide provides comprehensive instructions for setting up a local development environment for CF0 that mirrors the production architecture while enabling rapid testing and debugging without pushing to git and waiting for deployments.

## Current State Analysis

### What's Working
- Basic Docker Compose for API and Workers
- Nx monorepo commands for coordinated builds
- Environment variable templates

### What's Missing
1. **Frontend not in Docker** - Requires separate manual startup
2. **No local Supabase** - Depends on cloud Supabase instance
3. **No hot reload** - Changes require container restart
4. **Manual database setup** - Migrations need Supabase CLI
5. **No integrated debugging** - Can't attach debuggers easily

## Recommended Local Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │     │  API Gateway    │     │    Workers      │
│  (Next.js)      │────▶│  (FastAPI)      │────▶│   (Python)      │
│  Port: 3000     │     │  Port: 8000     │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                        │
         └───────────────────────┴────────────────────────┘
                                │
                    ┌───────────────────────┐
                    │   Local Supabase      │
                    ├───────────────────────┤
                    │  PostgreSQL: 5432     │
                    │  Auth API: 9999       │
                    │  Storage: 8001        │
                    │  Studio: 3001         │
                    └───────────────────────┘
```

## Quick Start

### 1. Prerequisites Check

```bash
# Check required tools
./scripts/check-prerequisites.sh

# Expected output:
# ✅ Docker: installed
# ✅ Node.js: v18.17.0
# ✅ Python: 3.12.0
# ✅ Nx: 17.0.0
```

### 2. One-Command Setup

```bash
# Clone and setup everything
make local-setup

# This will:
# 1. Copy .env.example files
# 2. Start local Supabase
# 3. Run migrations
# 4. Seed test data
# 5. Start all services
```

### 3. Access Services

- **Frontend**: http://localhost:3000
- **API Gateway**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Supabase Studio**: http://localhost:3001
- **Mailhog** (emails): http://localhost:8025 

## Detailed Setup Instructions

### 1. Enhanced Docker Compose Configuration

Create `docker-compose.local.yml` in the project root:

```yaml
version: "3.9"

networks:
  cf0-network:
    driver: bridge

volumes:
  postgres-data:
  node-modules-frontend:
  node-modules-api:

services:
  # Local Supabase Stack
  postgres:
    image: supabase/postgres:15.1.0.117
    container_name: cf0-postgres
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: postgres
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./supabase/migrations:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    networks:
      - cf0-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  supabase-auth:
    image: supabase/gotrue:v2.132.3
    container_name: cf0-auth
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      GOTRUE_DB_DATABASE_URL: postgresql://postgres:YOUR-DB-PASSWORD@postgres:5432/postgres?search_path=auth
      GOTRUE_SITE_URL: http://localhost:3000
      GOTRUE_URI_ALLOW_LIST: http://localhost:3000
      GOTRUE_JWT_SECRET: super-secret-jwt-token-for-local-dev
      GOTRUE_JWT_EXP: 3600
      GOTRUE_SMTP_HOST: mailhog
      GOTRUE_SMTP_PORT: 1025
      GOTRUE_SMTP_SENDER: noreply@cf0.local
    ports:
      - "9999:9999"
    networks:
      - cf0-network

  supabase-storage:
    image: supabase/storage-api:v0.40.4
    container_name: cf0-storage
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      STORAGE_BACKEND: file
      FILE_STORAGE_BACKEND_PATH: /var/lib/storage
      DATABASE_URL: postgresql://postgres:YOUR-DB-PASSWORD@postgres:5432/postgres?search_path=storage
      PGRST_JWT_SECRET: super-secret-jwt-token-for-local-dev
      ANON_KEY: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
      SERVICE_KEY: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    volumes:
      - ./data/storage:/var/lib/storage
    ports:
      - "8001:5000"
    networks:
      - cf0-network

  # Email testing
  mailhog:
    image: mailhog/mailhog
    container_name: cf0-mailhog
    ports:
      - "1025:1025"  # SMTP
      - "8025:8025"  # Web UI
    networks:
      - cf0-network

  # API Gateway with hot reload
  api-gateway:
    build:
      context: ./apps/api-gateway
      dockerfile: Dockerfile.dev
    container_name: cf0-api
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://postgres:YOUR-DB-PASSWORD@postgres:5432/postgres
      SUPABASE_URL: http://supabase-auth:9999
      SUPABASE_SERVICE_ROLE_KEY: ${SUPABASE_SERVICE_ROLE_KEY:-local-dev-key}
      PYTHONUNBUFFERED: 1
      WATCHDOG_ENABLE: 1
      DEBUG: 1
    volumes:
      - ./apps/api-gateway:/app
      - /app/__pycache__
      - /app/.venv
    command: |
      sh -c "pip install watchdog[watchmedo] && 
             watchmedo auto-restart --recursive --pattern='*.py' -- 
             uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
    ports:
      - "8000:8000"
      - "5678:5678"  # Python debugger port
    networks:
      - cf0-network

  # Frontend with hot reload
  frontend:
    build:
      context: ./apps/frontend
      dockerfile: Dockerfile.dev
    container_name: cf0-frontend
    environment:
      NEXT_PUBLIC_SUPABASE_URL: http://localhost:9999
      NEXT_PUBLIC_SUPABASE_ANON_KEY: ${NEXT_PUBLIC_SUPABASE_ANON_KEY:-local-anon-key}
      NEXT_PUBLIC_API_URL: http://localhost:8000
      NODE_ENV: development
      WATCHPACK_POLLING: true
    volumes:
      - ./apps/frontend:/app
      - node-modules-frontend:/app/node_modules
      - /app/.next
    ports:
      - "3000:3000"
    networks:
      - cf0-network

  # Workers
  workers:
    build:
      context: ./apps/workers
      dockerfile: Dockerfile.dev
    container_name: cf0-workers
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://postgres:YOUR-DB-PASSWORD@postgres:5432/postgres
      PYTHONUNBUFFERED: 1
    volumes:
      - ./apps/workers:/app
      - /app/__pycache__
      - /app/.venv
    command: |
      sh -c "pip install watchdog[watchmedo] && 
             watchmedo auto-restart --recursive --pattern='*.py' -- 
             python worker.py"
    networks:
      - cf0-network

  # Supabase Studio (Optional)
  supabase-studio:
    image: supabase/studio:latest
    container_name: cf0-studio
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      SUPABASE_URL: http://supabase-auth:9999
      STUDIO_PG_META_URL: http://postgres:5432
    ports:
      - "3001:3000"
    networks:
      - cf0-network
```

### 2. Development Dockerfiles

Create `apps/api-gateway/Dockerfile.dev`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install dev dependencies
RUN pip install --no-cache-dir \
    watchdog[watchmedo] \
    debugpy \
    pytest \
    pytest-asyncio \
    httpx

# Copy application code
COPY . .

# Enable Python debugging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000 5678

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

Create `apps/frontend/Dockerfile.dev`:

```dockerfile
FROM node:18-alpine

WORKDIR /app

# Install dependencies for better performance
RUN apk add --no-cache libc6-compat

# Copy package files
COPY package*.json ./
COPY yarn.lock* ./
COPY pnpm-lock.yaml* ./

# Install dependencies based on lockfile
RUN \
  if [ -f yarn.lock ]; then yarn install --frozen-lockfile; \
  elif [ -f package-lock.json ]; then npm ci; \
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm install --frozen-lockfile; \
  else echo "No lockfile found." && exit 1; \
  fi

# Copy application code
COPY . .

# Expose ports
EXPOSE 3000

# Enable hot reload
ENV NODE_ENV=development
ENV WATCHPACK_POLLING=true

CMD ["npm", "run", "dev"]
``` 

### 3. Helper Scripts

Create `scripts/local-dev.sh`:

```bash
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
    cp .env.example apps/api-gateway/.env.local
    cp .env.example apps/frontend/.env.local
    cp .env.example apps/workers/.env.local
    
    # Update with local values
    sed -i '' 's|your_supabase_url|http://localhost:9999|g' apps/*/.env.local
    sed -i '' 's|postgresql://.*|postgresql://postgres:YOUR-DB-PASSWORD@localhost:5432/postgres|g' apps/*/.env.local
fi

# Start services
echo -e "${YELLOW}🐳 Starting Docker services...${NC}"
docker-compose -f docker-compose.local.yml up -d

# Wait for postgres to be ready
echo -e "${YELLOW}⏳ Waiting for PostgreSQL to be ready...${NC}"
until docker-compose -f docker-compose.local.yml exec -T postgres pg_isready; do
    sleep 1
done

# Run migrations
echo -e "${YELLOW}📊 Running database migrations...${NC}"
for migration in supabase/migrations/*.sql; do
    echo "Applying $migration..."
    docker-compose -f docker-compose.local.yml exec -T postgres \
        psql -U postgres -d postgres -f /docker-entrypoint-initdb.d/$(basename $migration)
done

# Seed test data
echo -e "${YELLOW}🌱 Seeding test data...${NC}"
docker-compose -f docker-compose.local.yml exec -T api-gateway \
    python scripts/seed-test-data.py

echo -e "${GREEN}✅ Local environment ready!${NC}"
echo ""
echo "Services available at:"
echo "  Frontend: http://localhost:3000"
echo "  API: http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo "  Supabase Studio: http://localhost:3001"
echo "  Mailhog: http://localhost:8025"
echo ""
echo "To view logs: docker-compose -f docker-compose.local.yml logs -f"
echo "To stop: docker-compose -f docker-compose.local.yml down"
```

Create `scripts/seed-test-data.py`:

```python
#!/usr/bin/env python3
import asyncio
import os
from datetime import datetime
from supabase import create_client
import json

async def seed_test_data():
    """Seed local database with test data"""
    
    # Initialize Supabase client
    supabase_url = os.getenv("SUPABASE_URL", "http://localhost:9999")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "local-dev-key")
    
    supabase = create_client(supabase_url, supabase_key)
    
    print("🌱 Seeding test data...")
    
    # Create test users
    test_users = [
        {
            "email": "test@example.com",
            "password": "testpassword123",
            "metadata": {"name": "Test User"}
        },
        {
            "email": "demo@example.com", 
            "password": "demopassword123",
            "metadata": {"name": "Demo User"}
        }
    ]
    
    created_users = []
    for user_data in test_users:
        try:
            response = supabase.auth.sign_up({
                "email": user_data["email"],
                "password": user_data["password"],
                "options": {"data": user_data["metadata"]}
            })
            created_users.append(response.user)
            print(f"✅ Created user: {user_data['email']}")
        except Exception as e:
            print(f"⚠️  User {user_data['email']} might already exist: {e}")
    
    # Create test workbooks
    if created_users:
        workbooks = [
            {
                "name": "Financial Model Template",
                "user_id": created_users[0].id,
                "created_at": datetime.now().isoformat()
            },
            {
                "name": "Q1 Budget Analysis",
                "user_id": created_users[0].id,
                "created_at": datetime.now().isoformat()
            }
        ]
        
        for wb in workbooks:
            response = supabase.table("workbooks").insert(wb).execute()
            print(f"✅ Created workbook: {wb['name']}")
    
    # Create sample prompts
    prompts = [
        {
            "role": "analyst",
            "version": "2.0",
            "content": "You are a financial analyst assistant...",
            "is_active": True
        },
        {
            "role": "ask",
            "version": "2.0", 
            "content": "You are a helpful spreadsheet assistant...",
            "is_active": True
        }
    ]
    
    for prompt in prompts:
        response = supabase.table("prompts").insert(prompt).execute()
        print(f"✅ Created prompt: {prompt['role']} v{prompt['version']}")
    
    print("🎉 Test data seeding complete!")

if __name__ == "__main__":
    asyncio.run(seed_test_data())
```

## Testing Strategies

### 1. API Testing Script

Create `scripts/test-api.sh`:

```bash
#!/bin/bash

API_URL="http://localhost:8000"

echo "🧪 Testing API endpoints..."

# Test health check
echo -n "Testing health check... "
response=$(curl -s -o /dev/null -w "%{http_code}" $API_URL/health)
if [ $response -eq 200 ]; then
    echo "✅ OK"
else
    echo "❌ Failed (HTTP $response)"
fi

# Test chat endpoint
echo -n "Testing chat endpoint... "
response=$(curl -s -X POST $API_URL/ask/stream \
    -H "Content-Type: application/json" \
    -d '{
        "message": "Hello, what is 2+2?",
        "wid": "test-workbook",
        "sid": "Sheet1",
        "model": "gpt-4o"
    }' \
    -o /dev/null -w "%{http_code}")
    
if [ $response -eq 200 ]; then
    echo "✅ OK"
else
    echo "❌ Failed (HTTP $response)"
fi

# Test workbook creation
echo -n "Testing workbook creation... "
response=$(curl -s -X POST $API_URL/workbook/test-wb/sheet \
    -H "Content-Type: application/json" \
    -d '{"name": "TestSheet"}' \
    -o /dev/null -w "%{http_code}")
    
if [ $response -eq 200 ]; then
    echo "✅ OK"
else
    echo "❌ Failed (HTTP $response)"
fi

echo "✅ API tests complete!"
```

### 2. Frontend E2E Tests

Create `apps/frontend/cypress/e2e/local-test.cy.ts`:

```typescript
describe('Local Development Tests', () => {
  beforeEach(() => {
    cy.visit('http://localhost:3000')
  })

  it('should load the homepage', () => {
    cy.contains('CF0').should('be.visible')
  })

  it('should connect to local API', () => {
    cy.request('http://localhost:8000/health').then((response) => {
      expect(response.status).to.eq(200)
      expect(response.body).to.have.property('status', 'healthy')
    })
  })

  it('should handle chat streaming', () => {
    cy.get('[data-testid="chat-input"]').type('Calculate sum of A1:A10')
    cy.get('[data-testid="send-button"]').click()
    
    // Wait for streaming to start
    cy.get('[data-testid="streaming-indicator"]').should('be.visible')
    
    // Wait for response
    cy.get('[data-testid="chat-message"]', { timeout: 10000 })
      .should('contain', 'sum')
  })
})
```

### 3. Load Testing

Create `scripts/load-test.js`:

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m', target: 20 },
    { duration: '30s', target: 0 },
  ],
};

export default function() {
  // Test chat endpoint
  const chatPayload = JSON.stringify({
    message: 'What is the sum of cells A1 to A10?',
    wid: 'test-workbook',
    sid: 'Sheet1',
    model: 'gpt-4o'
  });

  const chatResponse = http.post(
    'http://localhost:8000/ask/stream',
    chatPayload,
    { headers: { 'Content-Type': 'application/json' } }
  );

  check(chatResponse, {
    'chat status is 200': (r) => r.status === 200,
    'chat response time < 2s': (r) => r.timings.duration < 2000,
  });

  // Test workbook operations
  const workbookResponse = http.get('http://localhost:8000/workbook/test-wb/sheet/Sheet1');
  
  check(workbookResponse, {
    'workbook status is 200': (r) => r.status === 200,
  });

  sleep(1);
}
```

## Debugging Setup

### 1. VS Code Configuration

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug API Gateway (Docker)",
      "type": "python",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": 5678
      },
      "pathMappings": [
        {
          "localRoot": "${workspaceFolder}/apps/api-gateway",
          "remoteRoot": "/app"
        }
      ],
      "justMyCode": false
    },
    {
      "name": "Debug Frontend",
      "type": "node",
      "request": "attach",
      "port": 9229,
      "restart": true,
      "skipFiles": ["<node_internals>/**"],
      "sourceMapPathOverrides": {
        "webpack://_N_E/*": "${workspaceFolder}/apps/frontend/*"
      }
    },
    {
      "name": "Full Stack Debug",
      "configurations": ["Debug API Gateway (Docker)", "Debug Frontend"],
      "stopAll": true
    }
  ]
}
```

### 2. Enable Debugging in Docker

Update `docker-compose.local.yml` for API Gateway:

```yaml
api-gateway:
  # ... other config
  command: |
    sh -c "pip install debugpy && 
           python -m debugpy --listen 0.0.0.0:5678 --wait-for-client 
           -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
```

## Troubleshooting

### Common Issues

1. **Port conflicts**
   ```bash
   # Check what's using a port
   lsof -i :3000
   
   # Kill process using port
   kill -9 $(lsof -t -i:3000)
   ```

2. **Docker volume issues**
   ```bash
   # Clean up volumes
   docker-compose -f docker-compose.local.yml down -v
   
   # Rebuild without cache
   docker-compose -f docker-compose.local.yml build --no-cache
   ```

3. **Database connection issues**
   ```bash
   # Check postgres logs
   docker-compose -f docker-compose.local.yml logs postgres
   
   # Connect to postgres directly
   docker-compose -f docker-compose.local.yml exec postgres psql -U postgres
   ```

4. **Hot reload not working**
   - Ensure `WATCHPACK_POLLING=true` for frontend
   - Check volume mounts are correct
   - Verify file watchers are installed

## Best Practices

1. **Use environment-specific configs**
   - `.env.local` for local development
   - `.env.test` for testing
   - Never commit real credentials

2. **Keep containers lightweight**
   - Use multi-stage builds for production
   - Dev containers can have extra tools

3. **Regular cleanup**
   ```bash
   # Clean up unused containers/images
   docker system prune -a
   
   # Remove all CF0 containers
   docker-compose -f docker-compose.local.yml down --rmi all
   ```

4. **Monitor performance**
   - Use `docker stats` to monitor resource usage
   - Enable debug logging when needed
   - Profile slow operations

## Conclusion

This local testing setup provides:

1. **Complete local stack** - All services running locally
2. **Hot reload** - Changes reflect immediately
3. **Debugging support** - Attach debuggers to any service
4. **Test automation** - Scripts for various testing scenarios
5. **Production parity** - Mirrors production architecture

With this setup, you can develop and test changes locally without pushing to git or waiting for deployments, significantly speeding up the development cycle. 