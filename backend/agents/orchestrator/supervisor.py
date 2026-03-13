"""
Supervisor Agent
멀티에이전트 오케스트레이션의 중앙 조율자.

역할:
  - 태스크를 분석해 적절한 워커에게 위임
  - 워커 결과를 평가해 추가 작업 또는 완료 결정
  - 루프 방지 (MAX_ITERATIONS)
"""
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.output_parsers import JsonOutputParser
from core.llm_router import get_llm
from agents.orchestrator.state import AgentState, NextNode, MAX_ITERATIONS
import logging

logger = logging.getLogger(__name__)

SUPERVISOR_PROMPT_TEMPLATE = """당신은 멀티에이전트 팀을 조율하는 **Supervisor**입니다.

## 팀 구성
{worker_list}

## 현재 태스크
{task_input}

## 지금까지의 중간 결과
{intermediate_results}

## 지시사항
1. 중간 결과를 검토해 태스크가 완료됐는지 판단하세요.
2. 아직 작업이 필요하다면 가장 적합한 워커를 선택하세요.
3. 모든 작업이 완료됐다면 "FINISH"를 선택하세요.

반드시 아래 JSON 형식으로만 응답하세요:
{{"next": "worker_name 또는 FINISH", "reason": "선택 이유"}}"""


class SupervisorAgent:
    """
    Supervisor 노드 — LangGraph 그래프에서 중앙 라우터 역할.

    __call__ 을 구현해 LangGraph 노드로 직접 사용 가능:
        graph.add_node("supervisor", SupervisorAgent(workers, model))
    """

    def __init__(self, worker_names: list[str], model: str):
        self.worker_names = worker_names
        self.llm = get_llm(model, temperature=0.0)
        self.parser = JsonOutputParser()

    async def __call__(self, state: AgentState) -> dict:
        """LangGraph 노드로 호출됨"""

        # 루프 방지
        if state.get("iteration_count", 0) >= MAX_ITERATIONS:
            logger.warning(f"[Supervisor] MAX_ITERATIONS({MAX_ITERATIONS}) 초과 → 강제 종료")
            return {"next": "FINISH", "iteration_count": state["iteration_count"] + 1}

        # 중간 결과 포맷팅
        results_str = "\n".join([
            f"[{k}]: {v[:300]}..."  # 너무 긴 결과는 축약
            for k, v in state.get("intermediate_results", {}).items()
        ]) or "없음"

        worker_list_str = "\n".join([
            f"- {name}: 태스크의 일부를 처리하는 전문 에이전트"
            for name in self.worker_names
        ])

        messages = [
            SystemMessage(content=SUPERVISOR_PROMPT_TEMPLATE.format(
                worker_list=worker_list_str,
                task_input=state["task_input"],
                intermediate_results=results_str,
            )),
            HumanMessage(content="다음 액션을 결정하세요."),
        ]

        response = await self.llm.ainvoke(messages)

        try:
            parsed = self.parser.parse(response.content)
            next_node: NextNode = parsed.get("next", "FINISH")
        except Exception as e:
            logger.error(f"[Supervisor] 응답 파싱 실패: {e}")
            next_node = "FINISH"

        # 유효하지 않은 워커 이름 방어
        if next_node != "FINISH" and next_node not in self.worker_names:
            logger.warning(f"[Supervisor] 알 수 없는 워커: {next_node} → FINISH로 전환")
            next_node = "FINISH"

        logger.info(f"[Supervisor] → {next_node} (iteration: {state.get('iteration_count', 0) + 1})")

        return {
            "next": next_node,
            "messages": [AIMessage(content=response.content)],
            "iteration_count": state.get("iteration_count", 0) + 1,
        }
