"""Classrooms routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_workspace_id, require_teacher
from app.models import Classroom, Student, WorkspaceMember

router = APIRouter()


class ClassroomCreate(BaseModel):
    name: str
    description: str | None = None
    grade_level: str | None = None
    academic_year: str | None = None


class ClassroomResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str | None
    grade_level: str | None
    academic_year: str | None

    class Config:
        from_attributes = True


class StudentCreate(BaseModel):
    first_name: str
    last_name: str
    student_number: str | None = None
    email: str | None = None


class StudentResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    display_name: str | None
    student_number: str | None
    email: str | None

    class Config:
        from_attributes = True


@router.post("/", response_model=ClassroomResponse, status_code=status.HTTP_201_CREATED)
async def create_classroom(
    classroom_data: ClassroomCreate,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Create a new classroom."""
    classroom = Classroom(
        workspace_id=workspace_id,
        name=classroom_data.name,
        description=classroom_data.description,
        grade_level=classroom_data.grade_level,
        academic_year=classroom_data.academic_year,
    )
    db.add(classroom)
    await db.commit()
    await db.refresh(classroom)

    return ClassroomResponse(
        id=str(classroom.id),
        workspace_id=str(classroom.workspace_id),
        name=classroom.name,
        description=classroom.description,
        grade_level=classroom.grade_level,
        academic_year=classroom.academic_year,
    )


@router.post("/{classroom_id}/students/import")
async def import_students(
    classroom_id: UUID,
    file: UploadFile = File(...),
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Import students from CSV/Excel/PDF.

    Stub: For MVP, expects CSV with columns: first_name, last_name, student_number, email
    """
    # Verify classroom belongs to workspace
    result = await db.execute(
        select(Classroom)
        .where(Classroom.id == classroom_id)
        .where(Classroom.workspace_id == workspace_id)
    )
    classroom = result.scalar_one_or_none()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")

    # Read file content
    content = await file.read()

    # Stub: Simple CSV parsing (in production, use pandas or OCR for PDF)
    if file.filename.endswith(".csv"):
        import csv
        import io

        reader = csv.DictReader(io.StringIO(content.decode()))
        students_data = list(reader)
    else:
        # For PDF/Excel, return message for now
        return {
            "message": "PDF/Excel import stub - implement OCR/pandas parsing",
            "needs_validation": True,
        }

    # Create students
    created_students = []
    for row in students_data:
        student = Student(
            workspace_id=workspace_id,
            classroom_id=classroom_id,
            first_name=row.get("first_name", ""),
            last_name=row.get("last_name", ""),
            display_name=f"{row.get('first_name', '')} {row.get('last_name', '')}",
            student_number=row.get("student_number"),
            email=row.get("email"),
        )
        db.add(student)
        created_students.append(student)

    await db.commit()

    return {
        "message": f"Imported {len(created_students)} students",
        "count": len(created_students),
    }


@router.get("/{classroom_id}/students", response_model=list[StudentResponse])
async def list_students(
    classroom_id: UUID,
    workspace_id: UUID = Depends(get_workspace_id),
    membership: WorkspaceMember = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """List students in a classroom."""
    result = await db.execute(
        select(Student)
        .where(Student.classroom_id == classroom_id)
        .where(Student.workspace_id == workspace_id)
    )
    students = result.scalars().all()

    return [
        StudentResponse(
            id=str(s.id),
            first_name=s.first_name,
            last_name=s.last_name,
            display_name=s.display_name,
            student_number=s.student_number,
            email=s.email,
        )
        for s in students
    ]
