"""
Langfuse Tracing — 에이전트 실행 전 과정 관측
모든 에이전트 실행, LLM 호출, 도구 사용을 자동으로 기록.
Phase 3 변경점:
  - AgentTracer에서 lf.trace() 제거 (Langfuse 3.x에서 제거된 메서드)
  - 콜백 핸들러가 trace 자동 수집하므로 중복 제거
"""
from functools import wraps
from typing import Callable, Any
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler   # ← 3.x 경로
from core.config import get_settings
import logging
import time

logger = logging.getLogger(__name__)
settings = get_settings()

_langfuse_client = None


def _init_langfuse():
    """앱 시작 시 1회 Langfuse 클라이언트 초기화"""
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client
    if not settings.LANGFUSE_PUBLIC_KEY:
        return None
    try:
        _langfuse_client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        logger.info(f"[Langfuse] 초기화 성공 / auth: {_langfuse_client.auth_check()}")
    except Exception as e:
        logger.warning(f"[Langfuse] 초기화 실패: {e}")
        _langfuse_client = None
    return _langfuse_client


# 앱 로드 시 즉시 초기화
_init_langfuse()


def get_langfuse_callback(trace_id: str = None):
    """LangGraph 콜백 핸들러 반환 (langfuse 3.x 방식)"""
    client = _init_langfuse()
    if client is None:
        return None
    try:
        handler = CallbackHandler()   # ← 인수 없이 생성
        logger.info(f"[Langfuse] 콜백 생성 결과: {handler}")
        return handler
    except Exception as e:
        logger.warning(f"[Langfuse] 콜백 생성 실패: {e}")
        return None


def flush_langfuse():
    """LLM 호출 후 데이터를 Langfuse로 즉시 전송"""
    client = _init_langfuse()
    if client:
        try:
            client.flush()
        except Exception as e:
            logger.warning(f"[Langfuse] flush 실패: {e}")


class AgentTracer:
    """
    에이전트 실행 단위 트레이서.
    context manager로 사용해 자동 시작/종료.
    Langfuse 3.x: trace()가 제거되어 콜백 핸들러에 위임.
    """

    def __init__(self, run_id: str, agent_name: str, input_text: str = ""):
        self.run_id = run_id
        self.agent_name = agent_name
        self.input_text = input_text
        self._start_time = None

    def __enter__(self):
        self._start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        flush_langfuse()

    def span(self, name: str, input_data: Any = None):
        return _NoopSpan()

    def update(self, output: Any = None, usage: dict = None, metadata: dict = None):
        pass  # 콜백 핸들러가 자동으로 trace 수집


class _NoopSpan:
    """Langfuse 미설정 시 아무것도 안 하는 더미 스팬"""
    def end(self, *args, **kwargs): pass
    def update(self, *args, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass


def trace_agent_run(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(*args, **kwargs):
        run_id = kwargs.get("run_id", "unknown")
        agent_name = kwargs.get("agent_name", func.__name__)
        input_text = kwargs.get("input_text", "")

        with AgentTracer(run_id, agent_name, input_text) as tracer:
            kwargs["tracer"] = tracer
            result = await func(*args, **kwargs)
            tracer.update(output=result)
            return result

    return wrapper