"""
Cost Tracker — 에이전트별 토큰 사용량 및 비용 집계
Phase 4: 운영 비용 가시성 확보.

모델별 토큰 단가 기반으로 USD 비용을 자동 계산.
대시보드에서 에이전트별, 날짜별 비용 조회 가능.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models.cost import CostRecord
import uuid

# ── 모델별 토큰 단가 (USD per 1M tokens) ──────────────────────────────
MODEL_PRICING = {
    "openai/gpt-4o":           {"input": 5.00,   "output": 15.00},
    "openai/gpt-4o-mini":      {"input": 0.15,   "output": 0.60},
    "anthropic/claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "anthropic/claude-3-haiku-20240307":    {"input": 0.25, "output": 1.25},
    "ollama/llama3":            {"input": 0.00,  "output": 0.00},  # 로컬 무료
}


@dataclass
class CostSummary:
    total_usd: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    runs: int


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """토큰 수로 USD 비용 계산"""
    pricing = MODEL_PRICING.get(model, {"input": 5.00, "output": 15.00})
    cost = (
        (prompt_tokens / 1_000_000) * pricing["input"]
        + (completion_tokens / 1_000_000) * pricing["output"]
    )
    return round(cost, 6)


class CostTracker:
    """
    에이전트 실행마다 비용 기록 + 집계 조회.

    사용:
        tracker = CostTracker(db)
        await tracker.record(
            run_id="uuid",
            agent_config_id="uuid",
            model="openai/gpt-4o",
            prompt_tokens=500,
            completion_tokens=200,
        )
        summary = await tracker.get_agent_summary(agent_id)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record(
        self,
        run_id: str,
        agent_config_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """실행 비용 기록. 계산된 USD 비용 반환."""
        cost_usd = calculate_cost(model, prompt_tokens, completion_tokens)

        record = CostRecord(
            run_id=uuid.UUID(run_id),
            agent_config_id=uuid.UUID(agent_config_id),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost_usd,
        )
        self.db.add(record)
        return cost_usd

    async def get_agent_summary(
        self,
        agent_config_id: str,
        days: int = 30,
    ) -> CostSummary:
        """에이전트의 최근 N일 비용 요약"""
        since = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(
                func.sum(CostRecord.cost_usd).label("total_usd"),
                func.sum(CostRecord.prompt_tokens).label("prompt_tokens"),
                func.sum(CostRecord.completion_tokens).label("completion_tokens"),
                func.sum(CostRecord.total_tokens).label("total_tokens"),
                func.count(CostRecord.id).label("runs"),
            ).where(
                CostRecord.agent_config_id == uuid.UUID(agent_config_id),
                CostRecord.created_at >= since,
            )
        )
        row = result.first()

        return CostSummary(
            total_usd=round(row.total_usd or 0, 4),
            prompt_tokens=row.prompt_tokens or 0,
            completion_tokens=row.completion_tokens or 0,
            total_tokens=row.total_tokens or 0,
            runs=row.runs or 0,
        )

    async def get_daily_breakdown(self, agent_config_id: str, days: int = 14) -> list[dict]:
        """날짜별 비용 분석 (차트용)"""
        since = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(
                func.date(CostRecord.created_at).label("date"),
                func.sum(CostRecord.cost_usd).label("cost_usd"),
                func.sum(CostRecord.total_tokens).label("tokens"),
                func.count(CostRecord.id).label("runs"),
            ).where(
                CostRecord.agent_config_id == uuid.UUID(agent_config_id),
                CostRecord.created_at >= since,
            ).group_by(func.date(CostRecord.created_at))
            .order_by(func.date(CostRecord.created_at))
        )

        return [
            {"date": str(row.date), "cost_usd": round(row.cost_usd, 4),
             "tokens": row.tokens, "runs": row.runs}
            for row in result.all()
        ]
