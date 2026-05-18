"""CRUD operations for user expenses stored in CSV."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

EXPENSES_CSV = Path(__file__).resolve().parent.parent / "data" / "expenses.csv"
COLUMNS = ("id", "username", "title", "amount", "category", "expense_date", "notes")
EXPENSE_CATEGORIES = (
    "Food",
    "Transport",
    "Shopping",
    "Bills",
    "Entertainment",
    "Health",
    "Education",
    "Other",
)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return pd.DataFrame(columns=list(COLUMNS))
    if "id" not in out.columns:
        out["id"] = range(1, len(out) + 1)
    out["id"] = pd.to_numeric(out["id"], errors="coerce").fillna(0).astype(int)
    for col in COLUMNS:
        if col not in out.columns:
            out[col] = ""
    out["username"] = out["username"].fillna("").astype(str).str.strip().str.lower()
    out["title"] = out["title"].fillna("").astype(str).str.strip()
    out["category"] = out["category"].fillna("Other").astype(str).str.strip()
    out["notes"] = out["notes"].fillna("").astype(str).str.strip()
    out["amount"] = pd.to_numeric(out["amount"], errors="coerce").fillna(0.0)
    out["expense_date"] = out["expense_date"].fillna("").astype(str).str.strip()
    return out[list(COLUMNS)].reset_index(drop=True)


def _load(csv_path: Path | None = None) -> pd.DataFrame:
    path = Path(csv_path) if csv_path else EXPENSES_CSV
    if not path.exists():
        return _normalize(pd.DataFrame(columns=list(COLUMNS)))
    return _normalize(pd.read_csv(path))


def _save(df: pd.DataFrame, csv_path: Path | None = None) -> pd.DataFrame:
    path = Path(csv_path) if csv_path else EXPENSES_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _normalize(df)
    normalized.to_csv(path, index=False)
    return normalized


def _next_id(df: pd.DataFrame) -> int:
    if df.empty:
        return 1
    return int(df["id"].max()) + 1


def _validate(title: str, amount: float, category: str) -> None:
    if not title.strip():
        raise ValueError("Title is required.")
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    if category.strip() not in EXPENSE_CATEGORIES:
        raise ValueError(f"Category must be one of: {', '.join(EXPENSE_CATEGORIES)}")


def list_expenses(
    username: str,
    category: str | None = None,
    csv_path: Path | None = None,
) -> pd.DataFrame:
    """Read all expenses for a user."""
    df = _load(csv_path)
    user = (username or "").strip().lower()
    out = df[df["username"] == user].copy()
    if category and category != "All":
        out = out[out["category"] == category]
    return out.sort_values("expense_date", ascending=False).reset_index(drop=True)


def get_expense(expense_id: int, username: str, csv_path: Path | None = None) -> pd.Series | None:
    """Read one expense by id (scoped to user)."""
    df = list_expenses(username, csv_path=csv_path)
    match = df[df["id"] == int(expense_id)]
    if match.empty:
        return None
    return match.iloc[0]


def create_expense(
    username: str,
    title: str,
    amount: float,
    category: str,
    expense_date: str | None = None,
    notes: str = "",
    csv_path: Path | None = None,
) -> pd.Series:
    """Create a new expense."""
    _validate(title, float(amount), category)
    df = _load(csv_path)
    user = username.strip().lower()
    new_row = pd.Series(
        {
            "id": _next_id(df),
            "username": user,
            "title": title.strip(),
            "amount": round(float(amount), 2),
            "category": category.strip(),
            "expense_date": (expense_date or str(date.today())).strip(),
            "notes": (notes or "").strip(),
        }
    )
    df = pd.concat([df, new_row.to_frame().T], ignore_index=True)
    _save(df, csv_path)
    return new_row


def update_expense(
    expense_id: int,
    username: str,
    title: str,
    amount: float,
    category: str,
    expense_date: str,
    notes: str = "",
    csv_path: Path | None = None,
) -> pd.Series:
    """Update an existing expense."""
    _validate(title, float(amount), category)
    df = _load(csv_path)
    user = username.strip().lower()
    idx = df.index[(df["id"] == int(expense_id)) & (df["username"] == user)]
    if len(idx) == 0:
        raise ValueError(f"Expense id {expense_id} not found.")

    df.loc[idx[0], "title"] = title.strip()
    df.loc[idx[0], "amount"] = round(float(amount), 2)
    df.loc[idx[0], "category"] = category.strip()
    df.loc[idx[0], "expense_date"] = expense_date.strip()
    df.loc[idx[0], "notes"] = (notes or "").strip()
    _save(df, csv_path)
    return df.loc[idx[0]]


def delete_expense(expense_id: int, username: str, csv_path: Path | None = None) -> bool:
    """Delete an expense by id."""
    df = _load(csv_path)
    user = username.strip().lower()
    before = len(df)
    df = df[~((df["id"] == int(expense_id)) & (df["username"] == user))].reset_index(drop=True)
    if len(df) == before:
        return False
    _save(df, csv_path)
    return True


def expense_summary(username: str, csv_path: Path | None = None) -> dict:
    """Totals by category for dashboard."""
    df = list_expenses(username, csv_path=csv_path)
    if df.empty:
        return {"total": 0.0, "count": 0, "by_category": {}}
    by_cat = df.groupby("category")["amount"].sum().round(2).to_dict()
    return {
        "total": round(float(df["amount"].sum()), 2),
        "count": len(df),
        "by_category": by_cat,
    }
