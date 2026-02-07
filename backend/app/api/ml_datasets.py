"""ML datasets export routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from app.database import get_db
from app.models import AnswerBlockLabel, PreferenceSample, WorkspaceMember
from app.dependencies import get_workspace_id, require_admin

router = APIRouter()


@router.get("/datasets/supervised")
async def export_supervised_datasets(
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Export supervised learning datasets (answer block labels)."""
    result = await db.execute(
        select(AnswerBlockLabel).where(AnswerBlockLabel.workspace_id == workspace_id)
    )
    labels = result.scalars().all()

    return {
        "count": len(labels),
        "format": "jsonl",
        "message": "Supervised dataset export stub - implement full JSONL export",
    }


@router.get("/datasets/preferences")
async def export_preference_datasets(
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Export preference learning datasets."""
    result = await db.execute(
        select(PreferenceSample).where(PreferenceSample.workspace_id == workspace_id)
    )
    samples = result.scalars().all()

    return {
        "count": len(samples),
        "format": "jsonl",
        "message": "Preference dataset export stub - implement full JSONL export",
    }


@router.get("/calibration/metrics")
async def get_calibration_metrics(
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get AI calibration metrics."""
    from app.models import CalibrationRecord

    result = await db.execute(
        select(CalibrationRecord).where(CalibrationRecord.workspace_id == workspace_id)
    )
    records = result.scalars().all()

    # Calculate basic metrics
    if not records:
        return {"message": "No calibration data yet"}

    total = len(records)
    correct = sum(1 for r in records if r.was_correct)
    accuracy = correct / total if total > 0 else 0

    return {
        "total_predictions": total,
        "correct_predictions": correct,
        "accuracy": accuracy,
        "message": "Calibration metrics stub - implement detailed calibration analysis",
    }
