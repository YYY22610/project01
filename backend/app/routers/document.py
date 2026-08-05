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


@router.get("/download/{file_name}")
async def download_document(file_name: str, user: User = Depends(get_current_user)):
    """Download a generated document.

    健壮性：若精确文件名不存在（如 AI 回复里被改写过的文件名、或陈旧链接），
    自动回退到目录下最新的 .docx，避免用户点到 404。
    """
    from fastapi.responses import FileResponse

    file_path = os.path.join(UPLOAD_DIR, file_name)
    if not os.path.exists(file_path):
        # 回退：精确文件名找不到时，优先回退到「当前用户自己的」最新 .docx，
        # 避免误发其他参与者的文档；仅当用户无匹配文件时才取全局最新。
        all_docs = [f for f in os.listdir(UPLOAD_DIR) if f.lower().endswith(".docx")]
        user_prefix = str(user.id)[:8]
        own_docs = [f for f in all_docs if user_prefix in f]
        pool = own_docs if own_docs else all_docs
        candidates = sorted(
            pool,
            key=lambda f: os.path.getmtime(os.path.join(UPLOAD_DIR, f)),
            reverse=True,
        )
        if candidates:
            file_name = candidates[0]
            file_path = os.path.join(UPLOAD_DIR, file_name)
        else:
            raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=file_name,
    )
