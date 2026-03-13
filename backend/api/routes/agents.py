"""
API Routes — Builder & Agent 실행
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import get_db
from agents.builder.builder_agent import BuilderAgent
from agents.orchestrator.graph import AgentOrchestrator
from models.agent import AgentConfig, AgentRun, AgentRunStatus
from services.cost_tracker import CostTracker
import uuid
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request / Response 스키마 ─────────────────────────────────────────

class BuildRequest(BaseModel):
    request: str                      # "웹 검색 후 요약하는 에이전트 만들어줘"
    model: str = "openai/gpt-4o"      # Builder Agent가 사용할 모델

class RefineRequest(BaseModel):
    agent_id: str
    request: str

class RunRequest(BaseModel):
    agent_id: str
    input: str                        # 실제 실행할 태스크 입력


# ── Builder 엔드포인트 ─────────────────────────────────────────────────

@router.post("/builder/create")
async def create_agent(req: BuildRequest, db: AsyncSession = Depends(get_db)):
    """
    자연어로 에이전트 생성.
    BuilderAgent → AgentConfig → DB 저장
    """
    builder = BuilderAgent(model=req.model)

    try:
        config_dict = await builder.create(req.request)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    agent = AgentConfig(
        id=uuid.uuid4(),
        name=config_dict["name"],
        description=config_dict.get("description", ""),
        system_prompt=config_dict["system_prompt"],
        model=config_dict["model"],
        tools=config_dict["tools"],
        worker_configs=config_dict.get("worker_configs", []),
        meta={"builder_reasoning": config_dict.get("reasoning", "")},
    )
    db.add(agent)
    await db.flush()

    return {
        "agent_id": str(agent.id),
        "config": config_dict,
        "message": f"에이전트 '{agent.name}'이 생성되었습니다.",
    }


@router.post("/builder/refine")
async def refine_agent(req: RefineRequest, db: AsyncSession = Depends(get_db)):
    """기존 에이전트 수정"""
    agent = await db.get(AgentConfig, uuid.UUID(req.agent_id))
    if not agent:
        raise HTTPException(status_code=404, detail="에이전트를 찾을 수 없습니다.")

    current_config = {
        "id": str(agent.id),
        "name": agent.name,
        "system_prompt": agent.system_prompt,
        "model": agent.model,
        "tools": agent.tools,
        "worker_configs": agent.worker_configs,
    }

    builder = BuilderAgent()
    refined = await builder.refine(current_config, req.request)

    agent.name = refined.get("name", agent.name)
    agent.system_prompt = refined.get("system_prompt", agent.system_prompt)
    agent.tools = refined.get("tools", agent.tools)
    agent.worker_configs = refined.get("worker_configs", agent.worker_configs)

    return {"agent_id": req.agent_id, "config": refined}


# ── 에이전트 실행 엔드포인트 ──────────────────────────────────────────

@router.post("/agents/run")
async def run_agent(req: RunRequest, db: AsyncSession = Depends(get_db)):
    """에이전트 동기 실행 (짧은 태스크용)"""
    agent = await db.get(AgentConfig, uuid.UUID(req.agent_id))
    if not agent:
        raise HTTPException(status_code=404, detail="에이전트를 찾을 수 없습니다.")

    run = AgentRun(
        id=uuid.uuid4(),
        agent_config_id=agent.id,
        input=req.input,
        status=AgentRunStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.flush()

    config_dict = {
        "id": str(agent.id),
        "name": agent.name,
        "system_prompt": agent.system_prompt,
        "model": agent.model,
        "tools": agent.tools,
        "is_multi_agent": bool(agent.worker_configs),
        "worker_configs": agent.worker_configs,
    }

    try:
        orchestrator = AgentOrchestrator(config_dict)
        result = await orchestrator.run(req.input)

        run.output = result["output"]
        run.status = AgentRunStatus.SUCCESS
        run.finished_at = datetime.now(timezone.utc)

        # ── Cost Tracker 연동 ──────────────────────────────────────────
        # result에 토큰 사용량이 포함된 경우 비용 기록
        usage = result.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        if prompt_tokens or completion_tokens:
            tracker = CostTracker(db)
            cost_usd = await tracker.record(
                run_id=str(run.id),
                agent_config_id=str(agent.id),
                model=agent.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            logger.info(f"[CostTracker] {agent.model} | {prompt_tokens}+{completion_tokens} tokens | ${cost_usd:.6f}")
        else:
            # usage 정보가 없을 때 추정값으로 기록 (글자 수 기반 rough estimate)
            estimated_prompt = len(req.input) // 4
            estimated_completion = len(result["output"]) // 4
            tracker = CostTracker(db)
            cost_usd = await tracker.record(
                run_id=str(run.id),
                agent_config_id=str(agent.id),
                model=agent.model,
                prompt_tokens=estimated_prompt,
                completion_tokens=estimated_completion,
            )
            logger.info(f"[CostTracker] {agent.model} | 추정 {estimated_prompt}+{estimated_completion} tokens | ${cost_usd:.6f}")
        # ──────────────────────────────────────────────────────────────

        return {"run_id": str(run.id), "output": result["output"], "status": "success"}

    except Exception as e:
        run.status = AgentRunStatus.FAILED
        run.error = str(e)
        run.finished_at = datetime.now(timezone.utc)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/run/{run_id}")
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    """실행 결과 조회"""
    run = await db.get(AgentRun, uuid.UUID(run_id))
    if not run:
        raise HTTPException(status_code=404, detail="실행 기록을 찾을 수 없습니다.")

    return {
        "run_id": run_id,
        "status": run.status,
        "input": run.input,
        "output": run.output,
        "error": run.error,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }


@router.get("/tools")
async def list_tools():
    """사용 가능한 도구 목록 반환"""
    from agents.tools.registry import ToolRegistry
    return {"tools": ToolRegistry.list_all()}


@router.get("/models")
async def list_models():
    """사용 가능한 LLM 목록 반환"""
    from core.llm_router import AVAILABLE_MODELS
    return {"models": AVAILABLE_MODELS}