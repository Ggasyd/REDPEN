"""Celery tasks for async processing."""

import asyncio
from datetime import datetime, timedelta
from uuid import UUID

from app.workers import celery_app


def get_async_db():
    """Get async database session for tasks."""
    from app.database import AsyncSessionLocal

    return AsyncSessionLocal()


@celery_app.task(
    name="app.workers.tasks.process_submission_task", bind=True, max_retries=3
)
def process_submission_task(self, submission_id: str):
    """Process a submission asynchronously.

    Pipeline:
    1. Split PDF into pages
    2. Extract answer blocks (3 pillars: geometric, semantic, detection)
    3. OCR/HTR for transcription
    4. Assign questions
    5. Assign student
    6. Generate grade proposal
    7. Flag for review if needed
    """
    try:
        # Run async processing
        asyncio.run(process_submission_async(submission_id))
        return {"status": "success", "submission_id": submission_id}
    except Exception as e:
        # Retry on failure
        raise self.retry(exc=e, countdown=60)


async def process_submission_async(submission_id: str):
    """Async processing logic for submission."""
    from sqlalchemy import select

    from app.ml.pipeline import process_submission_pipeline
    from app.models import Submission
    from app.models.enums import SubmissionStatus

    async with get_async_db() as db:
        # Get submission
        result = await db.execute(
            select(Submission).where(Submission.id == UUID(submission_id))
        )
        submission = result.scalar_one_or_none()

        if not submission:
            raise ValueError(f"Submission {submission_id} not found")

        # Update status
        submission.status = SubmissionStatus.PROCESSING
        await db.commit()

        try:
            # Run full pipeline
            await process_submission_pipeline(submission, db)

            # Update status
            submission.status = SubmissionStatus.PROCESSED
            await db.commit()

        except Exception as e:
            submission.status = SubmissionStatus.ERROR
            await db.commit()
            raise e


@celery_app.task(name="app.workers.tasks.retention_enforcement_task")
def retention_enforcement_task(run_id: str):
    """Enforce GDPR retention policies."""
    try:
        asyncio.run(retention_enforcement_async(run_id))
        return {"status": "success", "run_id": run_id}
    except Exception as e:
        return {"status": "error", "run_id": run_id, "error": str(e)}


async def retention_enforcement_async(run_id: str):
    """Async retention enforcement logic."""
    from sqlalchemy import select

    from app.models import DataRetentionRun, Submission, WorkspaceSettings
    from app.models.enums import RetentionMode

    async with get_async_db() as db:
        # Get run
        result = await db.execute(
            select(DataRetentionRun).where(DataRetentionRun.id == UUID(run_id))
        )
        run = result.scalar_one_or_none()

        if not run:
            raise ValueError(f"Retention run {run_id} not found")

        # Get workspace settings
        result = await db.execute(
            select(WorkspaceSettings).where(
                WorkspaceSettings.workspace_id == run.workspace_id
            )
        )
        settings_obj = result.scalar_one_or_none()

        if not settings_obj:
            raise ValueError(f"Settings not found for workspace {run.workspace_id}")

        # Calculate cutoff dates
        submissions_cutoff = datetime.utcnow() - timedelta(
            days=settings_obj.retention_submissions_days
        )

        # Find expired submissions
        result = await db.execute(
            select(Submission)
            .where(Submission.workspace_id == run.workspace_id)
            .where(Submission.created_at < submissions_cutoff)
        )
        expired_submissions = result.scalars().all()

        summary = {
            "total_expired": len(expired_submissions),
            "mode": run.mode.value,
        }

        if run.mode == RetentionMode.PREVIEW:
            # Just count, don't modify
            pass

        elif run.mode == RetentionMode.ANONYMIZE:
            # Anonymize submissions
            for submission in expired_submissions:
                submission.is_anonymized = True
                submission.anonymized_at = datetime.utcnow()
                submission.candidate_name = "ANONYMIZED"
                submission.student_id = None

            await db.commit()

        elif run.mode == RetentionMode.DELETE:
            # Hard delete (in production, also delete artifacts from storage)
            for submission in expired_submissions:
                await db.delete(submission)

            await db.commit()

        # Update run
        run.finished_at = datetime.utcnow()
        run.summary_json = summary
        await db.commit()


@celery_app.task(name="app.workers.tasks.retention_enforcement_daily")
def retention_enforcement_daily():
    """Daily retention enforcement for all workspaces."""
    try:
        asyncio.run(retention_enforcement_daily_async())
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def retention_enforcement_daily_async():
    """Run retention enforcement for all workspaces."""
    from sqlalchemy import select

    from app.models import DataRetentionRun, Workspace
    from app.models.enums import RetentionMode

    async with get_async_db() as db:
        # Get all active workspaces
        result = await db.execute(select(Workspace).where(Workspace.is_active))
        workspaces = result.scalars().all()

        for workspace in workspaces:
            # Create retention run
            run = DataRetentionRun(
                workspace_id=workspace.id,
                mode=RetentionMode.ANONYMIZE,  # Default to anonymize
                started_at=datetime.utcnow(),
            )
            db.add(run)
            await db.flush()

            # Trigger task
            retention_enforcement_task.delay(str(run.id))

        await db.commit()
