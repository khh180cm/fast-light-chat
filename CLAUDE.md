# CLAUDE.md

이 파일은 Claude Code가 이 프로젝트를 이해하고 작업할 때 참고하는 가이드입니다.

## 프로젝트 개요

**Fast Light Chat** - 채널톡 스타일의 경량 고성능 실시간 채팅 상담 플랫폼

### 핵심 목표
- **성능**: 모든 API/WebSocket 응답 150ms 이하
- **동시 접속**: 10,000명 이상 지원
- **경량화**: 최소한의 의존성, 효율적인 리소스 사용

## 기술 스택

| 영역 | 기술 |
|------|------|
| Backend | FastAPI (Python 3.13) |
| Realtime | python-socketio |
| DB (정형) | PostgreSQL - 조직, 상담원, 환경 |
| DB (비정형) | MongoDB - 채팅, 메시지, 유저 |
| Cache | Redis - 세션, 캐싱, 상태 |
| Package Manager | uv |

## 아키텍처

### 디렉토리 구조
```
app/
├── core/           # 설정, 보안, 예외 (공통)
├── db/             # DB 연결 (PostgreSQL, MongoDB, Redis)
├── dependencies/   # FastAPI 의존성 주입
├── middlewares/    # HTTP 미들웨어
├── domains/        # 도메인별 모듈 (DDD)
│   ├── auth/       # 인증 (JWT 발급/검증)
│   ├── organization/  # 조직 (테넌트)
│   ├── environment/   # 환경 & API Key
│   ├── agent/      # 상담원
│   ├── user/       # 엔드유저
│   └── chat/       # 채팅 & 메시지
└── sockets/        # Socket.IO 네임스페이스
```

### 도메인 모듈 구조 (각 domains/* 폴더)
```
domain/
├── models.py       # 엔티티 (SQLAlchemy/Pydantic)
├── schemas.py      # 요청/응답 DTO
├── repository.py   # 데이터 접근 계층
├── service.py      # 비즈니스 로직
└── router.py       # API 엔드포인트
```

## 인증 방식

| 대상 | 방식 | 헤더 |
|------|------|------|
| SDK (고객) | Plugin Key | `X-Plugin-Key` |
| 백엔드 연동 | API Key + Secret | `X-API-Key` + `X-API-Secret` |
| 대시보드 | JWT Bearer | `Authorization: Bearer {token}` |

## 주요 명령어

```bash
# 의존성 설치
uv sync

# 서버 실행
uv run uvicorn app.asgi:app --reload

# 마이그레이션
uv run alembic upgrade head

# 시드 데이터
uv run python scripts/seed_data.py

# 테스트
uv run pytest

# 린팅
uv run ruff check .
uv run ruff format .
```

## 코딩 컨벤션

### Python
- Python 3.13+ 타입 힌트 사용 (`list[str]` not `List[str]`)
- Google 스타일 docstring
- Ruff로 린팅/포맷팅
- 비동기 우선 (async/await)

### FastAPI
- Pydantic v2 사용
- 의존성 주입으로 DB 세션, 인증 처리
- 응답은 항상 Pydantic 스키마로 정의

### 데이터베이스
- PostgreSQL: SQLAlchemy async (정형 데이터)
- MongoDB: Motor async (채팅 데이터)
- Redis: redis-py async (캐싱)

## 성능 최적화 원칙

1. **DB 쿼리 최소화**: 캐싱 우선, N+1 방지
2. **연결 풀링**: 모든 DB에 연결 풀 설정됨
3. **인덱스**: MongoDB 컬렉션에 필수 인덱스 생성
4. **비동기**: 모든 I/O 작업은 async

## 작업 시 주의사항

1. **보안**
   - `.env` 파일은 절대 커밋하지 않음
   - JWT 시크릿은 프로덕션에서 반드시 변경
   - 사용자 입력은 항상 검증

2. **테스트**
   - 새 기능 추가 시 테스트 코드 작성
   - 테스트 피라미드: Unit(70%) > Integration(20%) > E2E(10%)

3. **커밋**
   - 의미 있는 단위로 커밋
   - 커밋 메시지는 변경 내용을 명확히 설명

## 현재 TODO

- [ ] 테스트 코드 작성 (unit, integration, e2e)
- [ ] 부하 테스트 (Locust/k6)
- [ ] CI/CD 파이프라인 (GitHub Actions)
- [ ] 모니터링 설정 (Prometheus + Grafana)
- [ ] 프로덕션 배포 가이드

## 참고 문서

- [FastAPI 공식 문서](https://fastapi.tiangolo.com)
- [python-socketio 문서](https://python-socketio.readthedocs.io)
- [Pydantic v2 문서](https://docs.pydantic.dev)
- [SQLAlchemy 2.0 문서](https://docs.sqlalchemy.org)
