from sqlalchemy import Column, String, JSON, DateTime, Boolean, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
from core.database import Base
import uuid
import enum


class AgentStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class AgentRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class AgentConfig(Base):
    """
    Builder Agent가 생성한 에이전트 설정 저장.
    LangGraph 오케스트레이터가 이 설정을 읽어 실행.
    """
    __tablename__ = "agent_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    system_prompt = Column(Text, nullable=False)
    model = Column(String(100), default="openai/gpt-4o")
    tools = Column(JSON, default=list)          # ["web_search", "python_executor", ...]
    worker_configs = Column(JSON, default=list) # 멀티에이전트 워커 설정
    status = Column(Enum(AgentStatus), default=AgentStatus.DRAFT)
    is_public = Column(Boolean, default=False)  # 마켓플레이스 공개 여부
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    # 메타데이터 (빌더 대화 이력 등)
    meta = Column(JSON, default=dict)


class AgentRun(Base):
    """에이전트 실행 로그"""
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_config_id = Column(UUID(as_uuid=True), nullable=False)
    input = Column(Text, nullable=False)
    output = Column(Text)
    status = Column(Enum(AgentRunStatus), default=AgentRunStatus.PENDING)
    token_used = Column(JSON, default=dict)  # {"prompt": 100, "completion": 200}
    cost_usd = Column(JSON, default=dict)
    trace_id = Column(String(200))           # Langfuse trace ID
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    error = Column(Text)
