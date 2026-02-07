"""Fuzzy matching utilities for student name matching."""


from fuzzywuzzy import fuzz, process


def fuzzy_match_student(
    candidate_name: str,
    student_names: list[tuple[str, str]],  # [(student_id, full_name)]
    threshold: int = 80,
) -> tuple[str, str, int] | None:
    """Fuzzy match a candidate name against a list of student names.

    Args:
        candidate_name: Name to match
        student_names: List of (student_id, full_name) tuples
        threshold: Minimum similarity score (0-100)

    Returns:
        (student_id, matched_name, score) or None if no match above threshold
    """
    if not candidate_name or not student_names:
        return None

    # Extract just the names for matching
    names_only = [name for _, name in student_names]

    # Find best match
    best_match = process.extractOne(
        candidate_name, names_only, scorer=fuzz.token_sort_ratio
    )

    if best_match and best_match[1] >= threshold:
        matched_name = best_match[0]
        score = best_match[1]

        # Find the corresponding student_id
        for student_id, full_name in student_names:
            if full_name == matched_name:
                return (student_id, matched_name, score)

    return None


def normalize_name(name: str) -> str:
    """Normalize a name for matching (lowercase, strip whitespace, etc.)."""
    return " ".join(name.lower().strip().split())


def calculate_similarity(name1: str, name2: str) -> int:
    """Calculate similarity score between two names (0-100)."""
    return fuzz.token_sort_ratio(normalize_name(name1), normalize_name(name2))
