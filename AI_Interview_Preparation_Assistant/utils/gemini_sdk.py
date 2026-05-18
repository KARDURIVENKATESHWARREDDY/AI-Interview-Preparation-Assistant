"""Expense insights via Google GenAI SDK (google-genai package)."""

from __future__ import annotations

import os

import pandas as pd

# SDK reads GOOGLE_API_KEY or GEMINI_API_KEY from the environment automatically.
SDK_ENV_VARS = ("GOOGLE_API_KEY", "GEMINI_API_KEY")


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


def get_genai_client():
    """
    Return an initialized google-genai SDK client.
    Credentials via SDK env vars or Streamlit secrets.
    """
    try:
        from google import genai
    except ImportError as e:
        raise ImportError("Install the SDK: pip install -U google-genai") from e

    credentials = _resolve_sdk_credentials()
    if not credentials:
        return None

    return genai.Client(api_key=credentials)


def _expenses_to_text(df: pd.DataFrame) -> str:
    if df.empty:
        return "No expenses recorded."
    lines = []
    for _, row in df.iterrows():
        lines.append(
            f"- {row['expense_date']}: {row['title']} | ${row['amount']:.2f} | "
            f"{row['category']} | {row.get('notes', '')}"
        )
    return "\n".join(lines)


def analyze_expenses_with_sdk(df: pd.DataFrame, username: str) -> tuple[bool, str]:
    """Run spending analysis through the Google GenAI SDK."""
    if not _sdk_configured():
        return False, (
            "Configure the **Google GenAI SDK** to use AI insights.\n\n"
            "1. `pip install -U google-genai`\n"
            "2. Set `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) in your environment or "
            "`.streamlit/secrets.toml`\n\n"
            "Get a key: https://aistudio.google.com/apikey"
        )

    try:
        client = get_genai_client()
    except ImportError as e:
        return False, str(e)

    if client is None:
        return False, "SDK client could not be initialized. Check your credentials."

    summary_lines = []
    if not df.empty:
        total = df["amount"].sum()
        by_cat = df.groupby("category")["amount"].sum()
        summary_lines.append(f"Total: ${total:.2f} across {len(df)} expenses")
        for cat, amt in by_cat.items():
            summary_lines.append(f"  {cat}: ${amt:.2f}")

    prompt = f"""You are a personal finance assistant. Analyze expenses for user "{username}".

Summary:
{chr(10).join(summary_lines) if summary_lines else "No expenses yet."}

Detailed list:
{_expenses_to_text(df)}

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
            return True, text.strip()
        except Exception as e:
            last_error = e
            continue
    return False, f"Gemini SDK error: {last_error}"
