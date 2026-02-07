.PHONY: help build up down logs migrate test lint format clean seed

help:
	@echo "REDPEN - Makefile Commands"
	@echo "========================="
	@echo "build       - Build Docker images"
	@echo "up          - Start all services"
	@echo "down        - Stop all services"
	@echo "logs        - Show logs"
	@echo "migrate     - Run database migrations"
	@echo "makemigrations - Create new migration"
	@echo "seed        - Seed database with demo data"
	@echo "test        - Run tests"
	@echo "test-cov    - Run tests with coverage"
	@echo "lint        - Run linter"
	@echo "format      - Format code"
	@echo "clean       - Clean up containers and volumes"
	@echo "shell       - Open backend shell"
	@echo "psql        - Open PostgreSQL shell"

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Waiting for services to start..."
	@sleep 5
	@echo "Services are running!"
	@echo "API: http://localhost:8000"
	@echo "API Docs: http://localhost:8000/docs"
	@echo "MinIO Console: http://localhost:9001 (user: redpen_minio / pass: redpen_minio_secret_key_123)"
	@echo "Flower (Celery Monitor): http://localhost:5555"

down:
	docker-compose down

logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f api

logs-worker:
	docker-compose logs -f worker

migrate:
	docker-compose exec api alembic upgrade head

makemigrations:
	@read -p "Enter migration message: " msg; \
	docker-compose exec api alembic revision --autogenerate -m "$$msg"

seed:
	docker-compose exec api python -m app.seed

test:
	docker-compose exec api pytest

test-cov:
	docker-compose exec api pytest --cov=app --cov-report=html --cov-report=term

lint:
	docker-compose exec api ruff check app/

format:
	docker-compose exec api black app/
	docker-compose exec api ruff check --fix app/

clean:
	docker-compose down -v
	rm -rf backend/__pycache__
	rm -rf backend/app/__pycache__
	rm -rf minio-data

shell:
	docker-compose exec api bash

psql:
	docker-compose exec postgres psql -U redpen -d redpen_db

restart:
	docker-compose restart api worker
