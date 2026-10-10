"""Document router: generate Word documents using python-docx."""
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.task_submission import TaskSubmission
from app.schemas.task import DocumentGenerateRequest, DocumentResponse
from app.services.document_service import generate_docx

router = APIRouter()

# Directory for generated documents
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "documents")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/generate", response_model=DocumentResponse)
async def generate_document(
    req: DocumentGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a .docx file from the provided content."""
    file_name = f"hangzhou_trip_plan_{str(user.id)[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    try:
        generate_docx(file_path, req.title, req.content, req.format)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档生成失败: {str(e)}")

    # Update task submission
    result = await db.execute(
        TaskSubmission.__table__.select().where(TaskSubmission.user_id == user.id)
    )
    row = result.first()
    if row:
        await db.execute(
            TaskSubmission.__table__.update()
            .where(TaskSubmission.user_id == user.id)
            .values(docx_file_path=file_path, task2_document=True)
        )
    else:
        submission = TaskSubmission(
            user_id=user.id,
            docx_file_path=file_path,
            task2_document=True,
        )
        db.add(submission)

    await db.commit()
    return DocumentResponse(file_path=file_path, file_name=file_name)


def _is_inside_upload_dir(candidate: str) -> bool:
    """校验文件真实路径必须位于 UPLOAD_DIR 内（防路径遍历读取任意文件）。"""
    try:
        return os.path.commonpath(
            [os.path.abspath(candidate), os.path.abspath(UPLOAD_DIR)]
        ) == os.path.abspath(UPLOAD_DIR)
    except ValueError:  # 不同盘符等异常路径
        return False


# 兼容旧版本 AI 生成目录：之前 agent_tools.py 的 UPLOAD_DIR 路径计算错误，
# 导致部分文件生成到 backend/app/services/uploads/documents 或 backend/app/uploads/documents。
LEGACY_UPLOAD_DIRS = [
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "services", "uploads", "documents"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "documents"),
]


@router.get("/download/{file_name}")
async def download_document(file_name: str, user: User = Depends(get_current_user)):
    """Download a generated document.

    安全：仅接受 UPLOAD_DIR 内的文件名，剥离目录前缀/绝对路径，杜绝路径遍历。
    健壮性：若精确文件名不存在（如 AI 回复里被改写过的文件名、或陈旧链接），
    自动回退到「当前用户自己的」最新 .docx；不再回退全局文件，避免跨用户泄露。
    """
    from fastapi.responses import FileResponse

    def _resolve():
        user_prefix = str(user.id)[:8]
        # 1) 精确匹配主目录
        primary = os.path.join(UPLOAD_DIR, safe_name)
        if _is_inside_upload_dir(primary) and os.path.exists(primary):
            return primary, safe_name
        # 2) 精确匹配旧目录（兼容此前 agent_tools.py 路径算错的文件）
        for legacy_dir in LEGACY_UPLOAD_DIRS:
            legacy = os.path.join(legacy_dir, safe_name)
            if os.path.exists(legacy):
                return legacy, safe_name
        # 3) 按用户前缀回退主目录
        all_docs = [f for f in os.listdir(UPLOAD_DIR) if f.lower().endswith(".docx")]
        candidates = sorted(
            (f for f in all_docs if user_prefix in f),
            key=lambda f: os.path.getmtime(os.path.join(UPLOAD_DIR, f)),
            reverse=True,
        )
        if candidates:
            return os.path.join(UPLOAD_DIR, candidates[0]), candidates[0]
        # 4) 按用户前缀回退旧目录
        for legacy_dir in LEGACY_UPLOAD_DIRS:
            if not os.path.isdir(legacy_dir):
                continue
            all_docs = [f for f in os.listdir(legacy_dir) if f.lower().endswith(".docx")]
            candidates = sorted(
                (f for f in all_docs if user_prefix in f),
                key=lambda f: os.path.getmtime(os.path.join(legacy_dir, f)),
                reverse=True,
            )
            if candidates:
                return os.path.join(legacy_dir, candidates[0]), candidates[0]
        return None, None

    # 防路径遍历：只取文件名部分（剥离 .. / 目录前缀 / 绝对路径）
    safe_name = os.path.basename(file_name)
    file_path, resolved_name = _resolve()
    if not file_path:
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=resolved_name,
    )
