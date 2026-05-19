from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / ".env")

from utils.auth import authenticate, ensure_default_users, register_user
from utils.evaluator import evaluate_answer
from utils.expense_crud import (
    EXPENSE_CATEGORIES,
    create_expense,
    delete_expense,
    expense_summary,
    list_expenses,
    update_expense,
)
from utils.gemini_sdk import analyze_expenses_with_sdk
from utils.question_crud import (
    VALID_DIFFICULTIES,
    create_question,
    delete_question,
    list_questions,
    update_question,
)
from utils.question_loader import filter_questions, load_questions

ASSETS = Path(__file__).parent / "assets" / "style.css"
CATEGORIES = ("Behavioral", "Technical", "HR")


def load_css() -> None:
    if ASSETS.exists():
        st.markdown(f"<style>{ASSETS.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def score_class(score: int) -> str:
    if score >= 75:
        return "score-high"
    if score >= 50:
        return "score-mid"
    return "score-low"


def init_session() -> None:
    defaults = {
        "authenticated": False,
        "username": None,
        "current_question": None,
        "current_meta": None,
        "last_result": None,
        "answer_draft": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def pick_question(df, category: str, difficulty: str) -> None:
    filtered = filter_questions(df, category, difficulty)
    if filtered.empty:
        st.warning("No questions match your filters. Try broader options.")
        return
    row = filtered.sample(n=1).iloc[0]
    st.session_state.current_question = row["question"]
    st.session_state.current_meta = {
        "category": row["category"],
        "difficulty": row["difficulty"],
        "keywords": row.get("keywords", "") or "",
        "id": int(row["id"]),
    }
    st.session_state.last_result = None
    st.session_state.answer_draft = ""


def render_user_sidebar() -> None:
    st.sidebar.divider()
    st.sidebar.caption(f"Signed in as **{st.session_state.username}**")
    if st.sidebar.button("Sign out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.current_question = None
        st.session_state.last_result = None
        st.rerun()


def render_login_page() -> None:
    ensure_default_users()
    st.markdown(
        """
        <div class="app-header">
            <h1>🎯 AI Interview Preparation Assistant</h1>
            <p>Sign in to access interview practice and question management.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        st.markdown(
            """
            <div class="auth-wrapper">
                <h2>Welcome back</h2>
                <p class="auth-subtitle">Enter your username and password to continue</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        tab_signin, tab_register = st.tabs(["Sign in", "Register"])

        with tab_signin:
            with st.form("signin_form"):
                username = st.text_input("Username", placeholder="e.g. demo")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
                if submitted:
                    if authenticate(username, password):
                        st.session_state.authenticated = True
                        st.session_state.username = username.strip().lower()
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

        with tab_register:
            with st.form("register_form"):
                new_user = st.text_input("Choose username", placeholder="min 3 characters")
                new_pass = st.text_input("Choose password", type="password", placeholder="min 6 characters")
                confirm = st.text_input("Confirm password", type="password")
                reg_submit = st.form_submit_button("Create account", use_container_width=True)
                if reg_submit:
                    if new_pass != confirm:
                        st.error("Passwords do not match.")
                    else:
                        ok, msg = register_user(new_user, new_pass)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)

        st.markdown(
            '<p class="auth-hint">Demo accounts: demo / demo123 · admin / admin123</p>',
            unsafe_allow_html=True,
        )


def render_practice_tab(questions_df, category: str, difficulty: str) -> None:
    with st.sidebar:
        st.header("Session settings")
        st.caption(f"**{len(questions_df)}** questions in bank")
        filtered_count = len(filter_questions(questions_df, category, difficulty))
        st.caption(f"**{filtered_count}** match current filters")

        if st.button("🎲 New question", type="primary", use_container_width=True):
            pick_question(questions_df, category, difficulty)
            st.rerun()
        render_user_sidebar()

    if st.session_state.current_question is None:
        pick_question(questions_df, category, difficulty)

    meta = st.session_state.current_meta or {}
    st.markdown(
        f"""
        <div class="question-card">
            <div class="label">{meta.get("category", "")} · {meta.get("difficulty", "")}</div>
            <div class="text">{st.session_state.current_question}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Next question", use_container_width=True):
            pick_question(questions_df, category, difficulty)
            st.rerun()
    with col2:
        if st.button("Random from filters", use_container_width=True):
            pick_question(questions_df, category, difficulty)
            st.rerun()

    answer = st.text_area(
        "Your answer",
        value=st.session_state.answer_draft,
        height=220,
        placeholder="Type your answer here. Use specific examples and a clear structure…",
    )
    st.session_state.answer_draft = answer

    if st.button("Submit for feedback", type="primary", use_container_width=True):
        if not answer.strip():
            st.warning("Please write an answer before submitting.")
        else:
            meta = st.session_state.current_meta or {}
            with st.spinner("Running NLP analysis…"):
                result = evaluate_answer(
                    st.session_state.current_question,
                    answer,
                    keywords=meta.get("keywords", ""),
                    category=meta.get("category", ""),
                )
            st.session_state.last_result = result

    if st.session_state.last_result:
        r = st.session_state.last_result
        st.divider()
        st.subheader("Feedback")
        st.markdown(
            f'<p class="{score_class(r.score)}">Score: {r.score}/100</p>',
            unsafe_allow_html=True,
        )

        for msg in r.feedback:
            st.info(msg)

        if r.strengths:
            st.markdown(
                '<div class="feedback-box"><h4>✅ Strengths</h4><ul>'
                + "".join(f"<li>{s}</li>" for s in r.strengths)
                + "</ul></div>",
                unsafe_allow_html=True,
            )
        if r.improvements:
            st.markdown(
                '<div class="feedback-box"><h4>💡 Areas to improve</h4><ul>'
                + "".join(f"<li>{i}</li>" for i in r.improvements)
                + "</ul></div>",
                unsafe_allow_html=True,
            )

        if r.nlp_metrics:
            with st.expander("NLP analysis details", expanded=False):
                m = r.nlp_metrics
                c1, c2, c3 = st.columns(3)
                c1.metric("Relevance", f"{m.get('relevance', 0)}%")
                c2.metric("Keyword coverage", f"{m.get('keyword_coverage', 0)}%")
                c3.metric("Lexical diversity", f"{m.get('lexical_diversity', 0)}%")
                c4, c5, c6 = st.columns(3)
                c4.metric("Sentiment", m.get("sentiment", "—"))
                c5.metric("Flesch readability", m.get("flesch_reading_ease", "—"))
                c6.metric("Word count", m.get("word_count", 0))
                st.caption(
                    f"Polarity: {m.get('polarity')} · Subjectivity: {m.get('subjectivity')} · "
                    f"Grade level: {m.get('grade_level')} · Numbers mentioned: {m.get('numbers', 0)}"
                )


def _question_form_defaults(row=None) -> dict:
    if row is None:
        return {
            "category": CATEGORIES[0],
            "difficulty": VALID_DIFFICULTIES[0],
            "question": "",
            "keywords": "",
        }
    return {
        "category": row["category"],
        "difficulty": row["difficulty"],
        "question": row["question"],
        "keywords": row.get("keywords", ""),
    }


def render_crud_tab() -> None:
    with st.sidebar:
        render_user_sidebar()
    st.subheader("Manage questions")
    st.caption("Create, read, update, and delete interview questions in the database.")

    df = list_questions()
    crud_tabs = st.tabs(["📋 Read", "➕ Create", "✏️ Update", "🗑️ Delete"])

    with crud_tabs[0]:
        st.markdown("### All questions")
        f1, f2 = st.columns(2)
        with f1:
            cat_filter = st.selectbox("Filter category", ["All"] + sorted(df["category"].unique()), key="crud_cat")
        with f2:
            diff_filter = st.selectbox("Filter difficulty", ["All"] + list(VALID_DIFFICULTIES), key="crud_diff")
        view = filter_questions(df, cat_filter, diff_filter)
        st.dataframe(
            view[["id", "category", "difficulty", "question", "keywords"]],
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"Showing {len(view)} of {len(df)} questions")

    with crud_tabs[1]:
        st.markdown("### Add new question")
        defaults = _question_form_defaults()
        with st.form("create_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            category = c1.selectbox("Category", CATEGORIES, key="create_cat")
            difficulty = c2.selectbox("Difficulty", VALID_DIFFICULTIES, key="create_diff")
            question = st.text_area("Question", height=100, key="create_q")
            keywords = st.text_input(
                "Keywords (comma-separated, for NLP scoring)",
                key="create_kw",
                placeholder="e.g. project,impact,team",
            )
            if st.form_submit_button("Create question", type="primary"):
                try:
                    row = create_question(category, difficulty, question, keywords)
                    st.success(f"Created question #{int(row['id'])}.")
                    st.session_state.current_question = None
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    with crud_tabs[2]:
        st.markdown("### Edit question")
        if df.empty:
            st.info("No questions to edit.")
        else:
            options = {
                f"#{int(r['id'])} — {r['question'][:60]}…"
                if len(r["question"]) > 60
                else f"#{int(r['id'])} — {r['question']}": int(r["id"])
                for _, r in df.iterrows()
            }
            selected_label = st.selectbox("Select question", list(options.keys()), key="edit_select")
            row = df[df["id"] == options[selected_label]].iloc[0]
            with st.form("update_form"):
                c1, c2 = st.columns(2)
                cat_idx = list(CATEGORIES).index(row["category"]) if row["category"] in CATEGORIES else 0
                diff_idx = (
                    list(VALID_DIFFICULTIES).index(row["difficulty"])
                    if row["difficulty"] in VALID_DIFFICULTIES
                    else 0
                )
                category = c1.selectbox("Category", CATEGORIES, index=cat_idx)
                difficulty = c2.selectbox("Difficulty", VALID_DIFFICULTIES, index=diff_idx)
                question = st.text_area("Question", value=row["question"], height=100)
                keywords = st.text_input("Keywords", value=row.get("keywords", ""))
                if st.form_submit_button("Save changes", type="primary"):
                    try:
                        update_question(
                            options[selected_label],
                            category,
                            difficulty,
                            question,
                            keywords,
                        )
                        st.success(f"Updated question #{options[selected_label]}.")
                        st.session_state.current_question = None
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    with crud_tabs[3]:
        st.markdown("### Delete question")
        if df.empty:
            st.info("No questions to delete.")
        else:
            options = {f"#{int(r['id'])} — {r['question']}": int(r["id"]) for _, r in df.iterrows()}
            selected_label = st.selectbox("Select question to delete", list(options.keys()), key="del_select")
            st.warning("This action cannot be undone.")
            if st.button("Delete question", type="primary"):
                qid = options[selected_label]
                if delete_question(qid):
                    st.success(f"Deleted question #{qid}.")
                    st.session_state.current_question = None
                    st.rerun()
                else:
                    st.error("Question not found.")


def render_expense_tab() -> None:
    username = st.session_state.username
    with st.sidebar:
        render_user_sidebar()

    st.subheader("Expense Tracker")
    st.caption("Create, read, update, and delete your personal expenses.")

    summary = expense_summary(username)
    m1, m2, m3 = st.columns(3)
    m1.metric("Total spent", f"${summary['total']:,.2f}")
    m2.metric("Transactions", summary["count"])
    m3.metric("Categories", len(summary["by_category"]))

    if summary["by_category"]:
        chart_df = pd.DataFrame(
            [{"category": k, "amount": v} for k, v in summary["by_category"].items()]
        )
        st.bar_chart(chart_df.set_index("category"))

    crud_tabs = st.tabs(["📋 Read", "➕ Create", "✏️ Update", "🗑️ Delete", "🤖 AI insights"])

    with crud_tabs[0]:
        st.markdown("### Your expenses")
        cat_filter = st.selectbox(
            "Filter by category",
            ["All"] + list(EXPENSE_CATEGORIES),
            key="exp_filter_cat",
        )
        df = list_expenses(username, cat_filter)
        if df.empty:
            st.info("No expenses yet. Add one in the **Create** tab.")
        else:
            st.dataframe(
                df[["id", "title", "amount", "category", "expense_date", "notes"]],
                use_container_width=True,
                hide_index=True,
            )
            st.caption(f"Showing {len(df)} expense(s)")

    with crud_tabs[1]:
        st.markdown("### Add expense")
        with st.form("expense_create_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            title = c1.text_input("Title", placeholder="e.g. Lunch")
            amount = c2.number_input("Amount ($)", min_value=0.01, value=10.0, step=0.5)
            c3, c4 = st.columns(2)
            category = c3.selectbox("Category", EXPENSE_CATEGORIES, key="exp_create_cat")
            expense_date = c4.date_input("Date", value=date.today())
            notes = st.text_input("Notes (optional)")
            if st.form_submit_button("Add expense", type="primary"):
                try:
                    row = create_expense(
                        username,
                        title,
                        amount,
                        category,
                        str(expense_date),
                        notes,
                    )
                    st.success(f"Created expense #{int(row['id'])}.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    with crud_tabs[2]:
        st.markdown("### Edit expense")
        df = list_expenses(username)
        if df.empty:
            st.info("No expenses to edit.")
        else:
            options = {
                f"#{int(r['id'])} — {r['title']} (${r['amount']:.2f})": int(r["id"])
                for _, r in df.iterrows()
            }
            label = st.selectbox("Select expense", list(options.keys()), key="exp_edit_sel")
            row = df[df["id"] == options[label]].iloc[0]
            cat_idx = (
                list(EXPENSE_CATEGORIES).index(row["category"])
                if row["category"] in EXPENSE_CATEGORIES
                else 0
            )
            with st.form("expense_update_form"):
                c1, c2 = st.columns(2)
                title = c1.text_input("Title", value=row["title"])
                amount = c2.number_input("Amount ($)", min_value=0.01, value=float(row["amount"]), step=0.5)
                c3, c4 = st.columns(2)
                category = c3.selectbox("Category", EXPENSE_CATEGORIES, index=cat_idx)
                try:
                    parsed = date.fromisoformat(str(row["expense_date"]))
                except ValueError:
                    parsed = date.today()
                exp_date = c4.date_input("Date", value=parsed)
                notes = st.text_input("Notes", value=row.get("notes", ""))
                if st.form_submit_button("Save changes", type="primary"):
                    try:
                        update_expense(
                            options[label],
                            username,
                            title,
                            amount,
                            category,
                            str(exp_date),
                            notes,
                        )
                        st.success(f"Updated expense #{options[label]}.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    with crud_tabs[3]:
        st.markdown("### Delete expense")
        df = list_expenses(username)
        if df.empty:
            st.info("No expenses to delete.")
        else:
            options = {
                f"#{int(r['id'])} — {r['title']} (${r['amount']:.2f})": int(r["id"])
                for _, r in df.iterrows()
            }
            label = st.selectbox("Select expense to delete", list(options.keys()), key="exp_del_sel")
            st.warning("This cannot be undone.")
            if st.button("Delete expense", type="primary"):
                if delete_expense(options[label], username):
                    st.success(f"Deleted expense #{options[label]}.")
                    st.rerun()
                else:
                    st.error("Expense not found.")

    with crud_tabs[4]:
        st.markdown("### AI spending insights (Google GenAI SDK)")
        st.caption("Powered by `@google/genai` (npm) or `google-genai` (Python). Set `GOOGLE_API_KEY`.")
        df = list_expenses(username)
        if st.button("Analyze my expenses", type="primary"):
            with st.spinner("Running GenAI SDK…"):
                ok, msg = analyze_expenses_with_sdk(df, username)
            if ok:
                st.markdown(msg)
            else:
                st.warning(msg)


def main() -> None:
    st.set_page_config(
        page_title="AI Interview Prep Assistant",
        page_icon="🎯",
        layout="wide",
    )
    load_css()
    init_session()
    ensure_default_users()

    if not st.session_state.authenticated:
        render_login_page()
        return

    try:
        questions_df = load_questions()
    except (FileNotFoundError, ValueError) as e:
        st.error(str(e))
        st.stop()

    st.markdown(
        """
        <div class="app-header">
            <h1>🎯 AI Interview Preparation Assistant</h1>
            <p>Practice interview questions and get NLP-powered feedback on your answers.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    page = st.radio(
        "Navigation",
        ["🎤 Practice", "📚 Manage questions", "💰 Expense Tracker"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if page == "🎤 Practice":
        with st.sidebar:
            st.header("Session settings")
            categories = ["All"] + sorted(questions_df["category"].unique().tolist())
            difficulties = ["All"] + sorted(questions_df["difficulty"].unique().tolist())
            category = st.selectbox("Category", categories)
            difficulty = st.selectbox("Difficulty", difficulties)
        render_practice_tab(questions_df, category, difficulty)
    elif page == "📚 Manage questions":
        render_crud_tab()
    else:
        render_expense_tab()


if __name__ == "__main__":
    main()
