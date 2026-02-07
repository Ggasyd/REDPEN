"""Submissions routes - simplified for MVP."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel
from app.database import get_db
from app.models import Submission, ExamVersion, Exam, WorkspaceMember
from app.models.enums import SubmissionStatus
from app.dependencies import get_workspace_id, require_teacher
from app.utils.storage import storage
from app.workers.tasks import process_submission_task

router = APIRouter()


class SubmissionCreate(BaseModel):
    exam_version_id: str
    student_id: str | None = None
    candidate_name: str | None = None


class SubmissionResponse(BaseModel):
    id: str
    status: SubmissionStatus
    original_filename: str
    page_count: int | None

    class Config:
        from_attributes = True


@router.post("/", response_model=SubmissionResponse, status_code=201)
async def upload_submission(
    file: UploadFile = File(...),
    exam_version_id: str = None,
    student_id: str | None = None,
    candidate_name: str | None = None,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Upload a submission (student copy)."""
    if not exam_version_id:
        raise HTTPException(status_code=400, detail="exam_version_id required")

    # Verify exam version
    result = await db.execute(
        select(ExamVersion)
        .join(Exam)
        .where(ExamVersion.id == UUID(exam_version_id))
        .where(Exam.workspace_id == workspace_id)
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Exam version not found")

    # Upload file to storage
    file_content = await file.read()
    storage_url = storage.upload_bytes(
        file_content,
        object_name=file.filename,
        content_type=file.content_type or "application/pdf",
        folder="submissions",
    )

    # Create submission
    submission = Submission(
        workspace_id=workspace_id,
        exam_version_id=UUID(exam_version_id),
        student_id=UUID(student_id) if student_id else None,
        candidate_name=candidate_name,
        status=SubmissionStatus.UPLOADED,
        original_filename=file.filename,
        storage_url=storage_url,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    # Trigger async processing
    process_submission_task.delay(str(submission.id))

    return SubmissionResponse(
        id=str(submission.id),
        status=submission.status,
        original_filename=submission.original_filename,
        page_count=submission.page_count,
    )


@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: UUID,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Get submission details."""
    result = await db.execute(
        select(Submission)
        .where(Submission.id == submission_id)
        .where(Submission.workspace_id == workspace_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    return SubmissionResponse(
        id=str(submission.id),
        status=submission.status,
        original_filename=submission.original_filename,
        page_count=submission.page_count,
    )


@router.get("/{submission_id}/processing_status")
async def get_processing_status(
    submission_id: UUID,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Get submission processing status."""
    result = await db.execute(
        select(Submission)
        .where(Submission.id == submission_id)
        .where(Submission.workspace_id == workspace_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    return {
        "submission_id": str(submission.id),
        "status": submission.status.value,
        "page_count": submission.page_count,
    }


@router.post("/{submission_id}/reprocess")
async def reprocess_submission(
    submission_id: UUID,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Reprocess a submission."""
    result = await db.execute(
        select(Submission)
        .where(Submission.id == submission_id)
        .where(Submission.workspace_id == workspace_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Update status and trigger reprocessing
    submission.status = SubmissionStatus.PROCESSING
    await db.commit()

    process_submission_task.delay(str(submission.id))

    return {"message": "Reprocessing started", "submission_id": str(submission.id)}
