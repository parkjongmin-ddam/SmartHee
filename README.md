# SmartHee 🔨

> Conversation-driven Multi-Agent Orchestration Platform

자연어 대화만으로 AI 에이전트 팀을 구성하고 실행하는 플랫폼.

---

## 📁 프로젝트 구조

```
SmartHee/
├── architecture.mermaid          # 전체 시스템 아키텍처
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── main.py                   # FastAPI 진입점
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── core/
│   │   ├── config.py             # 환경변수 / 설정
│   │   ├── database.py           # SQLAlchemy async 세션
│   │   ├── tracing.py            # Langfuse 트레이싱
│   │   └── llm_router.py         # OpenAI / Claude / Ollama 추상화
│   ├── agents/
│   │   ├── builder/
│   │   │   ├── builder_agent.py  # ★ 자연어 → AgentConfig 생성
│   │   │   └── prompts.py        # Builder 프롬프트 템플릿
│   │   ├── orchestrator/
│   │   │   ├── state.py          # ★ LangGraph 공유 상태
│   │   │   ├── supervisor.py     # ★ 멀티에이전트 조율자
│   │   │   └── graph.py          # ★ 실행 그래프 빌더
│   │   ├── evaluator/
│   │   │   └── evaluator.py      # LLM Judge 평가
│   │   └── tools/
│   │       └── registry.py       # MCP 호환 도구 레지스트리
│   ├── api/
│   │   ├── routes/
│   │   │   ├── agents.py         # 에이전트 생성 / 실행 API
│   │   │   ├── evaluation.py     # 평가 API
│   │   │   ├── platform.py       # 스케줄링 / 웹훅 / 마켓플레이스
│   │   │   └── costs.py          # 비용 조회 API
│   │   └── websocket.py          # 실시간 스트리밍
│   ├── models/
│   │   ├── agent.py              # AgentConfig, AgentRun
│   │   ├── evaluation.py         # EvaluationResult
│   │   ├── platform.py           # AgentSchedule, MarketplaceTemplate
│   │   └── cost.py               # CostRecord
│   └── services/
│       ├── tasks.py              # Celery 비동기 태스크
│       └── cost_tracker.py       # 토큰 비용 계산 및 기록
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx               # 다크/라이트 테마 컨텍스트
        ├── api/client.ts         # FastAPI 연동
        ├── components/
        │   ├── Header.tsx        # 헤더 + 테마 토글
        │   ├── BuilderPanel.tsx  # 에이전트 생성
        │   ├── RunPanel.tsx      # 에이전트 실행
        │   └── ResultPanel.tsx   # 결과 표시
        └── pages/Dashboard.tsx   # 메인 대시보드
```

---

## 🚀 빠른 시작

```bash
# 1. 환경변수 설정
copy .env.example backend\.env
# backend\.env 에 API 키 입력

# 2. Docker로 PostgreSQL + Redis 실행
docker-compose up -d postgres redis

# 3. 백엔드 가상환경 생성 및 설치
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 4. FastAPI 서버 실행 (터미널 1)
uvicorn main:app --reload --port 8000

# 5. Celery Worker 실행 (터미널 2)
celery -A services.tasks worker --loglevel=info --pool=solo

# 6. 프론트엔드 실행 (터미널 3)
cd ..\frontend
npm install
npm run dev
```

**접속**
- 프론트엔드: `http://localhost:5173`
- API 문서 (Swagger): `http://localhost:8000/docs`

---

## 🔌 핵심 API

### 에이전트 생성 (Builder)

```
POST /api/v1/builder/create
{
  "request": "최신 AI 뉴스를 웹에서 검색해서 한국어로 요약하는 에이전트 만들어줘",
  "model": "openai/gpt-4o"
}
→ {"agent_id": "uuid", "config": {...}}
```

### 에이전트 실행

```
POST /api/v1/agents/run
{
  "agent_id": "uuid",
  "input": "오늘 AI 관련 뉴스 요약해줘"
}
→ {"run_id": "uuid", "output": "...", "status": "success"}
```

### 비동기 실행 + 웹훅

```
POST /api/v1/webhook/run
{
  "agent_id": "uuid",
  "input_text": "태스크 내용",
  "callback_url": "https://your-server.com/webhook"
}
→ {"task_id": "uuid", "status": "queued"}
```

### 비용 조회

```
GET /api/v1/costs/overview
GET /api/v1/costs/agent/{agent_id}?days=30
```

---

## 🗺️ 개발 로드맵

| Phase | 내용 | 상태 |
|-------|------|------|
| **Phase 1** | Builder Agent + LangGraph 오케스트레이터 + FastAPI 기반 구축 | ✅ 완료 |
| **Phase 2** | Langfuse 트레이싱 + LLM Judge 에이전트 평가 시스템 | ✅ 완료 |
| **Phase 3** | Celery 비동기 실행 + 웹훅 콜백 + 마켓플레이스 | ✅ 완료 |
| **Phase 4** | Cost Tracker + pytest 테스트 + React 프론트엔드 | ✅ 완료 |

---

## 🏗️ 아키텍처 결정 기록 (ADR)

### LangGraph 선택 이유

LangChain의 일반 체인은 선형 플로우만 지원하지만,
LangGraph는 **Supervisor ↔ Worker 루프**, **조건부 분기**, **공유 상태**를 네이티브로 지원.
멀티에이전트 오케스트레이션에 필수적인 사이클 그래프가 가능.

### Langfuse 선택 이유

LLM 애플리케이션은 같은 입력에도 매번 다른 결과가 나오기 때문에 일반 서버 모니터링만으로는 내부 동작을 파악할 수 없다. Langfuse는 LangGraph의 모든 노드 실행, LLM 호출, 도구 사용을 자동으로 Trace로 수집하고 모델별 비용까지 자동 계산한다.

### Celery + Redis 선택 이유

동기 방식은 에이전트 실행이 수십 초 이상 걸릴 경우 HTTP 타임아웃이 발생한다. Celery로 태스크를 비동기 처리하고 완료 시 웹훅으로 결과를 전달한다. Redis는 Phase 1부터 인프라에 포함되어 있어 브로커로 재활용했다.

### 비동기 SQLAlchemy 선택 이유

에이전트 실행 중 LLM API 대기 시간이 길어 동기 DB 드라이버는 스레드 블로킹 발생.
asyncpg + async SQLAlchemy로 I/O 바운드 작업 전체를 논블로킹으로 처리.

### React + Vite 선택 이유

Vite의 프록시 설정 한 줄로 FastAPI 백엔드와 CORS 없이 연동 가능하다. TypeScript로 API 응답 타입을 명시해 런타임 렌더링 오류를 컴파일 시점에 방지한다.
