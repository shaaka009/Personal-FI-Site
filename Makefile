SHELL := /bin/zsh

PYTHON := $(shell if [ -x backend/.venv/bin/python ]; then echo backend/.venv/bin/python; else echo python3; fi)
PIP := $(shell if [ -x backend/.venv/bin/pip ]; then echo backend/.venv/bin/pip; else echo pip3; fi)

.PHONY: help backend-install backend-migrate backend-run backend-test backend-shell \
	frontend-install frontend-run plaid-sync db-summary dev-note

help:
	@echo "Personal FI helper targets"
	@echo ""
	@echo "Setup:"
	@echo "  make backend-install   Create venv deps (if venv active, install there)"
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
	@echo "  make backend-test      Run backend tests"
	@echo "  make backend-shell     Open Django shell"

backend-install:
	cd backend && $(PIP) install django djangorestframework django-cors-headers plaid-python python-dotenv

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

dev-note:
	@echo "Open two terminals:"
	@echo "  Terminal 1: make backend-run"
	@echo "  Terminal 2: make frontend-run"
