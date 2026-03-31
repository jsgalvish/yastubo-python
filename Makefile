.PHONY: install lint format typecheck test test-fast test-cov qa clean

PYTHON := python
PYTEST := pytest
RUFF   := ruff
MYPY   := mypy

# ─────────────────── Setup ───────────────────────────────────────────────────

install:
	$(PYTHON) -m pip install -e ".[dev]"

# ─────────────────── Lint & Format ───────────────────────────────────────────

lint:
	$(RUFF) check app/ tests/ services/

lint-fix:
	$(RUFF) check --fix app/ tests/ services/

format:
	$(RUFF) format app/ tests/ services/

format-check:
	$(RUFF) format --check app/ tests/ services/

# ─────────────────── Type checking ───────────────────────────────────────────

typecheck:
	$(MYPY) app/

# ─────────────────── Tests ───────────────────────────────────────────────────

test:
	$(PYTEST)

test-fast:
	$(PYTEST) --no-cov -x

test-unit:
	$(PYTEST) -m unit --no-cov

test-integration:
	$(PYTEST) -m integration

test-cov:
	$(PYTEST) --cov=app --cov-report=html:coverage_html --cov-report=term-missing

# ─────────────────── Full QA pipeline ────────────────────────────────────────

qa: format-check lint typecheck test
	@echo "✅ QA pipeline complete"

# ─────────────────── Utils ───────────────────────────────────────────────────

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "coverage_html" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".coverage" -delete 2>/dev/null || true
