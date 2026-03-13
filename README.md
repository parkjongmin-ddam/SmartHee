# AgentForge 🔨
> Conversation-driven Multi-Agent Orchestration Platform

자연어 대화만으로 AI 에이전트 팀을 구성하고 실행하는 플랫폼.

---

## 📁 프로젝트 구조

```
agentforge/
├── architecture.mermaid          # 전체 시스템 아키텍처
├── docker-compose.yml
├── .env.example
└── backend/
    ├── main.py                   # FastAPI 진입점
    ├── requirements.txt
    ├── Dockerfile
    ├── core/
    │   ├── config.py             # 환경변수 / 설정
    │   ├── database.py           # SQLAlchemy async 세션
    │   └── llm_router.py         # OpenAI / Claude / Ollama 추상화
    ├── agents/
    │   ├── builder/
    │   │   ├── builder_agent.py  # ★ 자연어 → AgentConfig 생성
    │   │   └── prompts.py        # Builder 프롬프트 템플릿
    │   ├── orchestrator/
    │   │   ├── state.py          # ★ LangGraph 공유 상태
    │   │   ├── supervisor.py     # ★ 멀티에이전트 조율자
    │   │   └── graph.py          # ★ 실행 그래프 빌더
    │   └── tools/
    │       └── registry.py       # MCP 호환 도구 레지스트리
    ├── api/
    │   ├── routes/
    │   │   └── agents.py         # REST API 라우트
    │   └── websocket.py          # 실시간 스트리밍
    └── models/
        └── agent.py              # DB 모델 (AgentConfig, AgentRun)
```

---

## 🚀 빠른 시작

```bash
# 1. 환경변수 설정
cp .env.example .env
# .env에 API 키 입력

# 2. Docker로 전체 스택 실행
docker-compose up -d

# 3. API 확인
curl http://localhost:8000/health
# → {"status": "ok", "app": "AgentForge"}

# 4. Swagger UI
open http://localhost:8000/docs
```

---

## 🔌 핵심 API

### 에이전트 생성 (Builder)
```bash
POST /api/v1/builder/create
{
  "request": "최신 AI 뉴스를 웹에서 검색해서 한국어로 요약하는 에이전트 만들어줘"
}
# → {"agent_id": "uuid", "config": {...}}
```

### 에이전트 실행
```bash
POST /api/v1/agents/run
{
  "agent_id": "uuid",
  "input": "오늘 AI 관련 뉴스 요약해줘"
}
```

### 실시간 스트리밍 (WebSocket)
```javascript
const ws = new WebSocket("ws://localhost:8000/ws/agents/{agent_id}/stream");
ws.send(JSON.stringify({ input: "태스크 내용" }));
ws.onmessage = (e) => console.log(JSON.parse(e.data));
// {"type": "token", "content": "안녕"} ...
// {"type": "final", "content": "최종 결과"}
```

---

## 🗺️ 개발 로드맵

| Phase | 내용 | 상태 |
|-------|------|------|
| **Phase 1** | Builder Agent + LangGraph 오케스트레이터 | ✅ 완료 |
| **Phase 2** | Langfuse 트레이싱 + 에이전트 평가 시스템 | 🔜 예정 |
| **Phase 3** | 스케줄링 + 마켓플레이스 + MCP 외부 도구 | 🔜 예정 |
| **Phase 4** | Ollama 온프레미스 + 비용 대시보드 | 🔜 예정 |

---

## 🏗️ 아키텍처 결정 기록 (ADR)

### LangGraph 선택 이유
LangChain의 일반 체인은 선형 플로우만 지원하지만,
LangGraph는 **Supervisor ↔ Worker 루프**, **조건부 분기**, **공유 상태**를 네이티브로 지원.
멀티에이전트 오케스트레이션에 필수적인 사이클 그래프가 가능.

### 비동기 SQLAlchemy 선택 이유
에이전트 실행 중 LLM API 대기 시간이 길어 동기 DB 드라이버는 스레드 블로킹 발생.
asyncpg + async SQLAlchemy로 I/O 바운드 작업 전체를 논블로킹으로 처리.

### Redis를 캐시와 Celery 브로커 공용 사용 이유
인프라 단순화. DB 번호(0: 캐시, 1: Celery broker, 2: result backend)로 논리적 분리.
