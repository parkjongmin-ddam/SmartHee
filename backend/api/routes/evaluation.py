"""
Evaluation API Routes — Phase 2
에이전트 평가 및 A/B 테스트 엔드포인트.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import get_db
from agents.evaluator.evaluator import AgentEvaluator, ABTestRunner
from models.agent import AgentConfig, AgentRun
from models.evaluation import EvaluationResult, ABTestResult
import uuid

router = APIRouter()


class EvalRequest(BaseModel):
    run_id: str


class ABTestRequest(BaseModel):
    task: str
    agent_ids: list[str]  # 비교할 에이전트 ID 목록 (최대 5개)
    n_runs: int = 3


@router.post("/eval/run/{run_id}")
async def evaluate_run(run_id: str, db: AsyncSession = Depends(get_db)):
    """특정 실행 결과를 평가하고 점수 반환"""
    run = await db.get(AgentRun, uuid.UUID(run_id))
    if not run:
        raise HTTPException(status_code=404, detail="실행 기록 없음")
    if not run.output:
        raise HTTPException(status_code=400, detail="아직 완료되지 않은 실행")

    evaluator = AgentEvaluator()
    latency_ms = 0
    if run.started_at and run.finished_at:
        latency_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)

    score = await evaluator.evaluate(
        task=run.input,
        output=run.output,
        token_used=run.token_used or {},
        latency_ms=latency_ms,
    )

    # DB 저장
    result = EvaluationResult(
        run_id=run.id,
        agent_config_id=run.agent_config_id,
        task_success=score.task_success,
        token_efficiency=score.token_efficiency,
        latency_ms=score.latency_ms,
        tool_call_accuracy=score.tool_call_accuracy,
        overall_score=score.overall_score,
        reasoning=score.reasoning,
        raw_metrics=score.raw_metrics,
    )
    db.add(result)

    return {
        "run_id": run_id,
        "overall_score": score.overall_score,
        "task_success": score.task_success,
        "token_efficiency": score.token_efficiency,
        "tool_call_accuracy": score.tool_call_accuracy,
        "latency_ms": score.latency_ms,
        "reasoning": score.reasoning,
    }


@router.post("/eval/abtest")
async def run_ab_test(req: ABTestRequest, db: AsyncSession = Depends(get_db)):
    """여러 에이전트 구성을 동일 태스크로 비교"""
    if len(req.agent_ids) > 5:
        raise HTTPException(status_code=400, detail="최대 5개 에이전트까지 비교 가능")

    configs = []
    for aid in req.agent_ids:
        agent = await db.get(AgentConfig, uuid.UUID(aid))
        if not agent:
            raise HTTPException(status_code=404, detail=f"에이전트 없음: {aid}")
        configs.append({
            "id": str(agent.id),
            "name": agent.name,
            "model": agent.model,
            "system_prompt": agent.system_prompt,
            "tools": agent.tools,
            "is_multi_agent": bool(agent.worker_configs),
            "worker_configs": agent.worker_configs,
        })

    runner = ABTestRunner()
    report = await runner.run(task=req.task, configs=configs, n_runs=req.n_runs)

    # DB 저장
    ab_result = ABTestResult(
        task=req.task,
        winner_config_name=report["winner"],
        results=report["results"],
        recommendation=report["recommendation"],
    )
    db.add(ab_result)

    return report


@router.get("/eval/agent/{agent_id}/stats")
async def get_agent_stats(agent_id: str, db: AsyncSession = Depends(get_db)):
    """에이전트 누적 성능 통계"""
    from sqlalchemy import select, func

    results = await db.execute(
        select(
            func.avg(EvaluationResult.overall_score).label("avg_score"),
            func.avg(EvaluationResult.task_success).label("avg_task_success"),
            func.avg(EvaluationResult.latency_ms).label("avg_latency_ms"),
            func.count(EvaluationResult.id).label("total_evals"),
        ).where(EvaluationResult.agent_config_id == uuid.UUID(agent_id))
    )
    row = results.first()

    return {
        "agent_id": agent_id,
        "avg_overall_score": round(row.avg_score or 0, 3),
        "avg_task_success": round(row.avg_task_success or 0, 3),
        "avg_latency_ms": int(row.avg_latency_ms or 0),
        "total_evaluations": row.total_evals,
    }
