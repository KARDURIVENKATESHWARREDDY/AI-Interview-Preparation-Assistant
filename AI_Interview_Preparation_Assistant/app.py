from pathlib import Path

import streamlit as st

from utils.auth import authenticate, ensure_default_users, register_user
from utils.evaluator import evaluate_answer
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
        ["🎤 Practice", "📚 Manage questions"],
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
    else:
        render_crud_tab()


if __name__ == "__main__":
    main()
