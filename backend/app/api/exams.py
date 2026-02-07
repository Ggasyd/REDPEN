"""Exams routes - simplified for MVP."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_workspace_id, require_teacher
from app.models import Exam, ExamVersion, Question, WorkspaceMember
from app.models.enums import QuestionType

router = APIRouter()


class ExamCreate(BaseModel):
    title: str
    description: str | None = None
    subject: str | None = None
    grade_level: str | None = None


class ExamResponse(BaseModel):
    id: str
    title: str
    description: str | None
    subject: str | None

    class Config:
        from_attributes = True


class QuestionCreate(BaseModel):
    question_number: str
    question_text: str
    question_type: QuestionType
    max_points: float
    order_index: int


@router.post("/", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
async def create_exam(
    exam_data: ExamCreate,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Create a new exam."""
    exam = Exam(
        workspace_id=workspace_id,
        title=exam_data.title,
        description=exam_data.description,
        subject=exam_data.subject,
        grade_level=exam_data.grade_level,
    )
    db.add(exam)
    await db.flush()

    # Create version 1
    version = ExamVersion(
        exam_id=exam.id,
        version_number=1,
        is_active=True,
    )
    db.add(version)
    await db.commit()
    await db.refresh(exam)

    return ExamResponse(
        id=str(exam.id),
        title=exam.title,
        description=exam.description,
        subject=exam.subject,
    )


@router.post("/{exam_id}/versions")
async def create_exam_version(
    exam_id: UUID,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Create a new version of an exam."""
    # Get exam
    result = await db.execute(
        select(Exam).where(Exam.id == exam_id).where(Exam.workspace_id == workspace_id)
    )
    exam = result.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    # Count existing versions
    result = await db.execute(select(ExamVersion).where(ExamVersion.exam_id == exam_id))
    versions = result.scalars().all()
    new_version_number = len(versions) + 1

    # Create new version
    version = ExamVersion(
        exam_id=exam_id,
        version_number=new_version_number,
        is_active=True,
    )
    db.add(version)
    await db.commit()

    return {"message": "Version created", "version_number": new_version_number}


@router.post("/versions/{version_id}/questions", status_code=status.HTTP_201_CREATED)
async def create_questions_bulk(
    version_id: UUID,
    questions: list[QuestionCreate],
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Create questions in bulk for an exam version."""
    # Verify version exists and belongs to workspace
    result = await db.execute(
        select(ExamVersion)
        .join(Exam)
        .where(ExamVersion.id == version_id)
        .where(Exam.workspace_id == workspace_id)
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Exam version not found")

    # Create questions
    created_questions = []
    for q_data in questions:
        question = Question(
            exam_version_id=version_id,
            question_number=q_data.question_number,
            question_text=q_data.question_text,
            question_type=q_data.question_type,
            max_points=q_data.max_points,
            order_index=q_data.order_index,
        )
        db.add(question)
        created_questions.append(question)

    await db.commit()

    return {
        "message": f"Created {len(created_questions)} questions",
        "count": len(created_questions),
    }
