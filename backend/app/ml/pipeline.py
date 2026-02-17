"""Complete submission processing pipeline (legacy + template-first V2)."""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.alignment_service import alignment_service
from app.ml.detection_service import detection_service
from app.ml.ocr_service import ocr_service
from app.ml.vision_service import vision_service
from app.models import (
    AnswerBlock,
    ExamTemplate,
    ExamVersion,
    GradeDecision,
    Question,
    Student,
    StudentAssignment,
    Submission,
    SubmissionPage,
    TemplateZone,
)
from app.models.enums import (
    AssignMethod,
    BlockType,
    StudentAssignMethod,
    SubmissionStatus,
)
from app.utils.fuzzy_matching import fuzzy_match_student
from app.utils.storage import storage

logger = logging.getLogger(__name__)


async def process_submission_pipeline(submission: Submission, db: AsyncSession):
    """Process submission using V2 (feature-flagged) or legacy flow."""
    if settings.pipeline_v2_enabled:
        await process_submission_pipeline_v2(submission, db)
        return

    await process_submission_pipeline_v1(submission, db)


async def process_submission_pipeline_v2(submission: Submission, db: AsyncSession):
    """Template-first pipeline: template -> alignment -> zones -> OCR by zone."""
    pages = await split_pdf_to_pages(submission, db)

    # Load active template (if configured)
    template_bytes = None
    result = await db.execute(
        select(ExamVersion).where(ExamVersion.id == submission.exam_version_id)
    )
    exam_version = result.scalar_one_or_none()
    if exam_version and exam_version.active_template_id:
        from app.models import ExamTemplate

        template_result = await db.execute(
            select(ExamTemplate).where(
                ExamTemplate.id == exam_version.active_template_id
            )
        )
        template = template_result.scalar_one_or_none()
        if template:
            try:
                template_bytes = storage.download_file(template.storage_url)
            except Exception as e:
                print(f"Warning: Could not download template {template.id}: {e}")

    # Step 2-4: Process each page
    alignment_scores: list[float] = []
    for page in pages:
        page_alignment = await align_submission_page(page, submission, template_bytes)
        if page_alignment is not None:
            alignment_scores.append(page_alignment.score)
        await process_page(page, submission, db)

    if alignment_scores:
        best_alignment = max(alignment_scores)
        submission.alignment_score = best_alignment

    # Step 5: Assign student
    await assign_student_to_submission(submission, db)

    if total_zones > 0 and successful_alignments == 0:
        submission.status = SubmissionStatus.ERROR
    elif alignment_average >= 0.75 and coverage_ratio >= 0.7 and blank_ratio <= 0.6:
        submission.status = SubmissionStatus.PROCESSED
    else:
        submission.status = SubmissionStatus.NEEDS_REVIEW

    logger.info(
        {
            "event": "pipeline_v2_status_decision",
            "submission_id": str(submission.id),
            "alignment_average": round(alignment_average, 4),
            "coverage_ratio": round(coverage_ratio, 4),
            "blank_ratio": round(blank_ratio, 4),
            "total_zones": total_zones,
            "processed_zones": processed_zones,
            "successful_alignments": successful_alignments,
            "failed_alignments": failed_alignments,
            "status": submission.status.value,
        }
    )

    await db.flush()

    await assign_student_to_submission(submission, db)
    await generate_grade_proposal(submission, db)


