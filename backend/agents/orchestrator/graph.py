"""
LangGraph Orchestrator (Phase 3 — Celery + Platform 통합)
변경점:
  - state_modifier → prompt 파라미터 변경 (LangGraph 1.x 호환)
  - system_prompt 미정의 변수 수정 (self.config에서 가져오도록)
  - build_worker_node role 변수 분리
  - 깨진 문자열(결과 메시지) 한글로 복원
"""

from typing import AsyncGenerator
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from agents.orchestrator.state import AgentState, MAX_ITERATIONS
from agents.orchestrator.supervisor import SupervisorAgent
from agents.tools.registry import ToolRegistry
from core.llm_router import get_llm
from core.tracing import AgentTracer, get_langfuse_callback
import uuid, time, logging

logger = logging.getLogger(__name__)


def build_worker_node(worker_cfg: dict, model: str):
    llm = get_llm(model, temperature=0.0)
    tools = ToolRegistry.get(worker_cfg.get("tools", []))
    role = worker_cfg.get("role", "")
    react_agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=role if role else None,   # ← state_modifier → prompt
    )
    worker_name = worker_cfg["name"]

    async def worker_node(state: AgentState) -> dict:
        logger.info(f"[Worker:{worker_name}] 실행")
        cb = get_langfuse_callback(state.get("run_id"))
        response = await react_agent.ainvoke(
            {"messages": [HumanMessage(content=state["task_input"])]},
            config={"callbacks": [cb]} if cb else {},
        )
        final_msg = response["messages"][-1].content
        return {
            "intermediate_results": {**state.get("intermediate_results", {}), worker_name: final_msg},
            "messages": response["messages"],
        }

    worker_node.__name__ = f"worker_{worker_name}"
    return worker_node


class AgentOrchestrator:
    def __init__(self, agent_config: dict):
        self.config = agent_config
        self.graph = self._build_graph()

    def _build_graph(self):
        return self._build_multi_agent_graph() if self.config.get("is_multi_agent") else self._build_single_agent_graph()

    def _build_single_agent_graph(self):
        llm = get_llm(self.config["model"], temperature=0.0)
        tools = ToolRegistry.get(self.config.get("tools", []))
        system_prompt = self.config.get("system_prompt", "")   # ← config에서 가져오도록
        react_agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=system_prompt if system_prompt else None,   # ← state_modifier → prompt
        )

        async def single_agent_node(state: AgentState) -> dict:
            cb = get_langfuse_callback(state.get("run_id"))
            logger.info(f"[Langfuse] 콜백 생성 결과: {cb}")
            response = await react_agent.ainvoke(
                {"messages": [HumanMessage(content=state["task_input"])]},
                config={"callbacks": [cb]} if cb else {},
            )
            return {"final_output": response["messages"][-1].content, "messages": response["messages"]}

        graph = StateGraph(AgentState)
        graph.add_node("agent", single_agent_node)
        graph.set_entry_point("agent")
        graph.add_edge("agent", END)
        return graph.compile()

    def _build_multi_agent_graph(self):
        worker_configs = self.config.get("worker_configs", [])
        worker_names = [w["name"] for w in worker_configs]
        supervisor = SupervisorAgent(worker_names=worker_names, model=self.config["model"])

        graph = StateGraph(AgentState)
        graph.add_node("supervisor", supervisor)
        for w in worker_configs:
            graph.add_node(w["name"], build_worker_node(w, self.config["model"]))
            graph.add_edge(w["name"], "supervisor")

        graph.add_conditional_edges(
            "supervisor",
            lambda s: END if s.get("next", "FINISH") == "FINISH" else s["next"],
            {**{n: n for n in worker_names}, END: END},
        )
        graph.set_entry_point("supervisor")
        return graph.compile()

    async def run(self, user_input: str, run_id: str = None) -> dict:
        """Returns: {"output": str, "run_id": str, "latency_ms": int}"""
        run_id = run_id or str(uuid.uuid4())
        start = time.time()

        with AgentTracer(run_id, self.config.get("name", "agent"), user_input) as tracer:
            initial_state: AgentState = {
                "messages": [], "next": "", "task_input": user_input,
                "intermediate_results": {}, "final_output": "",
                "agent_config_id": str(self.config.get("id", "")),
                "run_id": run_id, "iteration_count": 0,
            }
            final_state = await self.graph.ainvoke(initial_state)
            output = final_state.get("final_output", "결과를 생성하지 못했습니다.")
            latency_ms = int((time.time() - start) * 1000)
            tracer.update(output=output, metadata={"latency_ms": latency_ms})

        return {"output": output, "run_id": run_id, "latency_ms": latency_ms}

    async def stream(self, user_input: str) -> AsyncGenerator[dict, None]:
        run_id = str(uuid.uuid4())
        initial_state: AgentState = {
            "messages": [], "next": "", "task_input": user_input,
            "intermediate_results": {}, "final_output": "",
            "agent_config_id": str(self.config.get("id", "")),
            "run_id": run_id, "iteration_count": 0,
        }
        async for event in self.graph.astream_events(initial_state, version="v2"):
            et = event.get("event")
            if et == "on_chain_start":
                yield {"type": "node_start", "node": event.get("name"), "run_id": run_id}
            elif et == "on_chat_model_stream":
                token = event.get("data", {}).get("chunk", {}).content
                if token:
                    yield {"type": "token", "content": token, "run_id": run_id}
            elif et == "on_chain_end":
                out = event.get("data", {}).get("output", {})
                if isinstance(out, dict) and "final_output" in out:
                    yield {"type": "final", "content": out["final_output"], "run_id": run_id}