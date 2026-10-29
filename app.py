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
    history = []

    print("South-View Cemetery Q&A — ask about notable figures (Ctrl+C to quit)\n")
    while True:
        try:
            question = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if not question:
            continue

        result = answer_question(question, retriever, client, MODEL, history)
        print(f"Assistant: {result['answer']}")
        for s in result["sources"]:
            print(f"  source: {s['title']}" + (f" ({s['url']})" if s.get("url") else ""))
        print()
        history += [{"role": "user", "content": question}, {"role": "assistant", "content": result["answer"]}]


if __name__ == "__main__":
    main()
