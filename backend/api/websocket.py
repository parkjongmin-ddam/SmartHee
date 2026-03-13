"""
WebSocket Handler — 에이전트 실행 실시간 스트리밍
클라이언트가 연결 후 태스크를 보내면 오케스트레이터 이벤트를 토큰 단위로 전송.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from agents.orchestrator.graph import AgentOrchestrator
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/agents/{agent_id}/stream")
async def agent_stream(websocket: WebSocket, agent_id: str):
    """
    WebSocket 연결 프로토콜:
      Client → {"input": "태스크 내용"}
      Server → {"type": "node_start", "node": "researcher"}
      Server → {"type": "token", "content": "안녕"}
      Server → {"type": "final", "content": "최종 결과"}
      Server → {"type": "done"}
      Server → {"type": "error", "detail": "오류 내용"}
    """
    await websocket.accept()
    logger.info(f"[WS] 연결: agent_id={agent_id}")

    try:
        # 에이전트 설정 로드 (간단화: 실제로는 DB 조회)
        data = await websocket.receive_json()
        user_input = data.get("input", "")

        if not user_input:
            await websocket.send_json({"type": "error", "detail": "입력이 비어있습니다."})
            return

        # TODO: DB에서 agent_config 로드
        # agent = await db.get(AgentConfig, agent_id)
        # config = {...}

        # 데모용 config (실제 구현에서는 DB 조회)
        config = {
            "id": agent_id,
            "model": "openai/gpt-4o",
            "system_prompt": "You are a helpful assistant.",
            "tools": ["web_search"],
            "is_multi_agent": False,
            "worker_configs": [],
        }

        orchestrator = AgentOrchestrator(config)

        async for event in orchestrator.stream(user_input):
            await websocket.send_json(event)

        await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        logger.info(f"[WS] 클라이언트 연결 종료: agent_id={agent_id}")
    except Exception as e:
        logger.error(f"[WS] 오류: {e}")
        try:
            await websocket.send_json({"type": "error", "detail": str(e)})
        except Exception:
            pass
