# Makefile for matchcaller project

.PHONY: help install test test-unit test-integration test-ui test-coverage test-fast test-snapshots lint clean run-demo run

# Default target
help:
	@echo "Available targets:"
	@echo "  install        - Install dependencies"
	@echo "  test           - Run all tests"
	@echo "  test-unit      - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-ui        - Run UI tests only"
	@echo "  test-coverage  - Run tests with coverage report"
	@echo "  test-fast      - Run fast tests (skip slow ones)"
	@echo "  test-snapshots - Update snapshot tests"
	@echo "  lint           - Run linting (if available)"
	@echo "  clean          - Clean up generated files"
	@echo "  run-demo       - Run app in demo mode"
	@echo "  run            - Run app (requires API_TOKEN and EVENT_SLUG env vars)"

# Installation
install:
	pip install -r requirements.txt

# Test targets
test:
	python run_tests.py

test-unit:
	python run_tests.py --unit

test-integration:
	python run_tests.py --integration

test-ui:
	python run_tests.py --ui

test-coverage:
	python run_tests.py --coverage

test-fast:
	python run_tests.py --fast

test-snapshots:
	python run_tests.py --snapshots

# Linting (optional, if you add linting tools)
lint:
	@echo "Linting not configured yet. Consider adding black, flake8, or ruff."

# Cleanup
clean:
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

# Run targets
run-demo:
	python matchcaller/matchcaller.py --demo

run:
	@if [ -z "$(API_TOKEN)" ]; then echo "Error: API_TOKEN environment variable required"; exit 1; fi
	@if [ -z "$(EVENT_SLUG)" ]; then echo "Error: EVENT_SLUG environment variable required"; exit 1; fi
	python matchcaller/matchcaller.py --token $(API_TOKEN) --slug $(EVENT_SLUG)