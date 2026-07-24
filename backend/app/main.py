"""FastAPI application entry point."""
import contextlib
import traceback
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    from app.database import init_db
    await init_db()

    # Seed initial data
    from app.services.seed_service import seed_initial_data
    await seed_initial_data()

    yield

    # Shutdown
    from app.database import engine
    await engine.dispose()


app = FastAPI(
    title="Travel Experiment Platform API",
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
from app.routers import auth, task, search, document, reminder, email, agent, questionnaire, log, admin  # noqa: E402

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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """兜底：把真实异常信息打到 uvicorn 控制台，并把简短消息返回前端，便于定位 500。"""
    traceback.print_exc()
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}", "path": str(request.url.path)},
    )


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "travel-experiment-platform"}
