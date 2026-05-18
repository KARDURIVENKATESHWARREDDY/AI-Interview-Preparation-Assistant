"""Expense insights via Google GenAI SDK (Node @google/genai or Python google-genai)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pandas as pd

SDK_ENV_VARS = ("GOOGLE_API_KEY", "GEMINI_API_KEY")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
NODE_SCRIPT = PROJECT_ROOT / "scripts" / "analyze_expenses.mjs"


def _resolve_sdk_credentials() -> str | None:
    """Resolve SDK credentials from environment or Streamlit secrets."""
    for key in SDK_ENV_VARS:
        val = os.environ.get(key)
        if val:
            return val
    try:
        import streamlit as st

        if hasattr(st, "secrets"):
            for key in SDK_ENV_VARS:
                if st.secrets.get(key):
                    return str(st.secrets[key])
    except Exception:
        pass
    return None


def _sdk_configured() -> bool:
    return _resolve_sdk_credentials() is not None


def _df_to_expense_list(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    records = []
    for _, row in df.iterrows():
        records.append(
            {
                "title": str(row["title"]),
                "amount": float(row["amount"]),
                "category": str(row["category"]),
                "expense_date": str(row["expense_date"]),
                "notes": str(row.get("notes", "") or ""),
            }
        )
    return records


def _analyze_with_node_sdk(df: pd.DataFrame, username: str) -> tuple[bool, str] | None:
    """Use @google/genai npm package via Node. Returns None if Node unavailable."""
    if not shutil.which("node"):
        return None
    if not NODE_SCRIPT.exists():
        return None

    credentials = _resolve_sdk_credentials()
    env = os.environ.copy()
    if credentials:
        env["GOOGLE_API_KEY"] = credentials
        env["GEMINI_API_KEY"] = credentials

    payload = json.dumps({"username": username, "expenses": _df_to_expense_list(df)})
    try:
        result = subprocess.run(
            ["node", str(NODE_SCRIPT)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=90,
            cwd=str(PROJECT_ROOT),
            env=env,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None

    if result.returncode != 0 and not result.stdout.strip():
        return None

    try:
        data = json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError:
        return None

    if data.get("ok"):
        model = data.get("model", "")
        prefix = f"_(via @google/genai SDK / {model})_\n\n" if model else ""
        return True, prefix + data.get("text", "")

    if data.get("error"):
        return False, data["error"]
    return None


def get_genai_client():
    """Return Python google-genai client (fallback)."""
    try:
        from google import genai
    except ImportError as e:
        raise ImportError("Install the SDK: pip install -U google-genai") from e

    credentials = _resolve_sdk_credentials()
    if not credentials:
        return None
    return genai.Client(api_key=credentials)


def _analyze_with_python_sdk(df: pd.DataFrame, username: str) -> tuple[bool, str]:
    """Fallback: Python google-genai package."""
    try:
        client = get_genai_client()
    except ImportError as e:
        return False, str(e)

    if client is None:
        return False, "SDK client could not be initialized. Check your credentials."

    lines = [
        f"- {e['expense_date']}: {e['title']} | ${e['amount']:.2f} | {e['category']}"
        for e in _df_to_expense_list(df)
    ]
    total = df["amount"].sum() if not df.empty else 0
    prompt = f"""You are a personal finance assistant. Analyze expenses for user "{username}".

Total: ${total:.2f} across {len(df)} expenses.

Detailed list:
{chr(10).join(lines) if lines else "No expenses yet."}

Provide a concise report with:
1. Top spending categories
2. One savings tip
3. Any unusual patterns
Keep under 200 words. Use bullet points."""

    models = ("gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro")
    last_error: Exception | None = None
    for model in models:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            text = response.text if hasattr(response, "text") and response.text else str(response)
            return True, f"_(via Python google-genai / {model})_\n\n{text.strip()}"
        except Exception as e:
            last_error = e
    return False, f"Gemini SDK error: {last_error}"


def analyze_expenses_with_sdk(df: pd.DataFrame, username: str) -> tuple[bool, str]:
    """Run spending analysis — prefers Node @google/genai, then Python SDK."""
    if not _sdk_configured():
        return False, (
            "Configure the **Google GenAI SDK** to use AI insights.\n\n"
            "1. `npm install` (installs `@google/genai`)\n"
            "2. `pip install -U google-genai` (Python fallback)\n"
            "3. Set `GOOGLE_API_KEY` in environment or `.streamlit/secrets.toml`\n\n"
            "Get a key: https://aistudio.google.com/apikey"
        )

    node_result = _analyze_with_node_sdk(df, username)
    if node_result is not None:
        return node_result

    return _analyze_with_python_sdk(df, username)
