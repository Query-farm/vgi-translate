# vgi-translate — dev and test targets. `make help` lists them.
#
#   make test         # unit tests + SQL (end-to-end) tests over stdio, launch and http
#   make test-unit    # pytest unit/integration suite
#   make test-offline # pytest with download-gated tests skipped (offline-safe)
#   make test-sql     # test/sql/*.test through DuckDB via ci/run-integration.sh
#   make lint         # ruff + mypy
#
# The SQL suite drives the *real* worker through the haybarn-unittest runner. It
# is self-contained: `test-sql` installs the runner and the Argos en->es / es->en
# language packages if they are missing.

HAYBARN_VERSION  ?= 2.0.1rc3
WORKER           := $(CURDIR)/.venv/bin/vgi-translate-worker
TOOLS            := $(CURDIR)/.tools
HAYBARN_UNITTEST := $(TOOLS)/bin/haybarn-unittest
TRANSPORTS       ?= stdio launch http

build: ## Install the worker (all extras: HTTP serving needs `http`) into .venv
	uv sync --locked --all-extras

tools: ## Install the pinned SQL test runner into .tools
	@test -x $(HAYBARN_UNITTEST) || { uv venv -q $(TOOLS) && uv pip install -q -p $(TOOLS) haybarn-unittest==$(HAYBARN_VERSION); }

test-sql: build tools ensure-en-es ## SQL tests through DuckDB over each transport: make test-sql TRANSPORTS=launch
	@set -e; for t in $(TRANSPORTS); do \
	  WORKER=$(WORKER) HAYBARN_UNITTEST=$(HAYBARN_UNITTEST) TRANSPORT=$$t ci/run-integration.sh; \
	done

test-sql-all: test-sql ## Alias: SQL tests over every transport

.DEFAULT_GOAL := help
.PHONY: help build tools test test-unit test-offline test-sql test-sql-all lint check ensure-en-es

help: ## List the targets
	@awk 'BEGIN{FS=":.*## "} /^[a-zA-Z_-]+:.*## /{printf "  %-14s %s\n",$$1,$$2}' $(MAKEFILE_LIST)

test: test-unit test-sql ## Unit + SQL tests

check: lint test ## Lint + unit + SQL tests

# Full unit suite (the en->es download test self-skips if the package can't be
# installed, so this stays green offline).
test-unit: build ## Unit tests (pytest)
	uv run pytest -q

# Offline-safe subset: skip every download-gated test outright.
test-offline: ## Unit tests with download-gated tests skipped
	uv run pytest -q -m "not download"

# Pre-install the Argos en->es (and es->en, used by the composed examples)
# packages so the real-translation E2E tests pass.
ensure-en-es: build ## Install the Argos en->es / es->en packages
	@uv run python scripts/ensure_argos_pair.py en es \
		|| echo 'WARNING: could not install Argos en->es (offline?); real-translation E2E tests may fail'
	@uv run python scripts/ensure_argos_pair.py es en \
		|| echo 'WARNING: could not install Argos es->en (offline?); composed E2E tests may fail'

lint: ## ruff + mypy
	uv run ruff check .
	uv run mypy vgi_translate/ || true
