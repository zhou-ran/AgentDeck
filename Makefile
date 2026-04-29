.PHONY: install install-dev build-frontend dev prod test test-verbose lint clean

# --- Install ---
install: build-frontend
	pip install -e .

install-dev: build-frontend
	pip install -e ".[dev]"

# --- Frontend ---
build-frontend:
	cd frontend && npm install && npm run build

# --- Dev mode (backend + frontend concurrently) ---
dev:
	@echo "Starting dev mode..."
	@echo "  Backend:  http://localhost:9797"
	@echo "  Frontend: http://localhost:5173"
	@trap 'kill 0' EXIT; \
	  uvicorn backend.main:app --reload --host 127.0.0.1 --port 9797 & \
	  cd frontend && npm run dev & \
	  wait

# --- Production mode ---
prod: build-frontend
	agent-foreman-local serve --host 127.0.0.1 --port 9797

# --- Tests ---
test:
	python -m pytest tests/ -v

test-verbose:
	python -m pytest tests/ -v --tb=long -x

# --- Lint ---
lint:
	cd frontend && npx tsc --noEmit

# --- Clean ---
clean:
	rm -rf frontend/dist frontend/node_modules
	rm -rf backend/static/assets backend/static/index.html
	rm -rf build dist *.egg-info __pycache__ backend/__pycache__ backend/api/__pycache__
	rm -rf .pytest_cache tests/__pycache__
