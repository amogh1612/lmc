"""Minimal, free RAG core: TF-IDF retrieval over a local .txt file + Groq for generation."""

import os
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KB_PATH = os.path.join(os.path.dirname(__file__), "knowledge_base.txt")

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


class Retriever:
    def __init__(self, chunks: list[str]):
        self.chunks = chunks
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform(chunks)

    def search(self, query: str, top_k: int = 2) -> list[tuple[str, float]]:
        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.matrix).flatten()
        ranked = sorted(zip(self.chunks, scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


def build_retriever() -> Retriever:
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
