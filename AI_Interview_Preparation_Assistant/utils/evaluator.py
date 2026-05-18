"""Evaluate interview answers using NLP and heuristic scoring."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from utils.nlp_engine import (
    count_entities_and_metrics,
    ensure_nltk_data,
    keyword_coverage,
    lexical_diversity,
    question_expansion,
    readability_scores,
    relevance_score,
    sentiment_analysis,
    star_structure_score,
)


@dataclass
class EvaluationResult:
    score: int
    feedback: list[str]
    strengths: list[str]
    improvements: list[str]
    nlp_metrics: dict = field(default_factory=dict)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def evaluate_answer(
    question: str,
    answer: str,
    keywords: str = "",
    category: str = "",
) -> EvaluationResult:
    ensure_nltk_data()
    answer = (answer or "").strip()
    feedback: list[str] = []
    strengths: list[str] = []
    improvements: list[str] = []
    points = 0.0

    if not answer:
        return EvaluationResult(
            score=0,
            feedback=["No answer provided."],
            strengths=[],
            improvements=["Write a complete response before submitting."],
            nlp_metrics={},
        )

    rel = relevance_score(question_expansion(question, keywords), answer)
    star = star_structure_score(answer)
    kw_cov = keyword_coverage(keywords, answer)
    sentiment = sentiment_analysis(answer)
    readability = readability_scores(answer)
    diversity = lexical_diversity(answer)
    entities = count_entities_and_metrics(answer)
    words = _word_count(answer)

    nlp_metrics = {
        "relevance": round(rel * 100, 1),
        "keyword_coverage": round(kw_cov * 100, 1),
        "sentiment": sentiment["label"],
        "polarity": sentiment["polarity"],
        "subjectivity": sentiment["subjectivity"],
        "lexical_diversity": round(diversity * 100, 1),
        "flesch_reading_ease": readability["flesch_reading_ease"],
        "grade_level": readability["grade_level"],
        "word_count": words,
        "star_score": round(star * 100, 1),
        **entities,
    }

    # Relevance (TF-IDF question–answer similarity)
    if rel >= 0.18:
        points += 18
        strengths.append(
            f"Answer is relevant to the question (NLP similarity: {nlp_metrics['relevance']}%)."
        )
    elif rel >= 0.08:
        points += 10
        improvements.append("Tie your answer more directly to what was asked.")
    else:
        improvements.append(
            "Your answer seems off-topic — restate the question and address it head-on."
        )

    # Keyword / topic coverage
    if keywords:
        if kw_cov >= 0.5:
            points += 15
            strengths.append(
                f"Covers key topics well (keyword coverage: {nlp_metrics['keyword_coverage']}%)."
            )
        elif kw_cov >= 0.25:
            points += 8
            improvements.append(
                f"Include more role-specific terms (coverage: {nlp_metrics['keyword_coverage']}%)."
            )
        else:
            improvements.append(
                "Use vocabulary that matches the question domain (e.g. impact, trade-offs, outcomes)."
            )

    # Length
    if words < 35:
        improvements.append("Expand to at least 4–6 sentences with concrete detail.")
    elif words <= 200:
        points += 15
        strengths.append(f"Appropriate length ({words} words).")
    else:
        points += 8
        improvements.append("Consider shortening — concise answers are easier to follow.")

    # Lexical diversity
    if diversity >= 0.55:
        points += 12
        strengths.append(
            f"Rich vocabulary (lexical diversity: {nlp_metrics['lexical_diversity']}%)."
        )
    elif diversity >= 0.35:
        points += 6
    else:
        improvements.append("Avoid repeating the same words — vary your phrasing.")

    # Readability (Flesch: 60–80 is conversational professional)
    fre = readability["flesch_reading_ease"]
    if 50 <= fre <= 85:
        points += 10
        strengths.append(f"Readable, conversational tone (Flesch: {fre}).")
    elif fre < 40:
        improvements.append("Simplify sentences — very dense text is hard to follow aloud.")
    elif fre > 90:
        improvements.append("Add more depth — answer may be too brief or choppy.")

    # Sentiment (interviews: neutral to mildly positive)
    pol = sentiment["polarity"]
    if -0.2 <= pol <= 0.6:
        points += 10
        strengths.append(f"Professional tone (sentiment: {sentiment['label']}).")
    elif pol < -0.2:
        improvements.append("Reframe negatives constructively — focus on learning and growth.")
    if sentiment["subjectivity"] > 0.75:
        improvements.append("Balance opinions with facts, metrics, or examples.")

    # Specificity (numbers, first-person storytelling)
    if entities["numbers"] >= 1:
        points += 10
        strengths.append("Includes quantifiable details (metrics or numbers).")
    else:
        improvements.append("Add a metric, percentage, or timeframe to strengthen credibility.")

    if entities["first_person"] >= 2 and entities["verbs"] >= 3:
        points += 10
        strengths.append("Uses active, personal narrative suitable for behavioral answers.")
    elif category == "Behavioral":
        improvements.append("Use STAR format: Situation, Task, Action, Result — with 'I' statements.")

    q_lower = question.lower()
    if any(k in q_lower for k in ("conflict", "failure", "challenge", "proud", "time you")):
        if star >= 0.5 or re.search(r"\b(result|outcome|learned|impact)\b", answer, re.I):
            points += 8
            strengths.append("Addresses outcome or learning (STAR-friendly).")
        else:
            improvements.append("End with the result and what you learned.")

    if any(k in q_lower for k in ("design", "how would", "explain", "difference")):
        if re.search(r"\b(because|trade-?off|scal(e|ability)|performance|security)\b", answer, re.I):
            points += 8
        else:
            improvements.append("Discuss trade-offs, constraints, or design rationale.")

    score = int(min(100, max(0, round(points))))

    if score >= 75:
        feedback.append("Strong NLP profile — polish with one more metric or sharper conclusion.")
    elif score >= 50:
        feedback.append("Solid base — improve relevance and topic keywords to score higher.")
    else:
        feedback.append("Focus on relevance, examples, and structured storytelling.")

    return EvaluationResult(
        score=score,
        feedback=feedback,
        strengths=strengths,
        improvements=improvements,
        nlp_metrics=nlp_metrics,
    )
