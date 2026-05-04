SHELL := /bin/zsh

# Paths are relative to backend/ because recipes use `cd backend && ...`.
PYTHON := $(shell if [ -x backend/.venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
PIP := $(shell if [ -x backend/.venv/bin/pip ]; then echo .venv/bin/pip; else echo pip3; fi)

.PHONY: help backend-install backend-migrate backend-run backend-test backend-shell \
	frontend-install frontend-run plaid-sync db-summary db-reset dev-note

help:
	@echo "Personal FI helper targets"
	@echo ""
	@echo "Setup:"
	@echo "  make backend-install   Create backend/.venv if missing, then install deps"
	@echo "  make backend-migrate   Run Django migrations"
	@echo "  make frontend-install  Install frontend dependencies"
	@echo ""
	@echo "Run:"
	@echo "  make backend-run       Start Django server on :8000"
	@echo "  make frontend-run      Start Vite dev server"
	@echo "  make dev-note          Print command hints for dual-terminal startup"
	@echo ""
	@echo "Data / checks:"
	@echo "  make plaid-sync        Trigger backend Plaid sync endpoint"
	@echo "  make db-summary        Show institutions/accounts/transactions counts"
	@echo "  make db-reset          Delete SQLite DB and re-run migrations (asks confirmation)"
	@echo "  make backend-test      Run backend tests"
	@echo "  make backend-shell     Open Django shell"

backend-install:
	cd backend && (test -x .venv/bin/python || python3 -m venv .venv) && .venv/bin/pip install -U pip && .venv/bin/pip install django djangorestframework django-cors-headers plaid-python python-dotenv

backend-migrate:
	cd backend && $(PYTHON) manage.py migrate

backend-run:
	cd backend && $(PYTHON) manage.py runserver

backend-test:
	cd backend && $(PYTHON) manage.py test

backend-shell:
	cd backend && $(PYTHON) manage.py shell

frontend-install:
	cd frontend && npm install

frontend-run:
	cd frontend && npm run dev

plaid-sync:
	curl -sS -X POST http://localhost:8000/api/plaid/sync | python3 -m json.tool

db-summary:
	cd backend && $(PYTHON) -c "import sqlite3; c=sqlite3.connect('db.sqlite3').cursor(); print('Plaid items:', c.execute('select count(*) from app_plaiditem').fetchone()[0]); print('Accounts:', c.execute('select count(*) from app_account').fetchone()[0]); print('Transactions:', c.execute('select count(*) from app_transaction').fetchone()[0]); print('Institutions:'); [print('-', (name or '<blank>'), '| success:', succ, '| last_sync_at:', last_at) for name,succ,last_at in c.execute('select institution_name, last_sync_success, last_sync_at from app_plaiditem order by institution_name')]"

db-reset:
	@echo ""; \
	echo "WARNING: This permanently deletes backend/db.sqlite3 (and WAL sidecars if present)."; \
	echo "You will lose:"; \
	echo "  - All Plaid items and stored access tokens"; \
	echo "  - All accounts and transactions synced into this app"; \
	echo ""; \
	echo "Stop the Django dev server first if it is running (recommended)."; \
	echo ""; \
	printf "Type RESET if you understand and want to continue: "; \
	read confirm; \
	if [[ "$$confirm" != "RESET" ]]; then echo "Aborted."; exit 1; fi; \
	cd backend && rm -f db.sqlite3 db.sqlite3-shm db.sqlite3-wal && $(PYTHON) manage.py migrate --noinput; \
	echo ""; \
	echo "Database reset complete. Use Connect Institution in the app to link banks again."

dev-note:
	@echo "Open two terminals:"
	@echo "  Terminal 1: make backend-run"
	@echo "  Terminal 2: make frontend-run"