async def process_submission_pipeline_v1(submission: Submission, db: AsyncSession):
    """Legacy 3-pillar pipeline kept for rollback via feature flag."""
    pages = await split_pdf_to_pages(submission, db)

    template_bytes = None
    result = await db.execute(
        select(ExamVersion).where(ExamVersion.id == submission.exam_version_id)
    )
    exam_version = result.scalar_one_or_none()
    if exam_version and exam_version.active_template_id:
        template_result = await db.execute(
            select(ExamTemplate).where(
                ExamTemplate.id == exam_version.active_template_id
            )
        )
        template = template_result.scalar_one_or_none()
        if template:
            try:
                template_bytes = storage.download_file(template.storage_url)
            except Exception as e:
                logger.warning(
                    {
                        "event": "alignment_template_download_failed",
                        "submission_id": str(submission.id),
                        "template_id": str(template.id),
                        "error": str(e),
                    }
                )

    alignment_scores: list[float] = []
    for page in pages:
        page_alignment = await align_submission_page(page, submission, template_bytes)
        if page_alignment is not None:
            alignment_scores.append(page_alignment.score)
        await process_page(page, submission, db)

    if alignment_scores:
        submission.alignment_score = max(alignment_scores)

    await assign_student_to_submission(submission, db)
    await generate_grade_proposal(submission, db)
    await flag_for_review_if_needed(submission, db)


async def _load_template_context(
    submission: Submission, db: AsyncSession
) -> dict | None:
    result = await db.execute(
        select(ExamVersion).where(ExamVersion.id == submission.exam_version_id)
    )
    exam_version = result.scalar_one_or_none()
    if not exam_version or not exam_version.active_template_id:
        return None

    template_result = await db.execute(
        select(ExamTemplate).where(ExamTemplate.id == exam_version.active_template_id)
    )
    template = template_result.scalar_one_or_none()
    if not template:
        return None

    try:
        template_bytes = storage.download_file(template.storage_url)
    except Exception as exc:
        logger.warning(
            {
                "event": "pipeline_v2_template_download_failed",
                "submission_id": str(submission.id),
                "template_id": str(template.id),
                "error": str(exc),
            }
        )
        return None

    template_pages = _render_template_pages(template_bytes)

    zones_result = await db.execute(
        select(TemplateZone)
        .where(TemplateZone.template_id == template.id)
        .order_by(TemplateZone.page_index, TemplateZone.question_key)
    )
    zones_by_page: dict[int, list[TemplateZone]] = defaultdict(list)
    for zone in zones_result.scalars().all():
        zones_by_page[zone.page_index].append(zone)

    return {
        "template": template,
        "template_pages": template_pages,
        "zones_by_page": zones_by_page,
    }


def _render_template_pages(template_bytes: bytes) -> dict[int, bytes]:
    """Render template PDF pages to image bytes for alignment."""
    try:
        import fitz

        rendered: dict[int, bytes] = {}
        with fitz.open(stream=template_bytes, filetype="pdf") as document:
            for index, page in enumerate(document):
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                rendered[index] = pixmap.tobytes("png")
        return rendered
    except Exception:
        return {0: template_bytes}


