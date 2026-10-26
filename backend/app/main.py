"""FastAPI application entry point."""
import asyncio
import contextlib
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    from app.database import init_db
    await init_db()

    # Seed initial data
    from app.services.seed_service import seed_initial_data
    await seed_initial_data()

    # 启动定时提醒调度器：每 30 秒扫描到期提醒并发送邮件到用户注册邮箱
    from app.services.reminder_service import send_due_reminders

    async def _reminder_scheduler_loop():
        while True:
            try:
                await send_due_reminders()
            except Exception:
                logger.exception("定时提醒调度异常")
            await asyncio.sleep(30)

    reminder_task = asyncio.create_task(_reminder_scheduler_loop())
    logger.info("定时提醒调度器已启动（每 30 秒扫描一次）")

    # 明确打印 LLM 运行模式，便于启动后立即确认是否接入真实模型
    if settings.use_mock_llm and settings.ALLOW_MOCK_LLM:
        logger.warning(
            "⚠️ LLM 当前为 MOCK 模式（未配置 LLM_API_KEY）。"
            "MOCK 返回的是写死的虚假回答，仅用于开发/自测，禁止用于收实验数据！"
        )
    else:
        logger.info("LLM 当前为 REAL 模式（真实模型：%s）", settings.LLM_MODEL)

    yield

    # Shutdown
    reminder_task.cancel()
    try:
        await reminder_task
    except asyncio.CancelledError:
        pass
    from app.database import engine
    await engine.dispose()


app = FastAPI(
    title="人机协作决策实验平台 API",
    description="人机协作决策实验平台 — 三组间对照实验系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from app.routers import auth, task, search, document, reminder, email, agent, questionnaire, log, admin, moa_group  # noqa: E402

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(task.router, prefix="/api/task", tags=["task"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(document.router, prefix="/api/document", tags=["document"])
app.include_router(reminder.router, prefix="/api/reminder", tags=["reminder"])
app.include_router(email.router, prefix="/api/email", tags=["email"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
app.include_router(questionnaire.router, prefix="/api/questionnaire", tags=["questionnaire"])
app.include_router(log.router, prefix="/api/log", tags=["log"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(moa_group.router, prefix="/api/moa", tags=["moa-group"])


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """兜底：完整异常写入服务端日志，但只向客户端返回通用消息，避免泄露内部细节。"""
    logger.exception(
        "Unhandled error on %s %s", request.method, request.url.path, exc_info=exc
    )
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误，请稍后重试"})


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "travel-experiment-platform",
        "llm_mode": "mock" if (settings.use_mock_llm and settings.ALLOW_MOCK_LLM) else "real",
    }
