from sqlalchemy import Column, Float, Integer, JSON, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
from core.database import Base
import uuid


class EvaluationResult(Base):
    """에이전트 실행 평가 결과 저장"""
    __tablename__ = "evaluation_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    agent_config_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # 평가 지표
    task_success = Column(Float)          # 0.0 ~ 1.0
    token_efficiency = Column(Float)
    latency_ms = Column(Integer)
    tool_call_accuracy = Column(Float)
    overall_score = Column(Float, index=True)

    # 상세 정보
    reasoning = Column(Text)
    raw_metrics = Column(JSON, default=dict)

    evaluated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ABTestResult(Base):
    """A/B 테스트 결과 저장"""
    __tablename__ = "ab_test_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task = Column(Text, nullable=False)
    winner_config_name = Column(String(200))
    results = Column(JSON)                # 전체 비교 결과
    recommendation = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
