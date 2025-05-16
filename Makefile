.PHONY: api workers frontend

# Development commands
api:
	cd apps/api-gateway && poetry run uvicorn main:app --reload

workers:
	cd apps/workers && poetry run python worker.py

frontend:
	cd apps/frontend && npm run dev

# Setup commands
setup-api:
	cd apps/api-gateway && poetry install

setup-workers:
	cd apps/workers && poetry install

setup-frontend:
	cd apps/frontend && npm install

setup: setup-api setup-workers setup-frontend
	@echo "All dependencies installed"

# Environment handling
api-env:
	cd apps/api-gateway && cp .env.example .env

workers-env:
	cd apps/workers && cp .env.example .env

frontend-env:
	cd apps/frontend && cp .env.example .env.local

setup-env: api-env workers-env frontend-env
	@echo "Environment files created, please update them with your credentials"

# Reset current Poetry environments in case of issues
reset-poetry:
	cd apps/api-gateway && rm -rf .venv || true
	cd apps/workers && rm -rf .venv || true
	@echo "Poetry environments have been reset" 