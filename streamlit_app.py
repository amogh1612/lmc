"""Simple web UI for the Southview Cemetery RAG assistant. Run with: streamlit run streamlit_app.py"""

import datetime
import os

import streamlit as st
from dotenv import load_dotenv
from groq import Groq

from featured import monthly_featured
from rag import answer_question, build_retriever

MODEL = "openai/gpt-oss-20b"

st.set_page_config(page_title="Southview Cemetery Q&A", page_icon="🪦", layout="wide")
st.title("Southview Cemetery Q&A")
st.caption("Ask about notable figures buried at Southview Cemetery.")

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
st.subheader(f"Featured figures for {today.strftime('%B %Y')}")
st.caption("Five people from South-View's history, chosen fresh each month. Tap a card to learn more.")

cols = st.columns(len(featured))
for col, fig in zip(cols, featured):
    with col:
        with st.container(border=True, height="stretch"):
            st.markdown(f"**{fig['name']}**")
            meta = ", ".join(fig["occupations"][:2])
            if fig["death_year"]:
                meta += f" · d. {fig['death_year']}"
            st.caption(meta)
            st.write(fig["teaser"])
            st.button("Ask about them", key=f"feat-{fig['name']}", on_click=ask_about, args=(fig["name"],),
                      use_container_width=True)

st.divider()

# --- Chat ---
for role, content in st.session_state.messages:
    with st.chat_message(role):
        st.markdown(content)

typed = st.chat_input("Ask a question about the cemetery...")
question = typed or st.session_state.pending_question
st.session_state.pending_question = None

if question:
    st.session_state.messages.append(("user", question))
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Looking it up..."):
            answer = answer_question(question, retriever, client, MODEL)
        st.markdown(answer)
    st.session_state.messages.append(("assistant", answer))
