from sqlalchemy import Column, Float, Integer, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
from core.database import Base
import uuid


class CostRecord(Base):
    """에이전트 실행 비용 기록"""
    __tablename__ = "cost_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    agent_config_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    model = Column(String(100), nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
