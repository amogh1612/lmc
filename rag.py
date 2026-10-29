"""Minimal, free RAG core: TF-IDF retrieval over a local knowledge base + Groq for generation."""

import json
import os
import re

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = os.path.dirname(__file__)
JSON_KB_PATH = os.path.join(BASE_DIR, "southview_rag_database.json")
KB_PATH = os.path.join(BASE_DIR, "knowledge_base.txt")

# Below this cosine-similarity score, we treat the question as "not in the knowledge base".
SIMILARITY_THRESHOLD = 0.11
TOP_K = 6
HISTORY_TURNS = 6  # how many recent messages the model sees for follow-up questions

BOOK = "South-View: City of the Dead, D.L. Henderson (Carrelspin Press, 2018)"
KB_SOURCE = "South-View knowledge base, compiled from Henderson (2018) and cemetery records"

NOT_FOUND = "I'm sorry, I don't have that information in South-View Cemetery's records."

SYSTEM_PROMPT = """You are a friendly, knowledgeable guide for South-View Cemetery in Atlanta, \
the city's oldest African American cemetery. You answer questions about the people buried there \
and the cemetery's history.

How to answer:
- Base every fact about people and the cemetery on the numbered CONTEXT entries.
- Every date, age, number, place, name or achievement you state about a person or the cemetery \
must appear in the CONTEXT. Do not fill gaps such as birth years from memory.
- You may add a short line of widely known general background to explain a term in the CONTEXT \
(for example what SNCC or the NAACP is), but nothing about specific individuals.
- Follow-up questions are welcome. Use the conversation so far to work out who "he", "she", \
"they" or "that" refers to.
- If the CONTEXT does not answer the question, say you don't have that in South-View's records, \
and suggest a related question you can answer if one fits.
- When the question asks which people or how many, check every CONTEXT entry and include each \
person who matches, not just the first.
- Write in a warm, plain style. A few sentences is usually right; use a short list when it helps.
- Finish with one last line in exactly this form, listing the CONTEXT numbers you used: \
SOURCES: [1], [3]
If you used none, write: SOURCES: none
"""

REWRITE_PROMPT = """Rewrite the user's latest message as one standalone question that names the \
person or topic it refers to, using the conversation for context. If it is already standalone, \
return it unchanged. Reply with the question only."""

CLARIFY_MESSAGE = (
    "Could you be more specific? Please include the person's name or the topic you're asking about."
)

GREETING_REPLY = (
    "Hello! I can tell you about the people buried at South-View Cemetery and the cemetery's history. "
    "Try asking about someone by name, or pick a figure from the cards above."
)
THANKS_REPLY = "You're welcome! Feel free to ask about anyone else at South-View."

# Words that refer to someone without naming them.
PRONOUNS = {"he", "she", "him", "her", "his", "hers", "they", "them", "their", "theirs", "himself", "herself"}

# Words that carry no subject on their own.
FILLER = {"did", "does", "do", "done", "tell", "know", "info", "information", "anything", "something", "stuff",
          "thing", "things", "explain", "describe", "talk", "say", "said", "like", "please", "happened", "happen",
          "life", "person", "people", "someone", "somebody", "guy", "man", "woman", "story", "fact", "facts",
          "details", "detail", "known", "famous", "important", "why", "who", "whom", "what", "was", "is", "are",
          "were", "can", "could", "would", "about", "more", "else", "again", "ok", "okay", "hi", "hello", "hey"}

GREETINGS = {"hi", "hello", "hey", "hiya", "greetings", "morning", "afternoon", "evening", "good"}
THANKS = {"thanks", "thank", "you", "thx", "ty", "appreciate", "it", "great", "awesome", "cool", "ok", "okay",
          "nice", "so", "much", "very", "bye", "goodbye"}

# Surnames that are also everyday words; they only count as a name when typed with a capital letter.
COMMON_WORD_NAMES = {"young", "white", "price", "hill", "bell", "king", "lee", "mae", "green", "brown", "grant",
                     "rush", "guest", "swift", "penn", "oliver", "fuller", "hart", "long", "reeves", "parker",
                     "turner", "carter", "cox", "nash", "miller", "shaw", "simon", "pace", "henry", "watts",
                     "bond", "hamilton", "russell", "aaron", "dobbs"}


def _chunk(text: str, sources: list[dict], names: list[str] | None = None) -> dict:
    return {"text": text.strip(), "sources": sources, "names": [n for n in (names or []) if n]}


