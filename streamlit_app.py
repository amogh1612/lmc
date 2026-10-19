"""Web UI for the South-View Cemetery RAG assistant. Run with: streamlit run streamlit_app.py"""

import datetime
import html
import os
import re
import time

import streamlit as st
from dotenv import load_dotenv
from groq import Groq

from featured import monthly_featured
from rag import answer_question, build_retriever

MODEL = "openai/gpt-oss-20b"
TITLE = "South-View Cemetery Q&A"

st.set_page_config(page_title=TITLE, page_icon="🌷", layout="wide")

# Flowers tied to remembrance, used for the card accents and falling petals.
CARD_FLOWERS = ["🌹", "🌷", "🌸", "🌺", "🌼"]
PETALS = ["🌸", "🌷", "🌼", "🌺", "🌹", "💮"]

CSS = """
<style>
:root {
  --rose: #c2185b;
  --rose-soft: #f8bbd0;
  --lavender: #b39ddb;
  --sage: #8fae8b;
  --gold: #e6b450;
  --cream: #fff8f5;
  --ink: #3b2a33;
}

.stApp {
  background:
    radial-gradient(circle at 8% 12%, rgba(248,187,208,.45) 0, transparent 28%),
    radial-gradient(circle at 92% 18%, rgba(179,157,219,.35) 0, transparent 30%),
    radial-gradient(circle at 85% 90%, rgba(143,174,139,.30) 0, transparent 32%),
    radial-gradient(circle at 10% 88%, rgba(230,180,80,.22) 0, transparent 30%),
    var(--cream);
}

/* Falling petals */
.petals { position: fixed; inset: 0; pointer-events: none; overflow: hidden; z-index: 0; }
.petals span {
  position: absolute; top: -10vh; opacity: .3;
  animation: fall linear infinite;
}
@keyframes fall {
  0%   { transform: translate(0, 0) rotate(0deg); }
  50%  { transform: translate(40px, 55vh) rotate(180deg); }
  100% { transform: translate(-20px, 115vh) rotate(360deg); }
}
@media (prefers-reduced-motion: reduce) { .petals { display: none; } }

/* Header */
.hero {
  position: relative; z-index: 1;
  text-align: center; padding: 1.6rem 1rem 1.2rem; margin-bottom: 1rem;
  border-radius: 24px;
  background: linear-gradient(135deg, rgba(248,187,208,.85), rgba(209,196,233,.85) 55%, rgba(200,230,201,.85));
  box-shadow: 0 10px 30px rgba(194,24,91,.12);
}
.hero h1 {
  margin: 0; font-size: 2.6rem; color: var(--ink); letter-spacing: .5px;
  font-family: Georgia, "Times New Roman", serif;
}
.hero p { margin: .35rem 0 0; color: #5d4652; font-size: 1.05rem; }

.section-title {
  font-family: Georgia, serif; font-size: 1.4rem; color: var(--rose);
  margin: .6rem 0 .1rem;
}
.section-sub { color: #7a6270; margin-bottom: .8rem; }

/* Featured cards */
[class*="st-key-featcard"] {
  background: rgba(255,255,255,.82);
  border-radius: 20px; padding: 1rem .9rem .9rem;
  border-top: 6px solid var(--accent, var(--rose-soft));
  box-shadow: 0 6px 18px rgba(59,42,51,.08);
  transition: transform .25s ease, box-shadow .25s ease;
  height: 100%;
}
[class*="st-key-featcard"]:hover {
  transform: translateY(-6px) rotate(-.4deg);
  box-shadow: 0 14px 28px rgba(194,24,91,.18);
}
.st-key-featcard-0 { --accent: #e57399; }
.st-key-featcard-1 { --accent: #b39ddb; }
.st-key-featcard-2 { --accent: #f4a6c0; }
.st-key-featcard-3 { --accent: #8fae8b; }
.st-key-featcard-4 { --accent: #e6b450; }
.card-flower { font-size: 1.8rem; line-height: 1; }
.card-name { font-weight: 700; font-family: Georgia, serif; font-size: 1.05rem; margin: .3rem 0 .15rem; }
.card-meta { color: #8a6f7d; font-size: .85rem; margin-bottom: .4rem; }
.card-teaser { font-size: .92rem; color: #4a3741; }

.stButton > button {
  border-radius: 999px; border: 1px solid var(--rose-soft);
  background: linear-gradient(135deg, #fde4ec, #ede7f6);
  color: var(--rose); font-weight: 600;
  transition: transform .15s ease, box-shadow .15s ease;
}
.stButton > button:hover {
  transform: scale(1.03); color: #fff; border-color: transparent;
  background: linear-gradient(135deg, #e57399, #9575cd);
  box-shadow: 0 6px 14px rgba(194,24,91,.25);
}

/* Chat bubbles */
.chat { position: relative; z-index: 1; display: flex; flex-direction: column; gap: .9rem; margin: 1rem 0 1.5rem; }
.row { display: flex; align-items: flex-end; gap: .55rem; animation: bloom .35s ease-out both; }
.row.user { flex-direction: row-reverse; }
.avatar {
  flex: 0 0 auto; width: 2.4rem; height: 2.4rem; border-radius: 50%;
  display: grid; place-items: center; font-size: 1.3rem;
  background: #fff; box-shadow: 0 3px 8px rgba(59,42,51,.12);
}
.bubble {
  max-width: min(75%, 680px); padding: .8rem 1.05rem; line-height: 1.5;
  border-radius: 20px; box-shadow: 0 4px 14px rgba(59,42,51,.08);
  word-wrap: break-word;
}
.row.user .bubble {
  color: #fff; border-bottom-right-radius: 6px;
  background: linear-gradient(135deg, #d81b60, #8e5bd0);
}
.row.bot .bubble {
  color: var(--ink); border-bottom-left-radius: 6px;
  background: rgba(255,255,255,.92); border: 1px solid #f3d3df;
}
.typing span {
  display: inline-block; width: .5rem; height: .5rem; margin: 0 .12rem; border-radius: 50%;
  background: var(--rose-soft); animation: pulse 1s infinite ease-in-out;
}
.typing span:nth-child(2) { animation-delay: .15s; background: var(--lavender); }
.typing span:nth-child(3) { animation-delay: .3s; background: var(--sage); }
@keyframes pulse { 0%, 100% { transform: scale(.6); opacity: .5; } 50% { transform: scale(1); opacity: 1; } }
@keyframes bloom { from { opacity: 0; transform: translateY(10px) scale(.97); } to { opacity: 1; transform: none; } }

.empty {
  text-align: center; color: #8a6f7d; padding: 1.2rem; border-radius: 18px;
  border: 2px dashed #f3c6d6; background: rgba(255,255,255,.6);
}

[data-testid="stChatInput"] textarea { font-size: 1rem; }
[data-testid="stChatInput"] > div {
  border-radius: 999px !important; border: 2px solid var(--rose-soft) !important;
  box-shadow: 0 6px 18px rgba(194,24,91,.12);
}
hr { border-color: #f3d3df !important; }
</style>
"""


