"""Seed database with demo data."""

import asyncio

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import (
    Classroom,
    Exam,
    ExamVersion,
    Question,
    Student,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceSettings,
)
from app.models.enums import (
    QuestionType,
    WorkspaceRole,
    WorkspaceType,
)
from app.utils.security import hash_password


async def seed_database():
    """Seed database with demo data."""
    print("🌱 Seeding database...")

    async with AsyncSessionLocal() as db:
        # Check if already seeded
        result = await db.execute(select(User).where(User.email == "prof@redpen.fr"))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print("✅ Database already seeded. Skipping...")
            return

        # Create demo user
        user = User(
            email="prof@redpen.fr",
            hashed_password=hash_password("password123"),
            full_name="Professeur Demo",
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.flush()

        # Create personal workspace
        personal_workspace = Workspace(
            name="Espace Personnel - Prof Demo",
            workspace_type=WorkspaceType.PERSONAL,
            is_active=True,
        )
        db.add(personal_workspace)
        await db.flush()

        # Create school workspace
        school_workspace = Workspace(
            name="Lycée Victor Hugo",
            workspace_type=WorkspaceType.SCHOOL,
            is_active=True,
        )
        db.add(school_workspace)
        await db.flush()

        # Add user as owner of both workspaces
        membership1 = WorkspaceMember(
            workspace_id=personal_workspace.id,
            user_id=user.id,
            role=WorkspaceRole.OWNER,
        )
        membership2 = WorkspaceMember(
            workspace_id=school_workspace.id,
            user_id=user.id,
            role=WorkspaceRole.OWNER,
        )
        db.add(membership1)
        db.add(membership2)

        # Create settings for both workspaces
        settings1 = WorkspaceSettings(
            workspace_id=personal_workspace.id,
            retention_submissions_days=settings.default_retention_submissions_days,
            retention_artifacts_days=settings.default_retention_artifacts_days,
            retention_ml_days=settings.default_retention_ml_days,
        )
        settings2 = WorkspaceSettings(
            workspace_id=school_workspace.id,
            retention_submissions_days=settings.default_retention_submissions_days,
            retention_artifacts_days=settings.default_retention_artifacts_days,
            retention_ml_days=settings.default_retention_ml_days,
        )
        db.add(settings1)
        db.add(settings2)

        # Create classroom in school workspace
        classroom = Classroom(
            workspace_id=school_workspace.id,
            name="Terminale S1",
            description="Classe de Terminale S - Section 1",
            grade_level="Terminale",
            academic_year="2024-2025",
        )
        db.add(classroom)
        await db.flush()

        # Create demo students
        students_data = [
            {"first_name": "Sophie", "last_name": "Martin", "student_number": "TS001"},
            {"first_name": "Thomas", "last_name": "Bernard", "student_number": "TS002"},
            {"first_name": "Emma", "last_name": "Dubois", "student_number": "TS003"},
            {"first_name": "Lucas", "last_name": "Durand", "student_number": "TS004"},
            {"first_name": "Léa", "last_name": "Petit", "student_number": "TS005"},
        ]

        for student_data in students_data:
            student = Student(
                workspace_id=school_workspace.id,
                classroom_id=classroom.id,
                first_name=student_data["first_name"],
                last_name=student_data["last_name"],
                display_name=f"{student_data['first_name']} {student_data['last_name']}",
                student_number=student_data["student_number"],
                email=f"{student_data['first_name'].lower()}.{student_data['last_name'].lower()}@lycee-hugo.fr",
            )
            db.add(student)

        # Create demo exam
        exam = Exam(
            workspace_id=school_workspace.id,
            title="Contrôle de Mathématiques - Analyse",
            description="Évaluation sur les fonctions et dérivées",
            subject="Mathématiques",
            grade_level="Terminale",
            total_points=20.0,
        )
        db.add(exam)
        await db.flush()

        # Create exam version
        exam_version = ExamVersion(
            exam_id=exam.id,
            version_number=1,
            is_active=True,
            notes="Version initiale",
        )
        db.add(exam_version)
        await db.flush()

        # Create demo questions
        questions_data = [
            {
                "number": "1",
                "text": "Calculer la dérivée de la fonction f(x) = x² + 3x - 2",
                "type": QuestionType.OPEN,
                "points": 4.0,
                "order": 1,
            },
            {
                "number": "2",
                "text": "Étudier le signe de la fonction g(x) = -2x + 6",
                "type": QuestionType.OPEN,
                "points": 6.0,
                "order": 2,
            },
            {
                "number": "3",
                "text": "Quelle est la limite de (1/x) quand x tend vers 0+ ?",
                "type": QuestionType.MCQ,
                "points": 3.0,
                "order": 3,
            },
            {
                "number": "4",
                "text": "Résoudre l'équation : x² - 5x + 6 = 0",
                "type": QuestionType.OPEN,
                "points": 7.0,
                "order": 4,
            },
        ]

        for q_data in questions_data:
            question = Question(
                exam_version_id=exam_version.id,
                question_number=q_data["number"],
                question_text=q_data["text"],
                question_type=q_data["type"],
                max_points=q_data["points"],
                order_index=q_data["order"],
            )
            db.add(question)

        await db.commit()

        print("✅ Database seeded successfully!")
        print("\n📊 Demo Data Created:")
        print("   - User: prof@redpen.fr (password: password123)")
        print("   - Workspaces: 2 (Personal + School)")
        print("   - Classroom: Terminale S1")
        print(f"   - Students: {len(students_data)}")
        print("   - Exam: Contrôle de Mathématiques - Analyse")
        print(f"   - Questions: {len(questions_data)}")


if __name__ == "__main__":
    asyncio.run(seed_database())
