"""
Phase 4 — 핵심 테스트 스위트
Builder Agent + Orchestrator 단위 테스트.

실행: cd backend && pytest tests/ -v
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch


# ── Builder Agent 테스트 ──────────────────────────────────────────────

class TestBuilderAgent:
    """BuilderAgent.create() / refine() / _parse_config() 테스트"""

    def test_parse_config_valid_json(self):
        """정상 JSON 파싱"""
        from agents.builder.builder_agent import BuilderAgent
        builder = BuilderAgent.__new__(BuilderAgent)

        raw = json.dumps({
            "name": "Test Agent",
            "tools": ["web_search"],
            "system_prompt": "You are a helpful assistant.",
            "model": "openai/gpt-4o",
        })

        config = builder._parse_config(raw)
        assert config["name"] == "Test Agent"
        assert "web_search" in config["tools"]

    def test_parse_config_with_markdown_fence(self):
        """```json ... ``` 코드블록 포함 응답 처리"""
        from agents.builder.builder_agent import BuilderAgent
        builder = BuilderAgent.__new__(BuilderAgent)

        raw = """```json
{
  "name": "Fenced Agent",
  "tools": ["python_executor"],
  "system_prompt": "You are a coder."
}
```"""
        config = builder._parse_config(raw)
        assert config["name"] == "Fenced Agent"

    def test_parse_config_missing_required_field(self):
        """필수 필드 누락 시 ValueError"""
        from agents.builder.builder_agent import BuilderAgent
        builder = BuilderAgent.__new__(BuilderAgent)

        raw = json.dumps({"name": "Incomplete"})  # tools, system_prompt 누락

        with pytest.raises(ValueError, match="필수 필드 누락"):
            builder._parse_config(raw)

    def test_parse_config_invalid_json(self):
        """잘못된 JSON 시 ValueError"""
        from agents.builder.builder_agent import BuilderAgent
        builder = BuilderAgent.__new__(BuilderAgent)

        with pytest.raises(ValueError, match="파싱 오류"):
            builder._parse_config("not a json {{{{")

    @pytest.mark.asyncio
    async def test_create_calls_llm(self):
        """create()가 LLM을 호출하고 config를 반환하는지"""
        from agents.builder.builder_agent import BuilderAgent

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "name": "Web Agent",
            "tools": ["web_search"],
            "system_prompt": "Search the web.",
            "model": "openai/gpt-4o",
        })

        with patch("agents.builder.builder_agent.get_llm") as mock_llm_factory:
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_response
            mock_llm_factory.return_value = mock_llm

            builder = BuilderAgent()
            config = await builder.create("웹 검색 에이전트 만들어줘")

        assert config["name"] == "Web Agent"
        assert mock_llm.ainvoke.called


# ── LLM Router 테스트 ─────────────────────────────────────────────────

class TestLLMRouter:

    def test_get_llm_openai(self):
        """openai/ prefix로 ChatOpenAI 반환"""
        from core.llm_router import get_llm
        from langchain_openai import ChatOpenAI

        with patch("core.llm_router.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.ANTHROPIC_API_KEY = ""
            mock_settings.OLLAMA_BASE_URL = "http://localhost:11434"
            mock_settings.DEFAULT_MODEL = "openai/gpt-4o"

            get_llm.cache_clear()
            llm = get_llm("openai/gpt-4o")
            assert isinstance(llm, ChatOpenAI)

    def test_get_llm_unknown_provider(self):
        """알 수 없는 provider → ValueError"""
        from core.llm_router import get_llm

        get_llm.cache_clear()
        with pytest.raises(ValueError, match="지원하지 않는"):
            get_llm("unknown/model")


# ── Tool Registry 테스트 ───────────────────────────────────────────────

class TestToolRegistry:

    def test_get_known_tools(self):
        """알려진 도구 이름으로 도구 객체 반환"""
        from agents.tools.registry import ToolRegistry

        tools = ToolRegistry.get(["get_current_time"])
        assert len(tools) == 1

    def test_get_unknown_tool_raises(self):
        """미등록 도구 요청 시 ValueError"""
        from agents.tools.registry import ToolRegistry

        with pytest.raises(ValueError, match="등록되지 않은 도구"):
            ToolRegistry.get(["nonexistent_tool"])

    def test_list_all_returns_metadata(self):
        """list_all()이 메타데이터 목록 반환"""
        from agents.tools.registry import ToolRegistry

        tools = ToolRegistry.list_all()
        assert isinstance(tools, list)
        assert len(tools) > 0
        assert "name" in tools[0]


# ── Cost Calculator 테스트 ─────────────────────────────────────────────

class TestCostCalculator:

    def test_calculate_gpt4o_cost(self):
        """GPT-4o 비용 계산 정확성"""
        from services.cost_tracker import calculate_cost

        # 1M input tokens = $5.00, 1M output = $15.00
        cost = calculate_cost("openai/gpt-4o", prompt_tokens=1_000_000, completion_tokens=0)
        assert abs(cost - 5.0) < 0.001

    def test_ollama_is_free(self):
        """Ollama(로컬)는 비용 0"""
        from services.cost_tracker import calculate_cost

        cost = calculate_cost("ollama/llama3", prompt_tokens=100_000, completion_tokens=100_000)
        assert cost == 0.0

    def test_unknown_model_uses_default_pricing(self):
        """미등록 모델은 기본 단가 사용"""
        from services.cost_tracker import calculate_cost

        cost = calculate_cost("unknown/model", prompt_tokens=1000, completion_tokens=500)
        assert cost > 0  # 기본값 적용으로 0보다 큰 값
