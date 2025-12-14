.PHONY: dev run db db-stop migrate seed test lint format install clean help

# 기본 명령어
help:
	@echo "Fast Light Chat - 사용 가능한 명령어"
	@echo ""
	@echo "  make dev        개발 서버 실행 (hot-reload)"
	@echo "  make run        프로덕션 모드 실행"
	@echo "  make db         DB 서비스만 실행 (PostgreSQL, MongoDB, Redis)"
	@echo "  make db-stop    DB 서비스 중지"
	@echo "  make db-ui      DB + 관리 UI 실행 (mongo-express, redis-commander)"
	@echo "  make up         전체 서비스 실행 (Docker)"
	@echo "  make down       전체 서비스 중지"
	@echo ""
	@echo "  make migrate    DB 마이그레이션 실행"
	@echo "  make seed       시드 데이터 생성"
	@echo ""
	@echo "  make test       테스트 실행"
	@echo "  make lint       린팅 검사"
	@echo "  make format     코드 포맷팅"
	@echo "  make install    의존성 설치"
	@echo ""

# 개발 서버 (Docker 기반 - migrate, seed 포함)
dev:
	docker compose up -d postgres mongo redis
	@echo "Waiting for DB to be ready..."
	@sleep 3
	docker compose up -d app
	@echo "Running migrations..."
	docker exec fast-light-chat-app alembic upgrade head
	@echo "Seeding data..."
	docker exec fast-light-chat-app python scripts/seed_data.py
	@echo "Starting app with logs..."
	docker compose logs -f app

# 프로덕션 모드
run:
	uv run uvicorn app.asgi:app --host 0.0.0.0 --port 8000

# DB만 실행
db:
	docker compose up -d postgres mongo redis

# DB 중지
db-stop:
	docker compose stop postgres mongo redis

# DB + 관리 UI
db-ui:
	docker compose --profile dev-tools up -d postgres mongo redis mongo-express redis-commander

# Docker 전체 실행
up:
	docker compose up -d

# Docker 전체 중지
down:
	docker compose down

# 마이그레이션 (Docker)
migrate:
	docker exec fast-light-chat-app alembic upgrade head

# 시드 데이터 (Docker)
seed:
	docker exec fast-light-chat-app python scripts/seed_data.py

# 테스트
test:
	uv run pytest

# 린팅
lint:
	uv run ruff check .

# 포맷팅
format:
	uv run ruff format .
	uv run ruff check --fix .

# 의존성 설치
install:
	uv sync

# 정리
clean:
	docker compose down -v
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
