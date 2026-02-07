"""Review routes - for correcting submissions."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID
from pydantic import BaseModel
from app.database import get_db
from app.models import Submission, AnswerBlock, GradeDecision, WorkspaceMember
from app.dependencies import get_workspace_id, require_teacher

router = APIRouter()


class AnswerBlockResponse(BaseModel):
    id: str
    question_id: str | None
    transcription: str | None
    crop_url: str
    confidence: float | None
    needs_review: bool

    class Config:
        from_attributes = True


class AnswerBlockUpdate(BaseModel):
    transcription: str | None = None
    question_id: str | None = None


class GradeDecisionUpdate(BaseModel):
    final_score: float
    teacher_notes: str | None = None


@router.get("/submissions/{submission_id}/answer_blocks", response_model=List[AnswerBlockResponse])
async def get_answer_blocks(
    submission_id: UUID,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Get all answer blocks for a submission."""
    # Verify submission
    result = await db.execute(
        select(Submission)
        .where(Submission.id == submission_id)
        .where(Submission.workspace_id == workspace_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Get answer blocks through pages
    from app.models import SubmissionPage
    result = await db.execute(
        select(AnswerBlock)
        .join(SubmissionPage)
        .where(SubmissionPage.submission_id == submission_id)
    )
    blocks = result.scalars().all()

    return [
        AnswerBlockResponse(
            id=str(b.id),
            question_id=str(b.question_id) if b.question_id else None,
            transcription=b.transcription,
            crop_url=b.crop_url,
            confidence=b.confidence,
            needs_review=b.needs_review,
        )
        for b in blocks
    ]


@router.patch("/answer_blocks/{block_id}")
async def update_answer_block(
    block_id: UUID,
    update_data: AnswerBlockUpdate,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Update an answer block (transcription, question assignment)."""
    # Get block and verify workspace access through submission
    result = await db.execute(
        select(AnswerBlock)
        .join(SubmissionPage)
        .join(Submission)
        .where(AnswerBlock.id == block_id)
        .where(Submission.workspace_id == workspace_id)
    )
    block = result.scalar_one_or_none()
    if not block:
        raise HTTPException(status_code=404, detail="Answer block not found")

    # Update fields
    if update_data.transcription is not None:
        block.transcription = update_data.transcription
        block.is_manually_edited = True

    if update_data.question_id is not None:
        block.question_id = UUID(update_data.question_id)

    await db.commit()

    return {"message": "Answer block updated", "block_id": str(block.id)}


@router.patch("/grade_decisions/{decision_id}")
async def update_grade_decision(
    decision_id: UUID,
    update_data: GradeDecisionUpdate,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Update grade decision."""
    result = await db.execute(
        select(GradeDecision)
        .join(Submission)
        .where(GradeDecision.id == decision_id)
        .where(Submission.workspace_id == workspace_id)
    )
    decision = result.scalar_one_or_none()
    if not decision:
        raise HTTPException(status_code=404, detail="Grade decision not found")

    decision.final_score = update_data.final_score
    if update_data.teacher_notes is not None:
        decision.teacher_notes = update_data.teacher_notes

    await db.commit()

    return {"message": "Grade decision updated", "decision_id": str(decision.id)}


@router.post("/submissions/{submission_id}/finalize")
async def finalize_submission(
    submission_id: UUID,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Finalize a submission (lock grades)."""
    result = await db.execute(
        select(Submission)
        .where(Submission.id == submission_id)
        .where(Submission.workspace_id == workspace_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    from datetime import datetime
    from app.models.enums import SubmissionStatus

    submission.is_finalized = True
    submission.finalized_at = datetime.utcnow()
    submission.status = SubmissionStatus.FINALIZED

    await db.commit()

    return {"message": "Submission finalized", "submission_id": str(submission.id)}