def _normalize_question_key(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().upper()
    if normalized.startswith("Q"):
        return normalized
    return f"Q{normalized}"


async def split_pdf_to_pages(
    submission: Submission, db: AsyncSession
) -> list[SubmissionPage]:
    """Split PDF into individual pages.

    Stub: In production, use PyPDF2 and pdf2image.
    """
    page = SubmissionPage(
        submission_id=submission.id,
        page_number=1,
        storage_url=submission.storage_url,
        width=1920,
        height=1080,
    )
    db.add(page)
    await db.flush()

    submission.page_count = 1
    return [page]


async def align_submission_page(
    page: SubmissionPage,
    submission: Submission,
    template_bytes: bytes | None,
):
    """Align submission page against active template and persist alignment metadata."""
    if not template_bytes:
        submission.alignment_method = "none"
        submission.alignment_rotation = 0
        if submission.alignment_score is None:
            submission.alignment_score = 0.0
        return None

    try:
        page_bytes = storage.download_file(page.storage_url)
    except Exception as e:
        print(f"Warning: Could not download page {page.id} for alignment: {e}")
        submission.alignment_method = "none"
        submission.alignment_rotation = 0
        submission.alignment_score = 0.0
        return None

    result = alignment_service.align_to_template(
        submission_page_bytes=page_bytes,
        template_page_bytes=template_bytes,
    )

    submission.alignment_score = result.score
    submission.alignment_method = result.method
    submission.alignment_rotation = result.rotation

    return result


async def process_page(page: SubmissionPage, submission: Submission, db: AsyncSession):
    """Process a single page using 3-pillar architecture."""
    try:
        page_bytes = storage.download_file(page.storage_url)
    except Exception as e:
        print(f"Warning: Could not download page {page.id}: {e}")
        return

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

    geometric_blocks = await extract_geometric_blocks(page_bytes, questions)
    semantic_blocks = await extract_semantic_blocks(page_bytes, questions)
    detection_blocks = await extract_detection_blocks(page_bytes, questions)

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


async def extract_geometric_blocks(
    page_bytes: bytes, questions: list[Question]
) -> list[dict]:
    """Pillar 1: Geometric extraction using OCR layout analysis."""
    try:
        layout = await ocr_service.extract_layout(page_bytes)
        blocks = []

        for i, block_data in enumerate(layout):
            # Assign to question based on order
            question_id = questions[i].id if i < len(questions) else None

            blocks.append(
                {
                    "question_id": question_id,
                    "block_type": BlockType.TEXT,
                    "assign_method": AssignMethod.GEOMETRIC,
                    "bbox": block_data.get("bbox", [0, 0, 100, 100]),
                    "transcription": block_data.get("text", ""),
                    "crop_url": "mock_crop_url",  # In production, save actual crop
                    "confidence": block_data.get("confidence", 0.9),
                }
            )

        return blocks
    except Exception as e:
        print(f"Geometric extraction error: {e}")
        return []


async def extract_semantic_blocks(
    page_bytes: bytes, questions: list[Question]
) -> list[dict]:
    """Pillar 2: Semantic extraction using vision models."""
    try:
        questions_data = [
            {"id": str(q.id), "number": q.question_number, "text": q.question_text}
            for q in questions
        ]

        classifications = await vision_service.classify_answer_blocks(
            page_bytes, questions_data
        )

        blocks = []
        for classification in classifications:
            blocks.append(
                {
                    "question_id": (
                        UUID(classification["question_id"])
                        if classification.get("question_id")
                        else None
                    ),
                    "block_type": BlockType.TEXT,
                    "assign_method": AssignMethod.SEMANTIC,
                    "bbox": classification.get("bbox", [0, 0, 100, 100]),
                    "transcription": "",  # Will be filled by OCR
                    "crop_url": "mock_crop_url",
                    "confidence": classification.get("confidence", 0.85),
                }
            )

        return blocks
    except Exception as e:
        print(f"Semantic extraction error: {e}")
        return []


async def extract_detection_blocks(
    page_bytes: bytes, questions: list[Question]
) -> list[dict]:
    """Pillar 3: Detection-based extraction for MCQ/tables."""
    # Filter MCQ questions
    from app.models.enums import QuestionType

    mcq_questions = [q for q in questions if q.question_type == QuestionType.MCQ]

    blocks = []
    for question in mcq_questions:
        # Stub: In production, crop MCQ region and detect
        try:
            result = detection_service.detect_mcq_marks(page_bytes)
            blocks.append(
                {
                    "question_id": question.id,
                    "block_type": BlockType.MCQ,
                    "assign_method": AssignMethod.DETECTION,
                    "bbox": [0, 0, 100, 100],
                    "transcription": result.get("detected_answer", "UNKNOWN"),
                    "crop_url": "mock_crop_url",
                    "confidence": result.get("confidence", 0.0),
                }
            )
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
        match = fuzzy_match_student(
            submission.candidate_name, student_names, threshold=80
        )

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
        .where(AnswerBlock.needs_review)
    )
    blocks_needing_review = result.scalars().all()

    if blocks_needing_review or submission.status == SubmissionStatus.NEEDS_REVIEW:
        submission.status = SubmissionStatus.NEEDS_REVIEW
    else:
        submission.status = SubmissionStatus.PROCESSED
