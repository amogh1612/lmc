"""Simple web UI for the Southview Cemetery RAG assistant. Run with: streamlit run streamlit_app.py"""

import os

import streamlit as st
from dotenv import load_dotenv
from groq import Groq

from rag import answer_question, build_retriever

MODEL = "openai/gpt-oss-20b"

st.set_page_config(page_title="Southview Cemetery Q&A", page_icon="🪦")
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


client, retriever = get_client_and_retriever()

if "messages" not in st.session_state:
    st.session_state.messages = []

for role, content in st.session_state.messages:
    with st.chat_message(role):
        st.markdown(content)

question = st.chat_input("Ask a question about the cemetery...")
if question:
    st.session_state.messages.append(("user", question))
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Looking it up..."):
            answer = answer_question(question, retriever, client, MODEL)
        st.markdown(answer)
    st.session_state.messages.append(("assistant", answer))
