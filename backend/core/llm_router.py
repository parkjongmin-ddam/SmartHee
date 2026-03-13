"""
LLM Router — 모델 추상화 레이어
모델 문자열 포맷: "provider/model-name"
예) "openai/gpt-4o", "anthropic/claude-3-5-sonnet-20241022", "ollama/llama3"
"""
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatOllama
from core.config import get_settings
from functools import lru_cache

settings = get_settings()


@lru_cache(maxsize=16)
def get_llm(model_string: str = None, temperature: float = 0.0) -> BaseChatModel:
    """
    모델 문자열을 파싱해 적절한 LangChain 모델 반환.
    캐시로 동일 설정 재사용.
    """
    model_string = model_string or settings.DEFAULT_MODEL
    provider, model_name = model_string.split("/", 1)

    match provider:
        case "openai":
            return ChatOpenAI(
                model=model_name,
                temperature=temperature,
                api_key=settings.OPENAI_API_KEY,
                streaming=True,
            )
        case "anthropic":
            return ChatAnthropic(
                model=model_name,
                temperature=temperature,
                api_key=settings.ANTHROPIC_API_KEY,
                streaming=True,
            )
        case "ollama":
            return ChatOllama(
                model=model_name,
                temperature=temperature,
                base_url=settings.OLLAMA_BASE_URL,
            )
        case _:
            raise ValueError(f"지원하지 않는 LLM provider: {provider}")


AVAILABLE_MODELS = [
    {"id": "openai/gpt-4o", "name": "GPT-4o", "provider": "openai"},
    {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai"},
    {"id": "anthropic/claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "provider": "anthropic"},
    {"id": "ollama/llama3", "name": "Llama 3 (Local)", "provider": "ollama"},
]
