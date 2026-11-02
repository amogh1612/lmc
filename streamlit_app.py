"""Web UI for the South-View Cemetery RAG assistant. Run with: streamlit run streamlit_app.py"""

import datetime
import html
import os
import re
import time

import importlib

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from groq import Groq

import directory
import featured as featured_module
import rag
import styles

APP_DIR = os.path.dirname(os.path.abspath(__file__))
# Changes whenever the code or database changes, so a redeploy never mixes old cached objects with new code.
CODE_VERSION = "-".join(
    str(int(os.path.getmtime(os.path.join(APP_DIR, f))))
    for f in ("rag.py", "directory.py", "featured.py", "styles.py", "southview_rag_database.json")
)


@st.cache_resource(show_spinner=False)
def _load_current_code(version: str) -> str:
    """Reload this project's modules once per code version (Streamlit Cloud can keep old ones in memory)."""
    for module in (rag, directory, featured_module, styles):
        importlib.reload(module)
    return version


_load_current_code(CODE_VERSION)

from directory import OCCUPATION_GROUPS, OTHER_GROUP, filter_people, load_people, load_prominent
from featured import monthly_featured
from rag import answer_question, build_retriever
from styles import CSS

MODEL = "openai/gpt-oss-20b"
TITLE = "South-View Cemetery Q&A"
PAGE_SIZE = 24

st.set_page_config(page_title=TITLE, page_icon="🌷", layout="wide")

# Flowers tied to remembrance, used for the card accents and falling petals.
CARD_FLOWERS = ["🌹", "🌷", "🌸", "🌺", "🌼"]
PETALS = ["🌸", "🌷", "🌼", "🌺", "🌹", "💮"]
ERA_ORDER = ["19th century", "Early 20th century", "Civil Rights era", "Late 20th century", "21st century", "Unknown"]


# ---------- HTML helpers ----------

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
    """Escape model or user text, keeping simple **bold**, bullet lines and line breaks."""
    safe = html.escape(text)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    safe = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"<em>\1</em>", safe)
    safe = re.sub(r"(?m)^\s*[-*•]\s+", "• ", safe)
    return safe.replace("\n", "<br>")


def sources_html(sources: list[dict]) -> str:
    if not sources:
        return ""
    items = []
    for s in sources:
        title = html.escape(s.get("title") or "Source")
        if s.get("url"):
            title = f'<a href="{html.escape(s["url"], quote=True)}" target="_blank" rel="noopener">{title}</a>'
        detail = f" · {html.escape(s['detail'])}" if s.get("detail") else ""
        items.append(f"<li>{title}{detail}</li>")
    return f'<div class="sources"><div class="sources-title">Sources</div><ol>{"".join(items)}</ol></div>'


def bubble(role: str, content_html: str) -> str:
    cls, avatar = ("user", "🙂") if role == "user" else ("bot", "🌷")
    return f'<div class="row {cls}"><div class="avatar">{avatar}</div><div class="bubble">{content_html}</div></div>'


def message_html(m: dict) -> str:
    body = to_html(m["content"])
    if m["role"] == "assistant":
        body += sources_html(m.get("sources", []))
    return bubble(m["role"], body)


def chat_html(messages: list[dict], extra: str = "") -> str:
    return '<div class="chat">' + "".join(message_html(m) for m in messages) + extra + "</div>"


def scroll_to_latest(slot, nonce: str, target: str = "latest") -> None:
    """Scroll the page so the newest question and its answer are in view, or to the top on first load."""
    selector = ".hero" if target == "top" else ".chat .row.user"
    delay = 700 if target == "top" else 150  # on first load, wait for Streamlit to finish laying out
    script = f"""<script>/* {nonce} */
    setTimeout(() => {{
      const rows = window.parent.document.querySelectorAll('{selector}');
      if (rows.length) rows[rows.length - 1].scrollIntoView({{behavior: 'smooth', block: 'start'}});
    }}, {delay});
    </script>"""
    with slot:
        if hasattr(st, "iframe"):  # newer Streamlit
            st.iframe(script, height=1)
        else:
            components.html(script, height=0)


# ---------- Setup ----------

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
def get_client_and_retriever(version: str):
    return Groq(api_key=api_key), build_retriever()


@st.cache_data
def get_featured(year: int, month: int, version: str):
    # Cached per month, so the picks refresh automatically when the month changes.
    return monthly_featured(datetime.date(year, month, 1))


@st.cache_data
def get_directory(version: str):
    return load_people(), load_prominent()


