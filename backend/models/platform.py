from sqlalchemy import Column, String, Text, Boolean, DateTime, JSON, Enum
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
from core.database import Base
import uuid
import enum


class ScheduleStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    DELETED = "deleted"


class AgentSchedule(Base):
    """에이전트 반복 실행 스케줄"""
    __tablename__ = "agent_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_config_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    input_text = Column(Text, nullable=False)       # 반복 실행할 태스크 입력
    cron_expression = Column(String(100))           # "0 9 * * 1-5" (평일 오전 9시)
    webhook_url = Column(String(500))               # 결과 전달 URL
    status = Column(Enum(ScheduleStatus), default=ScheduleStatus.ACTIVE)
    last_run_at = Column(DateTime(timezone=True))
    next_run_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class MarketplaceTemplate(Base):
    """마켓플레이스 공개 에이전트 템플릿"""
    __tablename__ = "marketplace_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(100), index=True)      # "research", "writing", "analysis"
    tags = Column(JSON, default=list)               # ["AI", "news", "summary"]
    agent_config = Column(JSON, nullable=False)     # AgentConfig 스냅샷
    author = Column(String(200))
    use_count = Column(String(20), default="0")     # 사용 횟수
    rating = Column(JSON, default=dict)             # {"avg": 4.5, "count": 12}
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Skill(Base):
    """재사용 가능한 도구 묶음 (Skill)"""
    __tablename__ = "skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    tools = Column(JSON, default=list)              # ["web_search", "python_executor"]
    system_prompt_snippet = Column(Text)            # 이 스킬 사용 시 추가할 프롬프트
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
