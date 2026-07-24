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
        generate_docx(file_path, req.title, req.content)
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
    """Download a generated document."""
    from fastapi.responses import FileResponse

    file_path = os.path.join(UPLOAD_DIR, file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=file_name,
    )