client, retriever = get_client_and_retriever(CODE_VERSION)
people, prominent = get_directory(CODE_VERSION)
prominent_by_id = {f["id"]: f for f in prominent}
prominent_by_person = {f.get("person_id"): f for f in prominent}

for key, default in [("messages", []), ("pending_question", None), ("find_limit", PAGE_SIZE)]:
    if key not in st.session_state:
        st.session_state[key] = default


def ask_about(name: str):
    st.session_state.pending_question = f"Tell me about {name}."


# ---------- Profile dialog ----------

@st.dialog("Profile", width="large")
def show_profile(fig_id: str):
    fig = prominent_by_id[fig_id]
    st.markdown(f"## {html.escape(fig['full_name'])}")
    meta = [fig.get("lifespan", "")]
    if fig.get("also_known_as"):
        meta.append("Also known as " + ", ".join(fig["also_known_as"]))
    st.markdown(f'<div class="profile-meta">{html.escape(" · ".join(m for m in meta if m))}</div>',
                unsafe_allow_html=True)
    if fig.get("burial"):
        st.markdown(f'<div class="profile-burial"><b>At South-View:</b> {html.escape(fig["burial"])}</div>',
                    unsafe_allow_html=True)

    def cites(nums):
        return f' <span class="cite">[{", ".join(str(n) for n in nums)}]</span>' if nums else ""

    for section in fig.get("sections", []):
        st.markdown(f"#### {html.escape(section['heading'])}")
        st.markdown(f"<div>{html.escape(section['text'])}{cites(section.get('sources'))}</div>",
                    unsafe_allow_html=True)
    if fig.get("timeline"):
        st.markdown("#### Timeline")
        rows = "".join(f"<div><b>{html.escape(str(t['year']))}</b> {html.escape(t['event'])}{cites(t.get('sources'))}</div>"
                       for t in fig["timeline"])
        st.markdown(f'<div class="timeline">{rows}</div>', unsafe_allow_html=True)
    if fig.get("sources"):
        st.markdown("#### Sources")
        items = "".join(
            f'<li><a href="{html.escape(s["url"], quote=True)}" target="_blank" rel="noopener">'
            f'{html.escape(s["title"])}</a>{" · " + html.escape(s["publisher"]) if s.get("publisher") else ""}</li>'
            for s in fig["sources"])
        st.markdown(f'<div class="sources" style="font-size:.85rem"><ol>{items}</ol></div>', unsafe_allow_html=True)
    if st.button("Ask about them in the chat", type="primary", use_container_width=True):
        ask_about(fig["full_name"])
        st.rerun()


# ---------- Browse tabs ----------

tab_prom, tab_feat, tab_find = st.tabs(["🌹 Prominent figures", "🌼 Featured this month", "🔎 Find people"])

