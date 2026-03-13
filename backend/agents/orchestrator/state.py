"""
LangGraph Shared State
모든 에이전트 노드가 공유하는 상태 정의.
TypedDict + Annotated로 LangGraph가 상태 병합 방식을 인식.
"""
from typing import Annotated, Sequence, TypedDict, Literal
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    오케스트레이터 전체에서 공유되는 상태.

    messages: 대화 이력 (add_messages: 덮어쓰지 않고 append)
    next: Supervisor가 다음에 실행할 노드 이름
    task_input: 현재 처리 중인 태스크 원문
    intermediate_results: 각 워커의 중간 결과물
    final_output: 최종 결과
    agent_config_id: 실행 중인 AgentConfig의 UUID
    run_id: 현재 실행 ID (Langfuse 트레이싱용)
    iteration_count: 루프 방지용 반복 횟수
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next: str
    task_input: str
    intermediate_results: dict[str, str]   # {worker_name: result}
    final_output: str
    agent_config_id: str
    run_id: str
    iteration_count: int


# Supervisor의 라우팅 결정 타입
# "FINISH" → 종료, 그 외는 워커 노드 이름
NextNode = Literal["FINISH"] | str


MAX_ITERATIONS = 10  # 무한 루프 방지 임계값
