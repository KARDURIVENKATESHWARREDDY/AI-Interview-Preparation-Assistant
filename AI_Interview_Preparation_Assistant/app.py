from pathlib import Path

import streamlit as st

from utils.evaluator import evaluate_answer
from utils.question_loader import filter_questions, load_questions

ASSETS = Path(__file__).parent / "assets" / "style.css"


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
    }
    st.session_state.last_result = None
    st.session_state.answer_draft = ""


def main() -> None:
    st.set_page_config(
        page_title="AI Interview Prep Assistant",
        page_icon="🎯",
        layout="wide",
    )
    load_css()
    init_session()

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

    with st.sidebar:
        st.header("Session settings")
        categories = ["All"] + sorted(questions_df["category"].unique().tolist())
        difficulties = ["All"] + sorted(questions_df["difficulty"].unique().tolist())

        category = st.selectbox("Category", categories)
        difficulty = st.selectbox("Difficulty", difficulties)

        st.divider()
        st.caption(f"**{len(questions_df)}** questions in bank")
        filtered_count = len(filter_questions(questions_df, category, difficulty))
        st.caption(f"**{filtered_count}** match current filters")

        if st.button("🎲 New question", type="primary", use_container_width=True):
            pick_question(questions_df, category, difficulty)

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


if __name__ == "__main__":
    main()
