.PHONY: dev worker api test eval-report

dev:
	@echo "Starting Temporal dev server..."
	temporal server start-dev &
	sleep 2
	@echo "Starting worker..."
	python -m app.worker &
	sleep 1
	@echo "Starting API..."
	uvicorn app.api.main:app --port 8000

worker:
	python -m app.worker

api:
	uvicorn app.api.main:app --reload --port 8000

test:
	pytest tests/ -v

eval-report:
	python scripts/eval_report.py