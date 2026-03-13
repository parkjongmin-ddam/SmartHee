"""
Celery Tasks — 스케줄링 + 비동기 에이전트 실행
Phase 3 핵심: 반복 태스크 자동화, 웹훅 콜백.

사용 패턴:
    # 즉시 비동기 실행
    task = run_agent_async.delay(agent_id, input_text)

    # 스케줄 등록 (Celery Beat)
    from celery.schedules import crontab
    app.conf.beat_schedule = {"daily-news": {"task": "run_agent", "schedule": crontab(hour=9)}}
"""
from celery import Celery
from celery.schedules import crontab
from core.config import get_settings
import asyncio
import httpx
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Celery 앱 초기화
celery_app = Celery(
    "agentforge",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Seoul",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,            # 실패 시 재시도 보장
    worker_prefetch_multiplier=1,   # 공정한 작업 분배
)


def _run_async(coro):
    """Celery 동기 컨텍스트에서 비동기 코루틴 실행"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="run_agent",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run_agent_task(self, agent_id: str, input_text: str, webhook_url: str = None):
    """
    에이전트 비동기 실행 태스크.

    Args:
        agent_id: 실행할 에이전트 UUID
        input_text: 태스크 입력
        webhook_url: 완료 후 결과를 보낼 URL (선택)
    """
    try:
        result = _run_async(_execute_agent(agent_id, input_text))

        # 웹훅 콜백
        if webhook_url:
            _run_async(_send_webhook(webhook_url, {
                "task_id": self.request.id,
                "agent_id": agent_id,
                "status": "success",
                "output": result.get("output"),
                "run_id": result.get("run_id"),
            }))

        return result

    except Exception as exc:
        logger.error(f"[Celery] 에이전트 실행 실패: {exc}")
        if webhook_url:
            _run_async(_send_webhook(webhook_url, {
                "task_id": self.request.id,
                "agent_id": agent_id,
                "status": "failed",
                "error": str(exc),
            }))
        raise self.retry(exc=exc)


async def _execute_agent(agent_id: str, input_text: str) -> dict:
    """DB에서 에이전트 로드 후 실행"""
    from core.database import AsyncSessionLocal
    from models.agent import AgentConfig
    from agents.orchestrator.graph import AgentOrchestrator
    import uuid

    async with AsyncSessionLocal() as db:
        agent = await db.get(AgentConfig, uuid.UUID(agent_id))
        if not agent:
            raise ValueError(f"에이전트 없음: {agent_id}")

        config = {
            "id": str(agent.id),
            "name": agent.name,
            "model": agent.model,
            "system_prompt": agent.system_prompt,
            "tools": agent.tools,
            "is_multi_agent": bool(agent.worker_configs),
            "worker_configs": agent.worker_configs,
        }

    orchestrator = AgentOrchestrator(config)
    return await orchestrator.run(input_text)


async def _send_webhook(url: str, payload: dict):
    """웹훅 POST 전송 (타임아웃 10초)"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"[Webhook] 전송 성공: {url} → {response.status_code}")
    except Exception as e:
        logger.error(f"[Webhook] 전송 실패: {url} → {e}")
