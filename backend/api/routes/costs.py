"""
Cost Dashboard API — Phase 4
에이전트별 토큰 사용량 및 비용 시각화 데이터 제공.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from core.database import get_db
from models.cost import CostRecord
from services.cost_tracker import CostTracker, MODEL_PRICING
import uuid

router = APIRouter()


@router.get("/costs/agent/{agent_id}")
async def get_agent_costs(
    agent_id: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """에이전트 비용 요약 + 날짜별 분석"""
    tracker = CostTracker(db)
    summary = await tracker.get_agent_summary(agent_id, days)
    daily = await tracker.get_daily_breakdown(agent_id, days)

    return {
        "agent_id": agent_id,
        "period_days": days,
        "summary": {
            "total_usd": summary.total_usd,
            "total_tokens": summary.total_tokens,
            "prompt_tokens": summary.prompt_tokens,
            "completion_tokens": summary.completion_tokens,
            "runs": summary.runs,
            "avg_cost_per_run": round(summary.total_usd / max(summary.runs, 1), 4),
        },
        "daily_breakdown": daily,
    }


@router.get("/costs/overview")
async def get_cost_overview(db: AsyncSession = Depends(get_db)):
    """전체 플랫폼 비용 개요"""
    result = await db.execute(
        select(
            CostRecord.agent_config_id,
            func.sum(CostRecord.cost_usd).label("total_usd"),
            func.sum(CostRecord.total_tokens).label("total_tokens"),
            func.count(CostRecord.id).label("runs"),
        ).group_by(CostRecord.agent_config_id)
        .order_by(func.sum(CostRecord.cost_usd).desc())
        .limit(20)
    )

    rows = result.all()
    total_usd = sum(r.total_usd for r in rows)

    return {
        "total_usd": round(total_usd, 4),
        "top_agents": [
            {
                "agent_id": str(r.agent_config_id),
                "total_usd": round(r.total_usd, 4),
                "total_tokens": r.total_tokens,
                "runs": r.runs,
                "cost_share_pct": round(r.total_usd / max(total_usd, 0.0001) * 100, 1),
            }
            for r in rows
        ],
    }


@router.get("/costs/models")
async def get_model_pricing():
    """모델별 토큰 단가 정보"""
    return {
        "pricing": [
            {
                "model": model,
                "input_per_1m_tokens_usd": p["input"],
                "output_per_1m_tokens_usd": p["output"],
                "is_free": p["input"] == 0,
            }
            for model, p in MODEL_PRICING.items()
        ]
    }
