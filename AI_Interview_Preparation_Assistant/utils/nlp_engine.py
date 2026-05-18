"""NLP utilities for interview answer analysis."""

from __future__ import annotations

import re
from functools import lru_cache

import nltk
import textstat
from nltk import pos_tag, word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from textblob import TextBlob

_NLTK_PACKAGES = (
    "punkt",
    "punkt_tab",
    "stopwords",
    "averaged_perceptron_tagger",
    "averaged_perceptron_tagger_eng",
    "wordnet",
    "omw-1.4",
)


@lru_cache(maxsize=1)
def ensure_nltk_data() -> None:
    for package in _NLTK_PACKAGES:
        nltk.download(package, quiet=True)


@lru_cache(maxsize=1)
def _lemmatizer() -> WordNetLemmatizer:
    ensure_nltk_data()
    return WordNetLemmatizer()


def _normalize(text: str) -> str:
    text = re.sub(r"[^\w\s]", " ", (text or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> list[str]:
    ensure_nltk_data()
    stops = set(stopwords.words("english"))
    lem = _lemmatizer()
    tokens = [
        lem.lemmatize(w)
        for w in word_tokenize(_normalize(text))
        if w.isalpha() and w not in stops and len(w) > 2
    ]
    return tokens


def question_expansion(question: str, keywords: str = "") -> str:
    """Combine question with keywords for fairer relevance scoring."""
    parts = [_normalize(question)]
    if keywords:
        parts.append(_normalize(keywords.replace(",", " ")))
    return " ".join(parts)


def star_structure_score(answer: str) -> float:
    """Detect STAR-style markers in behavioral answers (0–1)."""
    if not answer:
        return 0.0
    text = answer.lower()
    patterns = (
        r"\b(situation|when|background|context)\b",
        r"\b(task|goal|responsible|needed to)\b",
        r"\b(i |we |led|built|implemented|designed)\b",
        r"\b(result|outcome|impact|learned|improved)\b",
    )
    hits = sum(1 for p in patterns if re.search(p, text))
    return hits / len(patterns)


def relevance_score(question: str, answer: str) -> float:
    """TF-IDF cosine similarity between question and answer (0–1)."""
    if not (question or "").strip() or not (answer or "").strip():
        return 0.0
    docs = [_normalize(question), _normalize(answer)]
    matrix = TfidfVectorizer(ngram_range=(1, 2), min_df=1).fit_transform(docs)
    sim = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
    return float(max(0.0, min(1.0, sim)))


def keyword_coverage(keywords: str, answer: str) -> float:
    """Share of expected keywords present in the answer (0–1)."""
    if not keywords or not answer:
        return 0.0
    expected = [k.strip().lower() for k in keywords.split(",") if k.strip()]
    if not expected:
        return 0.0
    answer_tokens = set(tokenize(answer))
    answer_text = _normalize(answer)
    hits = sum(
        1
        for kw in expected
        if kw in answer_text or any(kw in t or t in kw for t in answer_tokens)
    )
    return hits / len(expected)


def sentiment_analysis(answer: str) -> dict:
    blob = TextBlob(answer or "")
    polarity = blob.sentiment.polarity
    subjectivity = blob.sentiment.subjectivity
    if polarity > 0.15:
        label = "Positive"
    elif polarity < -0.15:
        label = "Negative"
    else:
        label = "Neutral"
    return {
        "polarity": round(polarity, 3),
        "subjectivity": round(subjectivity, 3),
        "label": label,
    }


def readability_scores(answer: str) -> dict:
    if not (answer or "").strip():
        return {"flesch_reading_ease": 0.0, "grade_level": 0.0}
    return {
        "flesch_reading_ease": round(textstat.flesch_reading_ease(answer), 1),
        "grade_level": round(textstat.flesch_kincaid_grade(answer), 1),
    }


def lexical_diversity(answer: str) -> float:
    tokens = tokenize(answer)
    if len(tokens) < 5:
        return 0.0
    return len(set(tokens)) / len(tokens)


def count_entities_and_metrics(answer: str) -> dict:
    ensure_nltk_data()
    words = word_tokenize(answer or "")
    tagged = pos_tag(words)
    nouns = sum(1 for _, tag in tagged if tag.startswith("NN"))
    verbs = sum(1 for _, tag in tagged if tag.startswith("VB"))
    numbers = len(re.findall(r"\b\d+[%kKmMbB]?\b", answer or ""))
    first_person = len(re.findall(r"\b(I|my|me|we|our)\b", answer or "", re.I))
    return {
        "nouns": nouns,
        "verbs": verbs,
        "numbers": numbers,
        "first_person": first_person,
        "sentences": max(1, len(TextBlob(answer).sentences)),
    }