def load_chunks(path: str = KB_PATH) -> list[dict]:
    """Split the plain-text knowledge base into one chunk per '## Name' entry."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # Drop comment lines (lines starting with '#' but not '## ')
    lines = [ln for ln in text.splitlines() if not re.match(r"^#(?!# )", ln)]
    text = "\n".join(lines)

    raw_chunks = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    out = []
    for c in raw_chunks:
        if c.strip():
            name = c.strip().split("\n", 1)[0].lstrip("# ").strip()
            out.append(_chunk(c, [{"title": "knowledge_base.txt", "detail": name}], [name]))
    return out


def _fmt(value) -> str:
    """Flatten nested JSON values into readable text."""
    if isinstance(value, dict):
        return "; ".join(f"{k.replace('_', ' ')}: {_fmt(v)}" for k, v in value.items())
    if isinstance(value, list):
        return "; ".join(_fmt(v) for v in value)
    return str(value)


def _web_sources(entry: dict, all_sources: list[dict]) -> list[dict]:
    """Resolve a section's source numbers into title/url dicts."""
    out = []
    for i in entry.get("sources", []):
        if 1 <= i <= len(all_sources):
            s = all_sources[i - 1]
            out.append({"title": s["title"], "url": s.get("url"), "detail": s.get("publisher")})
    return out


def load_json_chunks(path: str = JSON_KB_PATH) -> list[dict]:
    """Turn every record in the South-View JSON database into one or more text chunks."""
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
        chunks.append(_chunk("\n".join(lines), [{"title": KB_SOURCE, "detail": "Cemetery profile"}]))

    for item in db.get("historical_context", []):
        topic = item.get("topic", "History")
        chunks.append(_chunk(f"## {topic}\n{item.get('content', '')}", [{"title": KB_SOURCE, "detail": topic}]))

    for person in db.get("people", []):
        name = person.get("full_name", "")
        has_name = name and "preceding entry" not in name.lower()
        lines = [f"## {name}" if has_name else "## Person buried at South-View"]
        if person.get("also_known_as"):
            lines.append(f"Also known as: {', '.join(person['also_known_as'])}")
        if person.get("birth_year"):
            lines.append(f"Born: {person['birth_year']}")
        if person.get("death_year"):
            lines.append(f"Died: {person['death_year']} ({person.get('era', '')})")
        if person.get("occupations"):
            lines.append(f"Occupations: {', '.join(person['occupations'])}")
        if person.get("spouse"):
            lines.append(f"Spouse: {person['spouse']}")
        if person.get("affiliated_organizations"):
            lines.append(f"Organizations: {', '.join(person['affiliated_organizations'])}")
        lines.append(person.get("biography", ""))
        if person.get("web_sources"):
            sources = [{"title": s["title"], "url": s.get("url"), "detail": s.get("publisher")}
                       for s in person["web_sources"]]
        else:
            sources = [{"title": BOOK, "detail": f"Biographical Dictionary: {name}" if has_name else None}]
        names = [name] + person.get("also_known_as", []) if has_name else []
        chunks.append(_chunk("\n".join(lines), sources, names))

    # Researched profiles of prominent figures: one chunk per section, each with its own web sources.
    for fig in db.get("prominent_figures", []):
        name = fig["full_name"]
        names = [name] + fig.get("also_known_as", [])
        aka = f" (also known as {', '.join(fig['also_known_as'])})" if fig.get("also_known_as") else ""
        header = f"## {name}{aka}, {fig.get('lifespan', '')}".rstrip(", ")
        for section in fig.get("sections", []):
            text = f"{header}\n### {section['heading']}\n{section['text']}"
            chunks.append(_chunk(text, _web_sources(section, fig.get("sources", [])), names))
        if fig.get("burial"):
            # Credit the sources the burial note names (e.g. "Find a Grave", "Associated Press").
            burial = fig["burial"].lower()
            named = [{"title": x["title"], "url": x.get("url"), "detail": x.get("publisher")}
                     for x in fig.get("sources", [])
                     if x.get("publisher") and x["publisher"].split(" (")[0].lower() in burial]
            chunks.append(_chunk(f"{header}\n### Burial or memorial at South-View\n{fig['burial']}",
                                 named or [{"title": BOOK, "detail": f"Biographical Dictionary: {name}"}], names))
        if fig.get("timeline"):
            text = f"{header}\n### Timeline\n" + "\n".join(f"{t['year']}: {t['event']}" for t in fig["timeline"])
            src = sorted({i for t in fig["timeline"] for i in t.get("sources", [])})
            chunks.append(_chunk(text, _web_sources({"sources": src}, fig.get("sources", [])), names))

    for ref in db.get("references", []):
        topic = ref.get("topic", "Reference")
        body = {k: v for k, v in ref.items() if k not in ("id", "type", "topic")}
        chunks.append(_chunk(f"## {topic}\n{_fmt(body)}", [{"title": KB_SOURCE, "detail": topic}]))

    # Link each FAQ to the person it is about, so the person's other records can be pulled in with it.
    person_names = [c["names"] for c in chunks if c["names"]]
    for faq in db.get("faqs", []):
        q = faq.get("q", "")
        about = next((names for names in person_names if any(n in q for n in names)), [])
        chunks.append(_chunk(f"## FAQ: {q}\n{faq.get('a', '')}",
                             [{"title": KB_SOURCE, "detail": "Frequently asked questions"}], about))

    return [c for c in chunks if c["text"]]


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", text)


