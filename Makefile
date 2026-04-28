.PHONY: up down backend frontend install

up:
	docker-compose up -d

down:
	docker-compose down

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

install:
	pip install -r backend/requirements.txt
	cd frontend && npm install
