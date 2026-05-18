"""CRUD operations for interview questions stored in CSV."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from utils.question_loader import DEFAULT_CSV, load_questions

COLUMNS = ("id", "category", "difficulty", "question", "keywords")
VALID_DIFFICULTIES = ("Easy", "Medium", "Hard")


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "id" not in out.columns:
        out["id"] = range(1, len(out) + 1)
    out["id"] = out["id"].astype(int)
    for col in ("category", "difficulty", "question", "keywords"):
        if col not in out.columns:
            out[col] = ""
        out[col] = out[col].fillna("").astype(str).str.strip()
    return out[list(COLUMNS)].dropna(subset=["question"]).reset_index(drop=True)


def _save(df: pd.DataFrame, csv_path: Path | None = None) -> pd.DataFrame:
    path = Path(csv_path) if csv_path else DEFAULT_CSV
    normalized = _normalize(df)
    normalized.to_csv(path, index=False)
    return normalized


def _next_id(df: pd.DataFrame) -> int:
    if df.empty or "id" not in df.columns:
        return 1
    return int(df["id"].max()) + 1


def _validate(category: str, difficulty: str, question: str) -> None:
    if not category.strip():
        raise ValueError("Category is required.")
    if not question.strip():
        raise ValueError("Question text is required.")
    if difficulty.strip() not in VALID_DIFFICULTIES:
        raise ValueError(f"Difficulty must be one of: {', '.join(VALID_DIFFICULTIES)}")


def create_question(
    category: str,
    difficulty: str,
    question: str,
    keywords: str = "",
    csv_path: Path | None = None,
) -> pd.Series:
    """Create a new question and persist to CSV."""
    _validate(category, difficulty, question)
    df = _normalize(load_questions(csv_path))
    new_row = pd.Series(
        {
            "id": _next_id(df),
            "category": category.strip(),
            "difficulty": difficulty.strip(),
            "question": question.strip(),
            "keywords": (keywords or "").strip(),
        }
    )
    df = pd.concat([df, new_row.to_frame().T], ignore_index=True)
    _save(df, csv_path)
    return new_row


def get_question(question_id: int, csv_path: Path | None = None) -> pd.Series | None:
    """Read a single question by id."""
    df = _normalize(load_questions(csv_path))
    match = df[df["id"] == int(question_id)]
    if match.empty:
        return None
    return match.iloc[0]


def update_question(
    question_id: int,
    category: str,
    difficulty: str,
    question: str,
    keywords: str = "",
    csv_path: Path | None = None,
) -> pd.Series:
    """Update an existing question by id."""
    _validate(category, difficulty, question)
    df = _normalize(load_questions(csv_path))
    idx = df.index[df["id"] == int(question_id)]
    if len(idx) == 0:
        raise ValueError(f"Question id {question_id} not found.")

    df.loc[idx[0], "category"] = category.strip()
    df.loc[idx[0], "difficulty"] = difficulty.strip()
    df.loc[idx[0], "question"] = question.strip()
    df.loc[idx[0], "keywords"] = (keywords or "").strip()
    _save(df, csv_path)
    return df.loc[idx[0]]


def delete_question(question_id: int, csv_path: Path | None = None) -> bool:
    """Delete a question by id. Returns True if deleted."""
    df = _normalize(load_questions(csv_path))
    before = len(df)
    df = df[df["id"] != int(question_id)].reset_index(drop=True)
    if len(df) == before:
        return False
    _save(df, csv_path)
    return True


def list_questions(csv_path: Path | None = None) -> pd.DataFrame:
    """Read all questions with ids."""
    return _normalize(load_questions(csv_path))
