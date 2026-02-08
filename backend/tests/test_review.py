"""Review endpoint tests."""
import pytest
from tests.utils import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnswerBlock,
    Exam,
    ExamVersion,
    GradeDecision,
    Submission,
    SubmissionPage,
    User,
)
from app.models.enums import AssignMethod, BlockType, SubmissionStatus, WorkspaceRole
from app.utils.security import hash_password


@pytest.mark.asyncio
async def test_get_answer_blocks(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="reviewer@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Review Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.flush()

    exam = Exam(workspace_id=workspace.id, title="Review Exam")
    db_session.add(exam)
    await db_session.flush()
    version = ExamVersion(exam_id=exam.id, version_number=1, is_active=True)
    db_session.add(version)
    await db_session.flush()
    submission = Submission(
        workspace_id=workspace.id,
        exam_version_id=version.id,
        original_filename="submission.pdf",
        storage_url="bucket/path",
    )
    db_session.add(submission)
    await db_session.flush()
    page = SubmissionPage(
        submission_id=submission.id,
        page_number=1,
        storage_url="bucket/page",
    )
    db_session.add(page)
    await db_session.flush()
    block = AnswerBlock(
        page_id=page.id,
        block_type=BlockType.TEXT,
        assign_method=AssignMethod.MANUAL,
        bbox_x=0,
        bbox_y=0,
        bbox_width=10,
        bbox_height=10,
        crop_url="bucket/crop",
    )
    db_session.add(block)
    await db_session.commit()

    response = await client.get(
        f"/api/review/submissions/{submission.id}/answer_blocks",
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(block.id)


@pytest.mark.asyncio
async def test_finalize_submission_updates_status(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="finalize@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Finalize Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.flush()

    exam = Exam(workspace_id=workspace.id, title="Finalize Exam")
    db_session.add(exam)
    await db_session.flush()
    version = ExamVersion(exam_id=exam.id, version_number=1, is_active=True)
    db_session.add(version)
    await db_session.flush()
    submission = Submission(
        workspace_id=workspace.id,
        exam_version_id=version.id,
        original_filename="submission.pdf",
        storage_url="bucket/path",
        status=SubmissionStatus.UPLOADED,
    )
    db_session.add(submission)
    await db_session.commit()

    response = await client.post(
        f"/api/review/submissions/{submission.id}/finalize",
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 200
    assert response.json()["submission_id"] == str(submission.id)


@pytest.mark.asyncio
async def test_update_grade_decision(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
    workspace_factory,
    membership_factory,
):
    user = User(
        email="grader@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    workspace = workspace_factory(name="Grade Workspace")
    db_session.add_all([user, workspace])
    await db_session.flush()
    membership = membership_factory(
        user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.TEACHER
    )
    db_session.add(membership)
    await db_session.flush()

    exam = Exam(workspace_id=workspace.id, title="Grade Exam")
    db_session.add(exam)
    await db_session.flush()
    version = ExamVersion(exam_id=exam.id, version_number=1, is_active=True)
    db_session.add(version)
    await db_session.flush()
    submission = Submission(
        workspace_id=workspace.id,
        exam_version_id=version.id,
        original_filename="submission.pdf",
        storage_url="bucket/path",
    )
    db_session.add(submission)
    await db_session.flush()
    decision = GradeDecision(submission_id=submission.id, final_score=0)
    db_session.add(decision)
    await db_session.commit()

    response = await client.patch(
        f"/api/review/grade_decisions/{decision.id}",
        json={"final_score": 95, "teacher_notes": "Great work"},
        headers={**auth_headers(user), "X-Workspace-Id": str(workspace.id)},
    )

    assert response.status_code == 200
    assert response.json()["decision_id"] == str(decision.id)
