## Bornă — pipeline entry points. Run `make help`.

SHELL := /bin/bash
-include .env
export

POSTGRES_DB       ?= borna
POSTGRES_USER     ?= borna
POSTGRES_PASSWORD ?= borna
POSTGRES_PORT     ?= 5432
PG_DSN := postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@localhost:$(POSTGRES_PORT)/$(POSTGRES_DB)
export PG_DSN

VENV := .venv
PY   := $(VENV)/bin/python
RUN  := cd pipeline && ../$(PY) -m
SOURCES ?=   # e.g. make download SOURCES=osm (default: all)

.DEFAULT_GOAL := help
.PHONY: help setup check-tools db-up db-down db-reset psql download import register lrs attributes qa tiles web-dev web-build test

help: ## Show this help
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

## --- environment ---------------------------------------------------------

setup: $(VENV) ## Create the Python 3.12 venv and install pipeline deps
$(VENV): pipeline/pyproject.toml
	python3.12 -m venv $(VENV)
	$(VENV)/bin/pip install -U pip
	$(VENV)/bin/pip install -e "pipeline[dev]"
	@touch $(VENV)

check-tools: ## Report which required tools are installed
	@for t in docker python3.12 ogr2ogr osm2pgsql tippecanoe duckdb node; do \
	  if command -v $$t >/dev/null && bash -c "$$t --version >/dev/null 2>&1; exit \$$?" 2>/dev/null; then printf "  ok       %s\n" $$t; \
	  else printf "  MISSING  %s\n" $$t; fi; done

db-up: ## Start PostGIS (docker compose)
	docker compose up -d --wait db

db-down: ## Stop PostGIS (keeps data)
	docker compose down

db-reset: ## Destroy the DB volume and recreate it from pipeline/sql/00_schema.sql
	docker compose down -v
	docker compose up -d --wait db

psql: ## Open a psql shell in the DB container
	docker compose exec db psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

## --- pipeline (ROADMAP §4) -----------------------------------------------

download: setup ## Phase 1: fetch public sources into data/raw/ (SOURCES=osm overture)
	$(RUN) borna.download $(SOURCES)

import: setup db-up ## Phase 1: load data/raw/ into PostGIS (raw schema)
	$(RUN) borna.importer $(SOURCES)

register: setup db-up ## Phase 1.3: parse HG 540/2000 annexes into borna.road
	$(RUN) borna.register

lrs: setup db-up ## Phase 2: match register to geometry, calibrate km
	$(RUN) borna.lrs $(ARGS)

attributes: setup db-up ## Phase 2: surface, lanes, speed, bridges, AADT onto road km ranges
	$(RUN) borna.attributes

qa: setup db-up ## Phase 2: QA report vs INS + gap report (data/out/qa/)
	$(RUN) borna.qa

tiles: setup db-up ## Phase 3: export PMTiles, road files, search index to web/public/data/
	$(RUN) borna.tiles

web-dev: ## Phase 3: run the site locally at http://localhost:4321 (after make tiles)
	cd web && npm install && npm run dev

web-build: ## Phase 3: build the static site into web/dist/
	cd web && npm install && npm run build

test: setup ## Run pipeline unit tests and lint
	cd pipeline && ../$(VENV)/bin/pytest -q && ../$(VENV)/bin/ruff check borna tests
