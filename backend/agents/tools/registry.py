"""
Tool Registry — MCP 호환 도구 관리
모든 도구는 이 레지스트리에 등록 후 에이전트에서 사용.
"""
from langchain_core.tools import BaseTool, tool
from langchain_community.tools.tavily_search import TavilySearchResults
from typing import Callable
import subprocess
import sys
import textwrap
from core.config import get_settings

settings = get_settings()

# ── 내장 도구 정의 ────────────────────────────────────────────────────

@tool
def web_search(query: str) -> str:
    """인터넷에서 최신 정보를 검색합니다. 뉴스, 최신 정보, 사실 확인에 사용하세요."""
    tavily = TavilySearchResults(
        api_key=settings.TAVILY_API_KEY,
        max_results=5,
    )
    results = tavily.invoke(query)
    return "\n\n".join([f"[{r['url']}]\n{r['content']}" for r in results])


@tool
def python_executor(code: str) -> str:
    """
    Python 코드를 안전한 샌드박스에서 실행합니다.
    데이터 분석, 계산, 파일 처리 등에 사용하세요.

    주의: 네트워크 접근 및 파일 시스템 쓰기는 제한됩니다.
    """
    # TODO: Production에서는 Docker 샌드박스 또는 e2b.dev 사용 권장
    safe_code = textwrap.dedent(f"""
import sys
import io
from contextlib import redirect_stdout

output = io.StringIO()
with redirect_stdout(output):
    exec(compile('''{code}''', '<string>', 'exec'))
print(output.getvalue())
    """)
    try:
        result = subprocess.run(
            [sys.executable, "-c", safe_code],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout or result.stderr
    except subprocess.TimeoutExpired:
        return "Error: 실행 시간 초과 (10초)"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def get_current_time() -> str:
    """현재 날짜와 시간을 반환합니다."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# ── Tool Registry ─────────────────────────────────────────────────────

class ToolRegistry:
    """
    모든 사용 가능한 도구를 관리하는 레지스트리.
    에이전트 설정의 tool 이름 목록으로 실제 도구 객체를 반환.
    """

    _tools: dict[str, BaseTool] = {
        "web_search": web_search,
        "python_executor": python_executor,
        "get_current_time": get_current_time,
    }

    # Builder Agent가 도구 선택 시 보여줄 메타데이터
    TOOL_METADATA = [
        {
            "name": "web_search",
            "description": "인터넷 검색 (최신 정보, 뉴스, 사실 확인)",
            "category": "search",
        },
        {
            "name": "python_executor",
            "description": "Python 코드 실행 (데이터 분석, 계산)",
            "category": "code",
        },
        {
            "name": "get_current_time",
            "description": "현재 시간 조회",
            "category": "utility",
        },
        # Phase 2에서 추가될 MCP 도구들
        # {"name": "slack_send_message", "category": "communication"},
        # {"name": "notion_create_page", "category": "productivity"},
    ]

    @classmethod
    def get(cls, tool_names: list[str]) -> list[BaseTool]:
        """도구 이름 목록으로 실제 도구 객체 반환"""
        tools = []
        for name in tool_names:
            if name not in cls._tools:
                raise ValueError(f"등록되지 않은 도구: {name}")
            tools.append(cls._tools[name])
        return tools

    @classmethod
    def register(cls, name: str, tool_fn: Callable):
        """커스텀 도구 동적 등록"""
        cls._tools[name] = tool_fn

    @classmethod
    def list_all(cls) -> list[dict]:
        return cls.TOOL_METADATA