def _name_tokens(chunks: list[dict]) -> set[str]:
    """Lowercased words from the names of people in the knowledge base."""
    tokens = set()
    for c in chunks:
        for n in c["names"]:
            tokens.update(w.lower().strip("'\"") for w in _words(n) if len(w) >= 3)
    return tokens - {"jr", "sr", "the", "and"}


# Words that appear in almost every question about the cemetery and only add noise to the search.
QUERY_NOISE = {"buried", "burial", "interred", "south", "view", "south-view", "southview", "here", "cemetery"}


def _tokenize(text: str) -> list[str]:
    """Lowercase words with light plural folding, so 'Airmen' matches 'Airman' and 'pastors' matches 'pastor'."""
    out = []
    for w in re.findall(r"[a-z0-9][a-z0-9'\-]*", text.lower()):
        w = w.removesuffix("'s")
        if w.endswith("men") and len(w) > 4:
            w = w[:-3] + "man"
        elif w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            w = w[:-1]
        out.append(w)
    return out


def _clean_query(query: str) -> str:
    words = query.split()
    kept = [w for w in words if w.lower().strip("?.,!") not in QUERY_NOISE]
    return " ".join(kept) if len(kept) >= 2 else query


class Retriever:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.name_tokens = _name_tokens(chunks)
        stop = sorted({t for w in ENGLISH_STOP_WORDS for t in _tokenize(w)})
        self.vectorizer = TfidfVectorizer(tokenizer=_tokenize, token_pattern=None, lowercase=False,
                                          stop_words=stop, ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform([c["text"] for c in chunks])

    def search(self, query: str, top_k: int = TOP_K) -> list[tuple[dict, float]]:
        query_vec = self.vectorizer.transform([_clean_query(query)])
        scores = cosine_similarity(query_vec, self.matrix).flatten()
        ranked = sorted(zip(self.chunks, scores), key=lambda x: x[1], reverse=True)

        # If the question names someone exactly (e.g. from a card), put their records first.
        q = query.lower()
        matched = [(c, max(len(n) for n in c["names"] if n.lower() in q)) for c, _ in ranked
                   if any(n.lower() in q for n in c["names"])]
        if matched:
            longest = max(m for _, m in matched)  # "Martin Luther King Sr." beats "Martin Luther King"
            exact = [c for c, m in matched if m == longest]
            ids = {id(c) for c in exact}
            ranked = [(c, s) for c, s in ranked if id(c) in ids] + [(c, s) for c, s in ranked if id(c) not in ids]
        else:
            ranked = self._pull_in_profile(ranked)
        return ranked[:top_k]

    @staticmethod
    def _pull_in_profile(ranked: list[tuple[dict, float]]) -> list[tuple[dict, float]]:
        """When the best match is a person, move their next-best chunks (e.g. profile sections) up too.

        A question like "Who founded Atlanta Life and when?" may match a short book entry best, while the
        detail ("1905") sits in the same person's researched profile.
        """
        if not ranked or not ranked[0][0]["names"]:
            return ranked
        top_chunk = ranked[0][0]
        person = top_chunk["names"][0]
        extra = [(c, s) for c, s in ranked[1:] if c["names"] and c["names"][0] == person and s > 0][:3]
        ids = {id(c) for c, _ in extra}
        return [ranked[0]] + extra + [(c, s) for c, s in ranked[1:] if id(c) not in ids]


def build_retriever() -> Retriever:
    if os.path.exists(JSON_KB_PATH):
        return Retriever(load_json_chunks())
    return Retriever(load_chunks())


def small_talk_reply(question: str) -> str | None:
    """Friendly replies for greetings and thanks, so they don't get treated as vague questions."""
    words = {w.lower() for w in _words(question)}
    if not words:
        return None
    if words <= GREETINGS | {"there", "how", "are", "you"}:
        return GREETING_REPLY
    if words <= THANKS and words & {"thanks", "thank", "thx", "ty", "appreciate", "bye", "goodbye"}:
        return THANKS_REPLY
    return None


def is_too_vague(question: str, retriever: Retriever) -> bool:
    """True when a question has no real subject, or says he/she/they without naming anyone."""
    raw = _words(question)
    words = [w.lower() for w in raw]
    content = [w for w in words if w not in ENGLISH_STOP_WORDS and w not in FILLER and w not in PRONOUNS]
    if not content:
        return True
    if any(w in PRONOUNS for w in words):
        names = {w.lower() for w in raw
                 if w.lower() in retriever.name_tokens and (w[0].isupper() or w.lower() not in COMMON_WORD_NAMES)}
        if not names:
            return True
    return False


def _chat(groq_client, model: str, messages: list[dict]) -> str:
    response = groq_client.chat.completions.create(model=model, messages=messages, temperature=0)
    return (response.choices[0].message.content or "").strip()


def _recent(history: list[dict]) -> list[dict]:
    return [{"role": m["role"], "content": m["content"]} for m in history[-HISTORY_TURNS:]]


def standalone_question(question: str, history: list[dict], groq_client, model: str) -> str:
    """Turn a follow-up like 'where did he study?' into 'Where did Julian Bond study?'."""
    if not history:
        return question
    convo = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in _recent(history))
    rewritten = _chat(groq_client, model, [
        {"role": "system", "content": REWRITE_PROMPT},
        {"role": "user", "content": f"CONVERSATION:\n{convo}\n\nLATEST MESSAGE: {question}"},
    ])
    rewritten = rewritten.strip().strip('"').strip()
    return rewritten or question


