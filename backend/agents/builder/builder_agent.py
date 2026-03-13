"""
Builder Agent (Meta Agent)
사용자의 자연어 요청 → AgentConfig JSON 생성

핵심 흐름:
  사용자 입력 → LLM (의도 분석 + 구성 생성) → AgentConfig → DB 저장
"""
import json
import re
from typing import AsyncGenerator
from langchain_core.messages import HumanMessage, SystemMessage
from core.llm_router import get_llm
from core.config import get_settings
from agents.tools.registry import ToolRegistry
from agents.builder.prompts import BUILDER_SYSTEM_PROMPT, BUILDER_REFINEMENT_PROMPT
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


class BuilderAgent:
    """
    자연어 입력을 AgentConfig dict로 변환하는 메타 에이전트.

    사용 예:
        builder = BuilderAgent()
        config = await builder.create("웹 검색해서 요약하는 에이전트 만들어줘")
        # → {"name": "Web Research Agent", "tools": ["web_search"], ...}
    """

    def __init__(self, model: str = None):
        self.llm = get_llm(model or settings.DEFAULT_MODEL, temperature=0.2)
        self._tool_metadata_str = json.dumps(
            ToolRegistry.list_all(), ensure_ascii=False, indent=2
        )

    async def create(self, user_request: str) -> dict:
        """
        자연어 요청으로 새 에이전트 구성 생성.
        Returns: AgentConfig dict
        """
        messages = [
            SystemMessage(content=BUILDER_SYSTEM_PROMPT.format(
                tool_metadata=self._tool_metadata_str
            )),
            HumanMessage(content=user_request),
        ]

        response = await self.llm.ainvoke(messages)
        return self._parse_config(response.content)

    async def refine(self, current_config: dict, user_request: str) -> dict:
        """
        기존 에이전트 구성을 사용자 요청에 따라 수정.
        Returns: 수정된 AgentConfig dict
        """
        messages = [
            SystemMessage(content=BUILDER_SYSTEM_PROMPT.format(
                tool_metadata=self._tool_metadata_str
            )),
            HumanMessage(content=BUILDER_REFINEMENT_PROMPT.format(
                current_config=json.dumps(current_config, ensure_ascii=False, indent=2),
                user_request=user_request,
            )),
        ]

        response = await self.llm.ainvoke(messages)
        refined = self._parse_config(response.content)

        # 기존 구성 기반으로 덮어쓰기 (ID 등 메타데이터 유지)
        merged = {**current_config, **refined}
        return merged

    async def stream_create(self, user_request: str) -> AsyncGenerator[str, None]:
        """
        생성 과정을 스트리밍으로 반환 (WebSocket용).
        """
        messages = [
            SystemMessage(content=BUILDER_SYSTEM_PROMPT.format(
                tool_metadata=self._tool_metadata_str
            )),
            HumanMessage(content=user_request),
        ]

        full_response = ""
        async for chunk in self.llm.astream(messages):
            token = chunk.content
            full_response += token
            yield token  # WebSocket으로 토큰 단위 전송

        # 스트리밍 완료 후 최종 파싱 결과 전송
        try:
            config = self._parse_config(full_response)
            yield f"\n__FINAL_CONFIG__:{json.dumps(config, ensure_ascii=False)}"
        except Exception as e:
            yield f"\n__ERROR__:{str(e)}"

    def _parse_config(self, raw: str) -> dict:
        """
        LLM 응답에서 JSON 파싱.
        마크다운 코드블록이 포함된 경우도 처리.
        """
        # ```json ... ``` 코드블록 제거
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()

        try:
            config = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Builder Agent JSON 파싱 실패: {e}\n원본: {raw}")
            raise ValueError(f"에이전트 구성 생성 실패. 다시 시도해주세요. (파싱 오류: {e})")

        # 필수 필드 검증
        required_fields = ["name", "tools", "system_prompt"]
        for field in required_fields:
            if field not in config:
                raise ValueError(f"필수 필드 누락: {field}")

        # 기본값 보완
        config.setdefault("model", settings.DEFAULT_MODEL)
        config.setdefault("is_multi_agent", False)
        config.setdefault("worker_configs", [])
        config.setdefault("description", "")

        return config
