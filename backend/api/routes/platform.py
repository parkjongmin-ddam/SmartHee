"""
Platform API Routes — Phase 3
스케줄링 / 웹훅 / 마켓플레이스 / 스킬 관리 엔드포인트.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, HttpUrl
from typing import Optional
from core.database import get_db
from models.agent import AgentConfig
from models.platform import AgentSchedule, MarketplaceTemplate, Skill, ScheduleStatus
from services.tasks import run_agent_task
import uuid

router = APIRouter()


# ── 스케줄링 ──────────────────────────────────────────────────────────

class ScheduleCreate(BaseModel):
    agent_id: str
    name: str
    input_text: str
    cron_expression: str             # "0 9 * * 1-5"
    webhook_url: Optional[str] = None


@router.post("/schedules")
async def create_schedule(req: ScheduleCreate, db: AsyncSession = Depends(get_db)):
    """에이전트 반복 실행 스케줄 등록"""
    agent = await db.get(AgentConfig, uuid.UUID(req.agent_id))
    if not agent:
        raise HTTPException(status_code=404, detail="에이전트 없음")

    schedule = AgentSchedule(
        agent_config_id=uuid.UUID(req.agent_id),
        name=req.name,
        input_text=req.input_text,
        cron_expression=req.cron_expression,
        webhook_url=req.webhook_url,
    )
    db.add(schedule)
    await db.flush()

    # Celery Beat에 동적 등록
    # 실제 운영: celery_app.conf.beat_schedule 동적 갱신 or DB 폴링 방식
    return {
        "schedule_id": str(schedule.id),
        "message": f"스케줄 등록 완료: {req.cron_expression}",
        "note": "Celery Beat 재시작 시 적용됩니다.",
    }


@router.post("/schedules/{schedule_id}/run-now")
async def run_schedule_now(schedule_id: str, db: AsyncSession = Depends(get_db)):
    """스케줄 즉시 실행 (테스트용)"""
    schedule = await db.get(AgentSchedule, uuid.UUID(schedule_id))
    if not schedule:
        raise HTTPException(status_code=404, detail="스케줄 없음")

    task = run_agent_task.delay(
        agent_id=str(schedule.agent_config_id),
        input_text=schedule.input_text,
        webhook_url=schedule.webhook_url,
    )

    return {"task_id": task.id, "status": "queued"}


@router.get("/schedules")
async def list_schedules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentSchedule).where(AgentSchedule.status != ScheduleStatus.DELETED)
    )
    schedules = result.scalars().all()
    return {"schedules": [
        {
            "id": str(s.id), "name": s.name,
            "cron": s.cron_expression, "status": s.status,
            "last_run_at": s.last_run_at,
        } for s in schedules
    ]}


# ── 웹훅 ────────────────────────────────────────────────────────────

class WebhookRunRequest(BaseModel):
    agent_id: str
    input_text: str
    callback_url: str    # 결과를 받을 URL


@router.post("/webhook/run")
async def run_with_webhook(req: WebhookRunRequest):
    """
    웹훅 기반 비동기 실행.
    즉시 task_id를 반환하고, 완료 시 callback_url로 결과 POST.
    """
    task = run_agent_task.delay(
        agent_id=req.agent_id,
        input_text=req.input_text,
        webhook_url=req.callback_url,
    )

    return {
        "task_id": task.id,
        "status": "queued",
        "callback_url": req.callback_url,
        "message": "완료 시 callback_url로 결과가 전송됩니다.",
    }


@router.get("/webhook/status/{task_id}")
async def get_task_status(task_id: str):
    """Celery 태스크 상태 조회"""
    from services.tasks import celery_app
    result = celery_app.AsyncResult(task_id)

    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }


# ── 마켓플레이스 ─────────────────────────────────────────────────────

class TemplateCreate(BaseModel):
    agent_id: str
    category: str
    tags: list[str] = []


@router.post("/marketplace/publish")
async def publish_to_marketplace(req: TemplateCreate, db: AsyncSession = Depends(get_db)):
    """에이전트를 마켓플레이스에 공개"""
    agent = await db.get(AgentConfig, uuid.UUID(req.agent_id))
    if not agent:
        raise HTTPException(status_code=404, detail="에이전트 없음")

    template = MarketplaceTemplate(
        name=agent.name,
        description=agent.description,
        category=req.category,
        tags=req.tags,
        agent_config={
            "name": agent.name,
            "system_prompt": agent.system_prompt,
            "model": agent.model,
            "tools": agent.tools,
            "worker_configs": agent.worker_configs,
        },
    )
    db.add(template)
    await db.flush()

    return {"template_id": str(template.id), "message": "마켓플레이스에 공개되었습니다."}


@router.get("/marketplace")
async def list_marketplace(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """마켓플레이스 템플릿 목록"""
    query = select(MarketplaceTemplate)
    if category:
        query = query.where(MarketplaceTemplate.category == category)
    query = query.order_by(MarketplaceTemplate.created_at.desc()).limit(50)

    result = await db.execute(query)
    templates = result.scalars().all()

    return {"templates": [
        {
            "id": str(t.id), "name": t.name,
            "description": t.description, "category": t.category,
            "tags": t.tags, "rating": t.rating,
        } for t in templates
    ]}


@router.post("/marketplace/{template_id}/use")
async def use_template(template_id: str, db: AsyncSession = Depends(get_db)):
    """마켓플레이스 템플릿으로 에이전트 생성"""
    template = await db.get(MarketplaceTemplate, uuid.UUID(template_id))
    if not template:
        raise HTTPException(status_code=404, detail="템플릿 없음")

    cfg = template.agent_config
    agent = AgentConfig(
        name=f"{cfg['name']} (from marketplace)",
        system_prompt=cfg["system_prompt"],
        model=cfg["model"],
        tools=cfg["tools"],
        worker_configs=cfg.get("worker_configs", []),
        meta={"source_template_id": template_id},
    )
    db.add(agent)
    await db.flush()

    return {"agent_id": str(agent.id), "message": "템플릿으로 에이전트가 생성되었습니다."}


# ── 스킬 ────────────────────────────────────────────────────────────

class SkillCreate(BaseModel):
    name: str
    description: str
    tools: list[str]
    system_prompt_snippet: str = ""
    is_public: bool = False


@router.post("/skills")
async def create_skill(req: SkillCreate, db: AsyncSession = Depends(get_db)):
    """재사용 가능한 스킬 저장"""
    skill = Skill(**req.model_dump())
    db.add(skill)
    await db.flush()
    return {"skill_id": str(skill.id), "message": f"스킬 '{req.name}' 저장 완료"}


@router.get("/skills")
async def list_skills(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Skill).order_by(Skill.created_at.desc()))
    skills = result.scalars().all()
    return {"skills": [
        {"id": str(s.id), "name": s.name, "tools": s.tools, "is_public": s.is_public}
        for s in skills
    ]}