def _split_sources(text: str, n_context: int) -> tuple[str, list[int] | None]:
    """Remove the trailing 'SOURCES: [1], [3]' line and return the cited context numbers."""
    m = re.search(r"\n?\s*\**SOURCES?\**\s*:\s*(.*?)\s*$", text, flags=re.IGNORECASE)
    if not m:
        return text.strip(), None
    cited = [int(n) for n in re.findall(r"\d+", m.group(1)) if 1 <= int(n) <= n_context]
    return text[: m.start()].strip(), list(dict.fromkeys(cited))


def _dedupe(sources: list[dict]) -> list[dict]:
    seen, out = set(), []
    for s in sources:
        key = (s.get("title"), s.get("url"), s.get("detail"))
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def answer_question(question: str, retriever: Retriever, groq_client, model: str,
                    history: list[dict] | None = None) -> dict:
    """Answer a question. Returns {"answer": str, "sources": [{"title", "url", "detail"}]}.

    `history` is the earlier conversation as [{"role": "user"|"assistant", "content": str}].
    """
    history = history or []

    reply = small_talk_reply(question)
    if reply:
        return {"answer": reply, "sources": []}

    query = standalone_question(question, history, groq_client, model)
    if is_too_vague(query, retriever):
        return {"answer": CLARIFY_MESSAGE, "sources": []}

    results = retriever.search(query)
    best_score = results[0][1] if results else 0.0
    if best_score < SIMILARITY_THRESHOLD:
        return {"answer": NOT_FOUND, "sources": []}

    context = "\n\n---\n\n".join(f"[{i}] {c['text']}" for i, (c, _) in enumerate(results, 1))
    asked = question if query == question else f"{question}\n(Interpreted as: {query})"
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + _recent(history) + [
        {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION: {asked}"},
    ]
    answer, cited = _split_sources(_chat(groq_client, model, messages), len(results))

    if cited is None:  # model forgot the SOURCES line; credit the best match
        cited = [1]
    if "don't have that" in answer.lower() or "do not have that" in answer.lower():
        cited = []
    sources = _dedupe([s for i in cited for s in results[i - 1][0]["sources"]])
    return {"answer": answer, "sources": sources}
