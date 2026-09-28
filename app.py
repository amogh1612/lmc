"""CLI chat for the Southview Cemetery RAG assistant. Free to run: local retrieval + Groq's free tier."""

import os
import sys

from dotenv import load_dotenv
from groq import Groq

from rag import answer_question, build_retriever

MODEL = "openai/gpt-oss-20b"


def main():
    load_dotenv()
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("Missing GROQ_API_KEY. Copy .env.example to .env and add your key.")
        sys.exit(1)

    client = Groq(api_key=api_key)
    retriever = build_retriever()

    print("Southview Cemetery Q&A — ask about notable figures (Ctrl+C to quit)\n")
    while True:
        try:
            question = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if not question:
            continue

        answer = answer_question(question, retriever, client, MODEL)
        print(f"Assistant: {answer}\n")


if __name__ == "__main__":
    main()
