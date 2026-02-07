"""GDPR and retention routes."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_workspace_id, require_admin, require_owner
from app.models import DataRetentionRun, Student, WorkspaceMember, WorkspaceSettings
from app.models.enums import RetentionMode

router = APIRouter()


class RetentionSettingsResponse(BaseModel):
    retention_submissions_days: int
    retention_artifacts_days: int
    retention_ml_days: int
    anonymize_on_expiry: bool
    hard_delete_on_expiry: bool
    ai_pseudonymize_before_send: bool
    eu_only_mode: bool

    class Config:
        from_attributes = True


class RetentionSettingsUpdate(BaseModel):
    retention_submissions_days: int | None = None
    retention_artifacts_days: int | None = None
    retention_ml_days: int | None = None
    anonymize_on_expiry: bool | None = None
    hard_delete_on_expiry: bool | None = None
    ai_pseudonymize_before_send: bool | None = None
    eu_only_mode: bool | None = None


@router.get("/settings/retention", response_model=RetentionSettingsResponse)
async def get_retention_settings(
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get GDPR retention settings for workspace."""
    result = await db.execute(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == workspace_id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")

    return RetentionSettingsResponse.model_validate(settings)


@router.patch("/settings/retention")
async def update_retention_settings(
    update_data: RetentionSettingsUpdate,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    """Update GDPR retention settings (OWNER only)."""
    result = await db.execute(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == workspace_id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")

    # Update fields
    if update_data.retention_submissions_days is not None:
        settings.retention_submissions_days = update_data.retention_submissions_days
    if update_data.retention_artifacts_days is not None:
        settings.retention_artifacts_days = update_data.retention_artifacts_days
    if update_data.retention_ml_days is not None:
        settings.retention_ml_days = update_data.retention_ml_days
    if update_data.anonymize_on_expiry is not None:
        settings.anonymize_on_expiry = update_data.anonymize_on_expiry
    if update_data.hard_delete_on_expiry is not None:
        settings.hard_delete_on_expiry = update_data.hard_delete_on_expiry
    if update_data.ai_pseudonymize_before_send is not None:
        settings.ai_pseudonymize_before_send = update_data.ai_pseudonymize_before_send
    if update_data.eu_only_mode is not None:
        settings.eu_only_mode = update_data.eu_only_mode

    await db.commit()

    return {"message": "Settings updated"}


@router.post("/retention/run")
async def run_retention_enforcement(
    mode: RetentionMode,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    """Run retention enforcement (preview, anonymize, or delete)."""
    # Create run record
    run = DataRetentionRun(
        workspace_id=workspace_id,
        mode=mode,
        started_at=datetime.utcnow(),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Trigger async task
    from app.workers.tasks import retention_enforcement_task

    retention_enforcement_task.delay(str(run.id))

    return {
        "message": "Retention enforcement started",
        "run_id": str(run.id),
        "mode": mode.value,
    }


@router.post("/student/{student_id}/anonymize")
async def anonymize_student(
    student_id: UUID,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Anonymize a student (GDPR right to be forgotten)."""
    result = await db.execute(
        select(Student)
        .where(Student.id == student_id)
        .where(Student.workspace_id == workspace_id)
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Anonymize
    student.first_name = "ANONYMIZED"
    student.last_name = "ANONYMIZED"
    student.display_name = None
    student.email = None
    student.student_number = None
    student.is_anonymized = True
    student.anonymized_at = datetime.utcnow()

    await db.commit()

    return {"message": "Student anonymized", "student_id": str(student.id)}