def petals_html(count: int = 18) -> str:
    spans = []
    for i in range(count):
        left = (i * 37) % 100
        size = 0.9 + (i % 4) * 0.25
        duration = 14 + (i * 7) % 12
        delay = -((i * 3.3) % duration)  # negative delay so petals are already falling on load
        spans.append(
            f'<span style="left:{left}vw;font-size:{size}rem;'
            f'animation-duration:{duration}s;animation-delay:{delay:.1f}s">{PETALS[i % len(PETALS)]}</span>'
        )
    return f'<div class="petals">{"".join(spans)}</div>'


def to_html(text: str) -> str:
    """Escape model or user text, keeping simple **bold** and line breaks."""
    safe = html.escape(text)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    return safe.replace("\n", "<br>")


def bubble(role: str, content_html: str) -> str:
    cls, avatar = ("user", "🙂") if role == "user" else ("bot", "🌷")
    return f'<div class="row {cls}"><div class="avatar">{avatar}</div><div class="bubble">{content_html}</div></div>'


def chat_html(messages: list[tuple[str, str]], extra: str = "") -> str:
    return '<div class="chat">' + "".join(bubble(r, to_html(c)) for r, c in messages) + extra + "</div>"


st.markdown(CSS + petals_html(), unsafe_allow_html=True)
st.markdown(
    f"""
    <div class="hero">
      <h1>{TITLE}</h1>
      <p>Ask about the people and history remembered at South-View Cemetery.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

load_dotenv()
api_key = os.environ.get("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", None)
if not api_key:
    st.error("Missing GROQ_API_KEY. Add it to a .env file (local) or to Streamlit secrets (hosted).")
    st.stop()


@st.cache_resource
def get_client_and_retriever():
    return Groq(api_key=api_key), build_retriever()


@st.cache_data
def get_featured(year: int, month: int):
    # Cached per month, so the picks refresh automatically when the month changes.
    return monthly_featured(datetime.date(year, month, 1))


client, retriever = get_client_and_retriever()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None


def ask_about(name: str):
    st.session_state.pending_question = f"Tell me about {name}."


# --- Featured figures of the month ---
today = datetime.date.today()
featured = get_featured(today.year, today.month)
st.markdown(
    f'<div class="section-title">🌼 Featured figures for {today.strftime("%B %Y")}</div>'
    '<div class="section-sub">Five people from South-View\'s history, chosen fresh each month. '
    "Tap a card to learn more.</div>",
    unsafe_allow_html=True,
)

cols = st.columns(len(featured))
for i, (col, fig) in enumerate(zip(cols, featured)):
    with col:
        with st.container(key=f"featcard-{i}"):
            meta = ", ".join(fig["occupations"][:2])
            if fig["death_year"]:
                meta += f" · d. {fig['death_year']}"
            st.markdown(
                f'<div class="card-flower">{CARD_FLOWERS[i % len(CARD_FLOWERS)]}</div>'
                f'<div class="card-name">{html.escape(fig["name"])}</div>'
                f'<div class="card-meta">{html.escape(meta)}</div>'
                f'<div class="card-teaser">{html.escape(fig["teaser"])}</div>',
                unsafe_allow_html=True,
            )
            st.button("Ask about them", key=f"feat-{fig['name']}", on_click=ask_about, args=(fig["name"],),
                      use_container_width=True)

st.divider()
st.markdown('<div class="section-title">🌸 Conversation</div>', unsafe_allow_html=True)

# --- Chat ---
chat_area = st.empty()

typed = st.chat_input("Ask a question about the cemetery...")
question = typed or st.session_state.pending_question
st.session_state.pending_question = None

if question:
    st.session_state.messages.append(("user", question))
    history = st.session_state.messages
    typing = bubble("bot", '<span class="typing"><span></span><span></span><span></span></span>')
    chat_area.markdown(chat_html(history, typing), unsafe_allow_html=True)

    answer = answer_question(question, retriever, client, MODEL)

    # Reveal the answer word by word inside its bubble.
    words = answer.split(" ")
    step = max(1, len(words) // 40)
    for n in range(step, len(words) + step, step):
        partial = " ".join(words[:n])
        chat_area.markdown(chat_html(history, bubble("bot", to_html(partial) + " ▍")), unsafe_allow_html=True)
        time.sleep(0.03)
    st.session_state.messages.append(("assistant", answer))

if st.session_state.messages:
    chat_area.markdown(chat_html(st.session_state.messages), unsafe_allow_html=True)
else:
    chat_area.markdown(
        '<div class="empty">🌷 No questions yet. Ask about a person, a place, or the cemetery\'s history below.</div>',
        unsafe_allow_html=True,
    )
