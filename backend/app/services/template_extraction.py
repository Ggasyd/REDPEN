"""Template zone extraction utilities based on PyMuPDF."""

import re

QUESTION_PATTERN = re.compile(
    r"^\s*(?:question|q)?\s*([0-9]+[a-zA-Z]?)\b", re.IGNORECASE
)


def extract_template_zones_from_pdf(
    pdf_bytes: bytes,
    pad_ratio: float = 0.10,
) -> tuple[int, list[dict]]:
    """Extract candidate question zones from a template PDF.

    Returns:
        tuple: (page_count, zones)
    """
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - env dependent
        raise RuntimeError("PyMuPDF is required for template extraction") from exc

    zones: list[dict] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        page_count = len(document)
        for page_index, page in enumerate(document):
            for block in page.get_text("blocks"):
                if len(block) < 5:
                    continue

                x0, y0, x1, y1, text = block[:5]
                cleaned_text = (text or "").strip()
                if not cleaned_text:
                    continue

                match = QUESTION_PATTERN.match(cleaned_text)
                if not match:
                    continue

                question_number = match.group(1)
                bbox_x = max(0, int(x0))
                bbox_y = max(0, int(y0))
                bbox_width = max(1, int(x1 - x0))
                bbox_height = max(1, int(y1 - y0))

                zones.append(
                    {
                        "page_index": page_index,
                        "question_key": f"Q{question_number}",
                        "bbox_x": bbox_x,
                        "bbox_y": bbox_y,
                        "bbox_width": bbox_width,
                        "bbox_height": bbox_height,
                        "pad_ratio": pad_ratio,
                        "confidence": 0.75,
                        "source": "auto_pymupdf",
                    }
                )

    return page_count, zones
