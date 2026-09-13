.PHONY: setup dev serve build test lint clean

setup:
	./setup.sh

dev:
	uv run craybee dev

serve:
	uv run craybee serve

build:
	uv run craybee build

test:
	uv run pytest
	cd frontend && npm test

lint:
	uv run ruff check backend tests
	cd frontend && npm run typecheck

clean:
	rm -rf backend/static frontend/dist frontend/node_modules
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
