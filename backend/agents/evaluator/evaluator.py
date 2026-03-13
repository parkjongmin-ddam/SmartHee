"""
Agent Evaluation System — Phase 2 핵심
에이전트 실행 결과를 다양한 지표로 자동 평가.

평가 지표:
  - Task Success Rate  : LLM이 결과의 목표 달성 여부를 판단
  - Token Efficiency   : 결과 품질 대비 토큰 사용량
  - Latency            : 실행 시간 (P50, P95)
  - Tool Call Accuracy : 적절한 도구를 올바르게 사용했는지
"""
from dataclasses import dataclass, field
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage
from core.llm_router import get_llm
from core.config import get_settings
from sqlalchemy.ext.asyncio import AsyncSession
from models.evaluation import EvaluationResult
import json
import uuid
import time
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


# ── 평가 결과 데이터클래스 ─────────────────────────────────────────────

@dataclass
class EvalScore:
    task_success: float        # 0.0 ~ 1.0
    token_efficiency: float    # 0.0 ~ 1.0 (낮을수록 토큰 낭비)
    latency_ms: int
    tool_call_accuracy: float  # 0.0 ~ 1.0
    overall_score: float = field(init=False)
    reasoning: str = ""
    raw_metrics: dict = field(default_factory=dict)

    def __post_init__(self):
        # 가중 평균: task_success 40%, token_efficiency 20%, tool_accuracy 40%
        self.overall_score = round(
            self.task_success * 0.4
            + self.token_efficiency * 0.2
            + self.tool_call_accuracy * 0.4,
            3,
        )


# ── LLM 기반 평가자 ───────────────────────────────────────────────────

EVAL_SYSTEM_PROMPT = """당신은 AI 에이전트의 실행 결과를 객관적으로 평가하는 전문가입니다.

## 평가 기준
1. **task_success** (0.0~1.0): 사용자의 원래 요청을 얼마나 잘 달성했는가
   - 1.0: 완벽히 달성, 0.5: 부분 달성, 0.0: 미달성

2. **tool_call_accuracy** (0.0~1.0): 도구를 적절히, 효율적으로 사용했는가
   - 불필요한 도구 호출이 없었는지
   - 올바른 도구를 선택했는지

3. **reasoning**: 평가 근거를 한국어로 간략히 설명

반드시 아래 JSON 형식으로만 응답하세요:
{"task_success": 0.8, "tool_call_accuracy": 0.9, "reasoning": "설명"}"""


class AgentEvaluator:
    """
    에이전트 실행 결과 자동 평가기.

    사용:
        evaluator = AgentEvaluator()
        score = await evaluator.evaluate(
            task="뉴스 요약해줘",
            output="오늘의 주요 뉴스: ...",
            token_used={"prompt": 300, "completion": 200},
            latency_ms=2500,
            tool_calls=["web_search"],
        )
        print(score.overall_score)  # 0.85
    """

    def __init__(self, model: str = None):
        # 평가 자체는 저렴한 모델로 (비용 절감)
        self.llm = get_llm(model or "openai/gpt-4o-mini", temperature=0.0)

    async def evaluate(
        self,
        task: str,
        output: str,
        token_used: dict,
        latency_ms: int,
        tool_calls: list[str] = None,
        expected_tools: list[str] = None,
    ) -> EvalScore:
        """단일 실행 평가"""

        # LLM으로 task_success, tool_call_accuracy 평가
        llm_scores = await self._llm_evaluate(task, output, tool_calls or [])

        # Token Efficiency: 결과 길이 / 총 토큰 비율 (단순 휴리스틱)
        total_tokens = token_used.get("prompt", 0) + token_used.get("completion", 0)
        output_len = len(output)
        token_efficiency = min(1.0, output_len / max(total_tokens, 1)) if total_tokens > 0 else 0.5

        return EvalScore(
            task_success=llm_scores.get("task_success", 0.5),
            token_efficiency=round(token_efficiency, 3),
            latency_ms=latency_ms,
            tool_call_accuracy=llm_scores.get("tool_call_accuracy", 0.5),
            reasoning=llm_scores.get("reasoning", ""),
            raw_metrics={
                "total_tokens": total_tokens,
                "prompt_tokens": token_used.get("prompt", 0),
                "completion_tokens": token_used.get("completion", 0),
                "tool_calls": tool_calls or [],
            },
        )

    async def _llm_evaluate(self, task: str, output: str, tool_calls: list[str]) -> dict:
        """LLM Judge 패턴으로 품질 평가"""
        user_msg = f"""
## 원래 태스크
{task}

## 에이전트 출력
{output[:2000]}  

## 사용된 도구
{', '.join(tool_calls) if tool_calls else '없음'}
"""
        messages = [
            SystemMessage(content=EVAL_SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            return json.loads(response.content)
        except Exception as e:
            logger.warning(f"[Evaluator] LLM 평가 실패: {e}")
            return {"task_success": 0.5, "tool_call_accuracy": 0.5, "reasoning": "평가 실패"}


# ── A/B 테스트 프레임워크 ─────────────────────────────────────────────

class ABTestRunner:
    """
    동일 태스크에 여러 에이전트 구성을 비교 실행.

    사용:
        runner = ABTestRunner()
        report = await runner.run(
            task="AI 뉴스 요약",
            configs=[config_a, config_b],
            n_runs=3,
        )
        print(report["winner"])  # "config_a"
    """

    def __init__(self):
        self.evaluator = AgentEvaluator()

    async def run(
        self,
        task: str,
        configs: list[dict],
        n_runs: int = 3,
    ) -> dict:
        from agents.orchestrator.graph import AgentOrchestrator

        results = {}

        for cfg in configs:
            cfg_name = cfg.get("name", str(uuid.uuid4())[:8])
            scores = []

            for i in range(n_runs):
                start = time.time()
                try:
                    orchestrator = AgentOrchestrator(cfg)
                    output = await orchestrator.run(task)
                    latency_ms = int((time.time() - start) * 1000)

                    score = await self.evaluator.evaluate(
                        task=task,
                        output=output,
                        token_used={"prompt": 300, "completion": 150},  # TODO: 실측값 연동
                        latency_ms=latency_ms,
                    )
                    scores.append(score)
                    logger.info(f"[ABTest] {cfg_name} run {i+1}: score={score.overall_score}")

                except Exception as e:
                    logger.error(f"[ABTest] {cfg_name} run {i+1} 실패: {e}")

            if scores:
                results[cfg_name] = {
                    "avg_score": round(sum(s.overall_score for s in scores) / len(scores), 3),
                    "avg_latency_ms": int(sum(s.latency_ms for s in scores) / len(scores)),
                    "avg_task_success": round(sum(s.task_success for s in scores) / len(scores), 3),
                    "runs": len(scores),
                    "scores": [s.overall_score for s in scores],
                }

        # 승자 결정
        winner = max(results, key=lambda k: results[k]["avg_score"]) if results else None

        return {
            "task": task,
            "winner": winner,
            "results": results,
            "recommendation": f"'{winner}' 구성이 평균 점수 {results[winner]['avg_score']}으로 가장 우수합니다." if winner else "비교 실패",
        }
