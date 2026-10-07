"""Minimal, free RAG core: TF-IDF retrieval over a local .txt file + Groq for generation."""

import json
import os
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = os.path.dirname(__file__)
JSON_KB_PATH = os.path.join(BASE_DIR, "southview_rag_database.json")
KB_PATH = os.path.join(BASE_DIR, "knowledge_base.txt")

# Below this cosine-similarity score, we treat the question as "not in the knowledge base".
SIMILARITY_THRESHOLD = 0.08

SYSTEM_PROMPT = """You are an assistant for Southview Cemetery. You answer ONLY using the \
CONTEXT provided below, which comes from the cemetery's records of notable figures.

Rules:
- Only use facts stated in the CONTEXT. Do not use outside knowledge.
- If the CONTEXT does not contain the answer, respond exactly with: \
"I'm sorry, I don't have that information in Southview Cemetery's records."
- Keep answers short and factual.
"""


def load_chunks(path: str = KB_PATH) -> list[str]:
    """Split the knowledge base into one chunk per '## Name' entry."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # Drop comment lines (lines starting with '#' but not '## ')
    lines = [ln for ln in text.splitlines() if not re.match(r"^#(?!# )", ln)]
    text = "\n".join(lines)

    raw_chunks = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    return [c.strip() for c in raw_chunks if c.strip()]


def _fmt(value) -> str:
    """Flatten nested JSON values into readable text."""
    if isinstance(value, dict):
        return "; ".join(f"{k.replace('_', ' ')}: {_fmt(v)}" for k, v in value.items())
    if isinstance(value, list):
        return "; ".join(_fmt(v) for v in value)
    return str(value)


def load_json_chunks(path: str = JSON_KB_PATH) -> list[str]:
    """Turn every record in the South-View JSON database into one text chunk."""
    with open(path, "r", encoding="utf-8") as f:
        db = json.load(f)

    chunks = []

    profile = db.get("cemetery_profile")
    if profile:
        lines = [f"## {profile.get('name', 'South-View Cemetery')} (cemetery profile)"]
        for key, value in profile.items():
            if key in ("id", "type"):
                continue
            lines.append(f"{key.replace('_', ' ').capitalize()}: {_fmt(value)}")
        chunks.append("\n".join(lines))

    for item in db.get("historical_context", []):
        chunks.append(f"## {item.get('topic', 'History')}\n{item.get('content', '')}")

    for person in db.get("people", []):
        name = person.get("full_name", "")
        lines = []
        if name and "preceding entry" not in name.lower():
            lines.append(f"## {name}")
        else:
            lines.append("## Person buried at South-View")
        if person.get("also_known_as"):
            lines.append(f"Also known as: {', '.join(person['also_known_as'])}")
        if person.get("death_year"):
            lines.append(f"Died: {person['death_year']} ({person.get('era', '')})")
        if person.get("occupations"):
            lines.append(f"Occupations: {', '.join(person['occupations'])}")
        if person.get("spouse"):
            lines.append(f"Spouse: {person['spouse']}")
        if person.get("affiliated_organizations"):
            lines.append(f"Organizations: {', '.join(person['affiliated_organizations'])}")
        lines.append(person.get("biography", ""))
        chunks.append("\n".join(lines))

    for ref in db.get("references", []):
        body = {k: v for k, v in ref.items() if k not in ("id", "type", "topic")}
        chunks.append(f"## {ref.get('topic', 'Reference')}\n{_fmt(body)}")

    for faq in db.get("faqs", []):
        chunks.append(f"## FAQ: {faq.get('q', '')}\n{faq.get('a', '')}")

    return [c.strip() for c in chunks if c.strip()]


class Retriever:
    def __init__(self, chunks: list[str]):
        self.chunks = chunks
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform(chunks)

    def search(self, query: str, top_k: int = 4) -> list[tuple[str, float]]:
        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.matrix).flatten()
        ranked = sorted(zip(self.chunks, scores), key=lambda x: x[1], reverse=True)

        # If the question names someone exactly (e.g. from a featured card), put their record first.
        q = query.lower()
        exact = [(c, s) for c, s in ranked if c.startswith("## ") and c[3:].split("\n", 1)[0].lower() in q
                 and "faq:" not in c[:8].lower()]
        if exact:
            best = max(exact, key=lambda x: len(x[0].split("\n", 1)[0]))  # longest name wins
            ranked = [best] + [r for r in ranked if r[0] is not best[0]]
        return ranked[:top_k]


def build_retriever() -> Retriever:
    if os.path.exists(JSON_KB_PATH):
        return Retriever(load_json_chunks())
    return Retriever(load_chunks())


def answer_question(question: str, retriever: Retriever, groq_client, model: str) -> str:
    results = retriever.search(question)
    best_score = results[0][1] if results else 0.0

    if best_score < SIMILARITY_THRESHOLD:
        return "I'm sorry, I don't have that information in Southview Cemetery's records."

    context = "\n\n---\n\n".join(chunk for chunk, _ in results)

    response = groq_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION: {question}"},
        ],
        temperature=0,
    )
    return response.choices[0].message.content.strip()
