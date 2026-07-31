.PHONY: setup up down migrate logs clean install-skills test

setup:
	cp .env.example .env
	pip install -r requirements.txt
	python scripts/install_skills.py

up:
	docker compose up -d postgres redis qdrant
	@echo "Waiting for databases to be ready..."
	@sleep 8
	docker compose up -d

down:
	docker compose down

migrate:
	alembic upgrade head

logs:
	docker compose logs -f api agent-orchestrator prediction-engine forecast-evaluator

clean:
	docker compose down -v

install-skills:
	python scripts/install_skills.py

test:
	pytest tests/ -v --tb=short

lint:
	python -m py_compile agents/base_agent.py graph/state.py risk/circuit_breakers.py

# Phase 1: Start research platform only (no trading)
phase1:
	docker compose up -d postgres redis qdrant api prediction-engine forecast-evaluator prometheus grafana
	@echo ""
	@echo "=== Phase 1: Research Platform ==="
	@echo "API:            http://localhost:8000"
	@echo "API Docs:       http://localhost:8000/docs"
	@echo "Grafana:        http://localhost:3001  (admin/admin)"
	@echo "MLflow:         http://localhost:5000"
	@echo "Prometheus:     http://localhost:9090"
	@echo ""
	@echo "Forecasts dashboard: http://localhost:8000/forecasts/dashboard?symbol=BTC/USDT"
	@echo "Pending approvals:   http://localhost:8000/approvals/pending"
	@echo "System status:       http://localhost:8000/system/status"
	@echo "Kill switch:         POST http://localhost:8000/system/kill-switch/activate"
