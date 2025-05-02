# CF0 Monorepo

This project is structured as an Nx monorepo containing three applications:

- `frontend`: Next.js web application
- `api-gateway`: FastAPI backend service
- `workers`: Python worker processes for background tasks

## Prerequisites

- Node.js 18+
- Python 3.12+
- Docker Desktop
- Supabase account
- Railway account

## Tools Already Installed

The following tools have been installed globally:

- Nx CLI: `npm i -g nx@latest`
- Railway CLI: `curl -sL https://railway.app/install.sh | sh`
- Supabase CLI: `brew install supabase/tap/supabase`
- Docker Desktop: `brew install --cask docker`

## Getting Started

### 1. Setup Environment Variables

Create the following files with appropriate Supabase credentials:

- `apps/frontend/.env.local`
```
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon>
```

- `apps/api-gateway/.env`
```
DATABASE_URL=postgresql://.../postgres?sslmode=require
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service-role>
```

- `apps/workers/.env`
```
DATABASE_URL=postgresql://.../postgres?sslmode=require
SUPABASE_SERVICE_ROLE_KEY=<service-role>
```

### 2. Running Locally with Docker

```bash
# Start Docker Desktop
open -a Docker

# Start all services with Docker Compose
npm run docker:up

# Or using Docker Compose directly
docker compose up --build
```

Visit:
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs

### 3. Development Workflow

#### Using Nx

```bash
# Start all services in development mode
npm start

# Start individual services
npm run dev:frontend
npm run dev:api
npm run dev:workers

# Build all services
npm run build

# Run tests
npm run test

# Lint code
npm run lint
```

### 4. Database Migrations

```bash
# Login to Supabase
supabase login

# Link to your Supabase project
supabase link --project-ref <project-ref>

# Pull the current schema
supabase db pull

# Push new migrations
supabase db push
```

### 5. Deployment

The project is set up to deploy automatically to Railway through GitHub Actions.
Each push to the main branch triggers a deployment.

## Project Structure

```
cf0/
  ├── apps/
  │   ├── frontend/      # Next.js application
  │   ├── api-gateway/   # FastAPI service
  │   └── workers/       # Python workers
  ├── libs/
  │   └── common/        # Shared types and utilities
  ├── .github/
  │   └── workflows/     # GitHub Actions CI/CD
  ├── docker-compose.yml # Local development
  └── nx.json            # Nx configuration
```

## Additional Resources

- [Nx Documentation](https://nx.dev)
- [Railway Documentation](https://docs.railway.app)
- [Supabase Documentation](https://supabase.io/docs) 