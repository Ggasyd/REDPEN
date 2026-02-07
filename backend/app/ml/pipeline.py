"""Complete submission processing pipeline (3 pillars)."""
from typing import List, Dict
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import (
    Submission,
    SubmissionPage,
    AnswerBlock,
    Question,
    Student,
    StudentAssignment,
    GradeDecision,
)
from app.models.enums import (
    BlockType,
    AssignMethod,
    StudentAssignMethod,
    SubmissionStatus,
)
from app.utils.storage import storage
from app.utils.fuzzy_matching import fuzzy_match_student
from app.ml.ocr_service import ocr_service
from app.ml.vision_service import vision_service
from app.ml.detection_service import detection_service
import io
from PIL import Image


async def process_submission_pipeline(submission: Submission, db: AsyncSession):
    """Complete pipeline for processing a submission.

    Steps:
    1. Split PDF into pages
    2. Extract answer blocks (3 pillars)
    3. OCR/HTR for transcription
    4. Assign questions
    5. Assign student
    6. Generate grade proposal
    7. Flag for review if needed
    """

    # Step 1: Split PDF into pages (stub for MVP)
    pages = await split_pdf_to_pages(submission, db)

    # Step 2-4: Process each page
    for page in pages:
        await process_page(page, submission, db)

    # Step 5: Assign student
    await assign_student_to_submission(submission, db)

    # Step 6: Generate grade proposal
    await generate_grade_proposal(submission, db)

    # Step 7: Determine if needs review
    await flag_for_review_if_needed(submission, db)


async def split_pdf_to_pages(submission: Submission, db: AsyncSession) -> List[SubmissionPage]:
    """Split PDF into individual pages.

    Stub: In production, use PyPDF2 and pdf2image.
    """
    # For MVP, create single page
    page = SubmissionPage(
        submission_id=submission.id,
        page_number=1,
        storage_url=submission.storage_url,  # Mock: use same as submission
        width=1920,
        height=1080,
    )
    db.add(page)
    await db.flush()

    submission.page_count = 1
    return [page]


async def process_page(page: SubmissionPage, submission: Submission, db: AsyncSession):
    """Process a single page using 3-pillar architecture."""
    # Download page image
    try:
        page_bytes = storage.download_file(page.storage_url)
    except:
        # If download fails, skip (development mode without MinIO)
        print(f"Warning: Could not download page {page.id}")
        return

    # Get exam questions
    result = await db.execute(
        select(Question)
        .join(ExamVersion)
        .where(ExamVersion.id == submission.exam_version_id)
        .order_by(Question.order_index)
    )
    questions = result.scalars().all()

    if not questions:
        print("Warning: No questions found for exam version")
        return

    # Pillar 1: Geometric (OCR + horizontal slicing)
    geometric_blocks = await extract_geometric_blocks(page_bytes, questions)

    # Pillar 2: Semantic (Vision model classification)
    semantic_blocks = await extract_semantic_blocks(page_bytes, questions)

    # Pillar 3: Detection (MCQ/Tables)
    detection_blocks = await extract_detection_blocks(page_bytes, questions)

    # Merge and save blocks
    all_blocks = geometric_blocks + semantic_blocks + detection_blocks

    for block_data in all_blocks:
        block = AnswerBlock(
            page_id=page.id,
            question_id=block_data.get("question_id"),
            block_type=block_data.get("block_type", BlockType.TEXT),
            assign_method=block_data.get("assign_method", AssignMethod.GEOMETRIC),
            bbox_x=block_data.get("bbox", [0, 0, 100, 100])[0],
            bbox_y=block_data.get("bbox", [0, 0, 100, 100])[1],
            bbox_width=block_data.get("bbox", [0, 0, 100, 100])[2],
            bbox_height=block_data.get("bbox", [0, 0, 100, 100])[3],
            transcription=block_data.get("transcription"),
            crop_url=block_data.get("crop_url", ""),
            confidence=block_data.get("confidence", 0.0),
            needs_review=block_data.get("confidence", 1.0) < 0.7,
        )
        db.add(block)

    await db.flush()


async def extract_geometric_blocks(page_bytes: bytes, questions: List[Question]) -> List[Dict]:
    """Pillar 1: Geometric extraction using OCR layout analysis."""
    try:
        layout = await ocr_service.extract_layout(page_bytes)
        blocks = []

        for i, block_data in enumerate(layout):
            # Assign to question based on order
            question_id = questions[i].id if i < len(questions) else None

            blocks.append({
                "question_id": question_id,
                "block_type": BlockType.TEXT,
                "assign_method": AssignMethod.GEOMETRIC,
                "bbox": block_data.get("bbox", [0, 0, 100, 100]),
                "transcription": block_data.get("text", ""),
                "crop_url": "mock_crop_url",  # In production, save actual crop
                "confidence": block_data.get("confidence", 0.9),
            })

        return blocks
    except Exception as e:
        print(f"Geometric extraction error: {e}")
        return []


