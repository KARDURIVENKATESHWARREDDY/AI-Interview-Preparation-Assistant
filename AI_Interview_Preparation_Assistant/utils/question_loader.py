from pathlib import Path

import pandas as pd

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "data" / "questions.csv"


def load_questions(csv_path: str | Path | None = None) -> pd.DataFrame:
    path = Path(csv_path) if csv_path else DEFAULT_CSV
    if not path.exists():
        raise FileNotFoundError(f"Questions file not found: {path}")

    df = pd.read_csv(path)
    required = {"category", "difficulty", "question"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing columns: {missing}")

    df["category"] = df["category"].astype(str).str.strip()
    df["difficulty"] = df["difficulty"].astype(str).str.strip()
    df["question"] = df["question"].astype(str).str.strip()
    if "keywords" not in df.columns:
        df["keywords"] = ""
    else:
        df["keywords"] = df["keywords"].fillna("").astype(str).str.strip()
    return df.dropna(subset=["question"]).reset_index(drop=True)


def filter_questions(
    df: pd.DataFrame,
    category: str | None = None,
    difficulty: str | None = None,
) -> pd.DataFrame:
    out = df.copy()
    if category and category != "All":
        out = out[out["category"] == category]
    if difficulty and difficulty != "All":
        out = out[out["difficulty"] == difficulty]
    return out.reset_index(drop=True)