with tab_prom:
    st.markdown(
        '<div class="section-sub">In-depth profiles of some of South-View\'s best-known residents, '
        "researched from encyclopedias, archives and news obituaries.</div>",
        unsafe_allow_html=True,
    )
    if not prominent:
        st.info("Prominent-figure profiles haven't been added to the database yet.")
    for start in range(0, len(prominent), 4):
        cols = st.columns(4)
        for col, fig in zip(cols, prominent[start:start + 4]):
            with col, st.container(key=f"card-prom-{fig['id']}"):
                st.markdown(
                    '<span class="badge">★ Prominent figure</span>'
                    f'<div class="card-name">{html.escape(fig["full_name"])}</div>'
                    f'<div class="card-meta">{html.escape(fig.get("lifespan", ""))}</div>'
                    f'<div class="card-tagline">{html.escape(fig.get("tagline", ""))}</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Read profile", key=f"prof-{fig['id']}", use_container_width=True):
                    show_profile(fig["id"])
                st.button("Ask about them", key=f"askp-{fig['id']}", on_click=ask_about,
                          args=(fig["full_name"],), use_container_width=True)

with tab_feat:
    today = datetime.date.today()
    featured = get_featured(today.year, today.month, CODE_VERSION)
    st.markdown(
        f'<div class="section-sub">Five people from South-View\'s history for {today.strftime("%B %Y")}, '
        "chosen fresh each month.</div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(len(featured))
    for i, (col, fig) in enumerate(zip(cols, featured)):
        with col, st.container(key=f"featcard-{i}"):
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

with tab_find:
    years = [p["death_year"] for p in people if p["death_year"]]
    eras = [e for e in ERA_ORDER if any(p["era"] == e for p in people)]
    c1, c2, c3 = st.columns([2, 2, 2])
    name_q = c1.text_input("Name or occupation", placeholder="e.g. Herndon, pianist, nurse")
    groups = c2.multiselect("Field of work", list(OCCUPATION_GROUPS) + [OTHER_GROUP])
    era_sel = c3.multiselect("Era", eras)
    c4, c5 = st.columns([4, 2])
    died = c4.slider("Year of death", min(years), max(years), (min(years), max(years)))
    prom_only = c5.toggle("Prominent figures only")
    include_unknown = died == (min(years), max(years))  # don't hide people with no death year unless asked

    matches = filter_people(people, name_q, groups, era_sel, None if include_unknown else died, prom_only)

    sig = (name_q, tuple(groups), tuple(era_sel), died, prom_only)
    if st.session_state.get("find_sig") != sig:
        st.session_state.find_sig = sig
        st.session_state.find_limit = PAGE_SIZE

    shown = matches[: st.session_state.find_limit]
    st.markdown(f'<div class="result-count">{len(matches)} of {len(people)} people match.</div>',
                unsafe_allow_html=True)
    for start in range(0, len(shown), 4):
        cols = st.columns(4)
        for col, p in zip(cols, shown[start:start + 4]):
            with col, st.container(key=f"card-find-{p['id']}"):
                life = (f"{p['birth_year']}–{p['death_year']}" if p["birth_year"] and p["death_year"]
                        else f"d. {p['death_year']}" if p["death_year"] else "")
                meta = " · ".join(x for x in [", ".join(p["occupations"][:2]), life] if x)
                badge = '<span class="badge">★ Prominent figure</span>' if p["prominent"] else ""
                st.markdown(
                    f'{badge}<div class="card-name">{html.escape(p["name"])}</div>'
                    f'<div class="card-meta">{html.escape(meta)}</div>'
                    f'<div class="card-teaser">{html.escape(p["teaser"])}</div>',
                    unsafe_allow_html=True,
                )
                fig = prominent_by_person.get(p["id"])
                if fig and st.button("Read profile", key=f"proff-{p['id']}", use_container_width=True):
                    show_profile(fig["id"])
                st.button("Ask about them", key=f"askf-{p['id']}", on_click=ask_about, args=(p["name"],),
                          use_container_width=True)
    if len(matches) > len(shown):
        if st.button(f"Show more ({len(matches) - len(shown)} left)"):
            st.session_state.find_limit += PAGE_SIZE
            st.rerun()

st.divider()
st.markdown('<div class="section-title">🌸 Conversation</div>', unsafe_allow_html=True)

# ---------- Chat ----------

chat_area = st.empty()
scroll_slot = st.container(key="autoscroll").empty()

typed = st.chat_input("Ask a question, or a follow-up...")
question = typed or st.session_state.pending_question
st.session_state.pending_question = None

if question:
    history = list(st.session_state.messages)
    st.session_state.messages.append({"role": "user", "content": question})
    msgs = st.session_state.messages
    typing = bubble("bot", '<span class="typing"><span></span><span></span><span></span></span>')
    chat_area.markdown(chat_html(msgs, typing), unsafe_allow_html=True)
    scroll_to_latest(scroll_slot, f"q{len(msgs)}")

    result = answer_question(question, retriever, client, MODEL, history)
    answer = result["answer"]

    # Reveal the answer word by word inside its bubble, then show its sources.
    words = answer.split(" ")
    step = max(1, len(words) // 40)
    for n in range(step, len(words) + step, step):
        partial = " ".join(words[:n])
        chat_area.markdown(chat_html(msgs, bubble("bot", to_html(partial) + " ▍")), unsafe_allow_html=True)
        time.sleep(0.03)
    st.session_state.messages.append({"role": "assistant", "content": answer, "sources": result["sources"]})

if st.session_state.messages:
    chat_area.markdown(chat_html(st.session_state.messages), unsafe_allow_html=True)
    if question:
        scroll_to_latest(scroll_slot, f"a{len(st.session_state.messages)}")
elif not st.session_state.get("opened"):
    # Chat pages open pinned to the bottom; start visitors at the title instead.
    st.session_state.opened = True
    scroll_to_latest(scroll_slot, "top", target="top")
if not st.session_state.messages:
    chat_area.markdown(
        '<div class="empty">🌷 No questions yet. Ask about a person, a place, or the cemetery\'s history below. '
        "Follow-up questions work too.</div>",
        unsafe_allow_html=True,
    )
