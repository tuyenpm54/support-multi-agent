.PHONY: help install dev test test-unit test-integration lint format type-check clean init-db migrate-db seed-db reset-db build run

# Default target
help:
	@echo "Available commands:"
	@echo "  install     Install dependencies"
	@echo "  dev         Run development server"
	@echo "  test        Run all tests"
	@echo "  test-unit   Run unit tests"
	@echo "  test-integration Run integration tests"
	@echo "  lint        Run code linting"
	@echo "  format      Format code"
	@echo "  type-check   Run type checking"
	@echo "  clean       Clean up generated files"
	@echo "  init-db     Initialize database"
	@echo "  migrate-db  Run database migrations"
	@echo "  seed-db     Seed database with sample data"
	@echo "  reset-db    Reset database (dev only)"
	@echo "  build       Build Docker images"
	@echo "  run         Run with Docker Compose"

# Setup
install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pre-commit install

# Development
dev:
	uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000

# Database
init-db:
	psql $(DATABASE_URL) -f scripts/init_database.sql

migrate-db:
	alembic upgrade head

seed-db:
	python scripts/seed_database.py

reset-db:
	@echo "Dropping and recreating database..."
	dropdb support_system || true
	createdb support_system
	make init-db
	make seed-db

# Testing
test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

# Code quality
lint:
	flake8 src/ tests/
	mypy src/
	black --check src/ tests/
	isort --check-only src/ tests/

format:
	black src/ tests/
	isort src/ tests/

type-check:
	mypy src/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/

# Docker
build:
	docker-compose build

run:
	docker-compose up -d

# Production
deploy-dev:
	docker-compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up -d

deploy-prod:
	docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d