async def extract_semantic_blocks(page_bytes: bytes, questions: List[Question]) -> List[Dict]:
    """Pillar 2: Semantic extraction using vision models."""
    try:
        questions_data = [
            {"id": str(q.id), "number": q.question_number, "text": q.question_text}
            for q in questions
        ]

        classifications = await vision_service.classify_answer_blocks(page_bytes, questions_data)

        blocks = []
        for classification in classifications:
            blocks.append({
                "question_id": UUID(classification["question_id"]) if classification.get("question_id") else None,
                "block_type": BlockType.TEXT,
                "assign_method": AssignMethod.SEMANTIC,
                "bbox": classification.get("bbox", [0, 0, 100, 100]),
                "transcription": "",  # Will be filled by OCR
                "crop_url": "mock_crop_url",
                "confidence": classification.get("confidence", 0.85),
            })

        return blocks
    except Exception as e:
        print(f"Semantic extraction error: {e}")
        return []


async def extract_detection_blocks(page_bytes: bytes, questions: List[Question]) -> List[Dict]:
    """Pillar 3: Detection-based extraction for MCQ/tables."""
    # Filter MCQ questions
    from app.models.enums import QuestionType
    mcq_questions = [q for q in questions if q.question_type == QuestionType.MCQ]

    blocks = []
    for question in mcq_questions:
        # Stub: In production, crop MCQ region and detect
        try:
            result = detection_service.detect_mcq_marks(page_bytes)
            blocks.append({
                "question_id": question.id,
                "block_type": BlockType.MCQ,
                "assign_method": AssignMethod.DETECTION,
                "bbox": [0, 0, 100, 100],
                "transcription": result.get("detected_answer", "UNKNOWN"),
                "crop_url": "mock_crop_url",
                "confidence": result.get("confidence", 0.0),
            })
        except Exception as e:
            print(f"Detection error for question {question.id}: {e}")

    return blocks


async def assign_student_to_submission(submission: Submission, db: AsyncSession):
    """Hierarchical student assignment logic."""
    # If already explicitly assigned, skip
    if submission.student_id:
        assignment = StudentAssignment(
            submission_id=submission.id,
            student_id=submission.student_id,
            assign_method=StudentAssignMethod.EXPLICIT,
            is_validated=True,
        )
        db.add(assignment)
        return

    # Get all students in workspace
    result = await db.execute(
        select(Student).where(Student.workspace_id == submission.workspace_id)
    )
    students = result.scalars().all()

    if not students:
        # No students, use candidate_name
        assignment = StudentAssignment(
            submission_id=submission.id,
            student_id=None,
            assign_method=StudentAssignMethod.MANUAL,
            is_validated=False,
        )
        db.add(assignment)
        return

    # Try OCR name extraction (stub)
    # In production, would call ocr_service.extract_student_name()

    # Try fuzzy matching if candidate_name provided
    if submission.candidate_name:
        student_names = [(str(s.id), f"{s.first_name} {s.last_name}") for s in students]
        match = fuzzy_match_student(submission.candidate_name, student_names, threshold=80)

        if match:
            student_id, matched_name, score = match
            assignment = StudentAssignment(
                submission_id=submission.id,
                student_id=UUID(student_id),
                assign_method=StudentAssignMethod.OCR_AUTO,
                ocr_candidate_name=submission.candidate_name,
                confidence=score / 100.0,
                is_validated=score >= 90,
            )
            db.add(assignment)
            submission.student_id = UUID(student_id)
            return

    # No match, needs manual review
    assignment = StudentAssignment(
        submission_id=submission.id,
        student_id=None,
        assign_method=StudentAssignMethod.MANUAL,
        is_validated=False,
    )
    db.add(assignment)
    submission.status = SubmissionStatus.NEEDS_REVIEW


async def generate_grade_proposal(submission: Submission, db: AsyncSession):
    """Generate AI-assisted grade proposal (stub for MVP)."""
    # Stub: Calculate total score based on answer blocks
    grade_decision = GradeDecision(
        submission_id=submission.id,
        total_score=0.0,
        max_score=100.0,
        final_score=0.0,
        ai_suggested_score=0.0,
    )
    db.add(grade_decision)


async def flag_for_review_if_needed(submission: Submission, db: AsyncSession):
    """Flag submission for review if confidence is low."""
    # Check if any answer blocks need review
    result = await db.execute(
        select(AnswerBlock)
        .join(SubmissionPage)
        .where(SubmissionPage.submission_id == submission.id)
        .where(AnswerBlock.needs_review == True)
    )
    blocks_needing_review = result.scalars().all()

    if blocks_needing_review or submission.status == SubmissionStatus.NEEDS_REVIEW:
        submission.status = SubmissionStatus.NEEDS_REVIEW
    else:
        submission.status = SubmissionStatus.PROCESSED


# Import missing models
from app.models import ExamVersion
