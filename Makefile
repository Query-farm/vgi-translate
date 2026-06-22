# vgi-translate — test targets.
#
# Usage:
#   make test         # unit tests + SQL (end-to-end) tests
#   make test-unit    # pytest unit/integration suite
#   make test-offline # pytest with download-gated tests skipped (offline-safe)
#   make test-sql     # DuckDB sqllogictest E2E via haybarn-unittest
#   make lint         # ruff + mypy
#
# The SQL E2E suite drives the *real* worker as a DuckDB subprocess through the
# haybarn-unittest sqllogictest runner. It is self-contained: `test-sql`
# installs the runner and the Argos en->es language package if they are missing.

# The worker command DuckDB runs for the `vgi` extension's ATTACH.
VGI_TRANSLATE_WORKER ?= uv run --python 3.13 translate_worker.py

# haybarn-unittest is a uv tool; ~/.local/bin must be on PATH to find it.
HAYBARN ?= haybarn-unittest
LOCAL_BIN := $(HOME)/.local/bin

TEST_DIR     = .
TEST_PATTERN = test/sql/*

.PHONY: test test-unit test-offline test-sql lint ensure-haybarn ensure-en-es

test: test-unit test-sql

# Full unit suite (the en->es download test self-skips if the package can't be
# installed, so this stays green offline).
test-unit:
	uv run pytest -q

# Offline-safe subset: skip every download-gated test outright.
test-offline:
	uv run pytest -q -m "not download"

# Install the haybarn-unittest sqllogictest runner if it isn't already present.
ensure-haybarn:
	@if ! PATH="$(LOCAL_BIN):$$PATH" command -v $(HAYBARN) >/dev/null 2>&1; then \
		echo "Installing haybarn-unittest..."; \
		uv tool install haybarn-unittest; \
	fi

# Pre-install the Argos en->es package so the real-translation E2E tests pass.
ensure-en-es:
	@uv run python scripts/ensure_argos_pair.py en es \
		|| echo 'WARNING: could not install Argos en->es (offline?); real-translation E2E tests may fail'

# End-to-end SQL tests: load `vgi`, ATTACH the worker, run the .test glob.
# CRITICAL: under haybarn-unittest, `require vgi` SKIPS — the .test files use an
# explicit `LOAD vgi;` instead.
test-sql: ensure-haybarn ensure-en-es
	PATH="$(LOCAL_BIN):$$PATH" VGI_TRANSLATE_WORKER="$(VGI_TRANSLATE_WORKER)" \
		$(HAYBARN) --test-dir "$(TEST_DIR)" "$(TEST_PATTERN)"

lint:
	uv run ruff check .
	uv run mypy vgi_translate/ || true
