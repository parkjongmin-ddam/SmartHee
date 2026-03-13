from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.database import init_db
from core.config import get_settings
from api.routes.agents import router as agents_router
from api.routes.evaluation import router as eval_router
from api.routes.platform import router as platform_router
from api.routes.costs import router as costs_router
from api.websocket import router as ws_router
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행"""
    logger.info("🚀 AgentForge 서버 시작")
    await init_db()
    yield
    logger.info("🛑 AgentForge 서버 종료")


app = FastAPI(
    title="AgentForge API",
    description="Conversation-driven Multi-Agent Orchestration Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS (프론트엔드 개발 서버 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(agents_router, prefix="/api/v1", tags=["Agents"])
app.include_router(ws_router, tags=["WebSocket"])
app.include_router(eval_router, prefix="/api/v1", tags=["Evaluation"])
app.include_router(platform_router, prefix="/api/v1", tags=["Platform"])
app.include_router(costs_router, prefix="/api/v1", tags=["Costs"])


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}
