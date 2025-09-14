import os
from pathlib import Path
from typing import List, Iterable

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_qdrant import QdrantVectorStore
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

COLLECTION = os.getenv("QDRANT_COLLECTION", os.getenv("CHROMA_COLLECTION", "personal_kb"))
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4.1")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gpt-4.1-mini")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_store")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_HOST = os.getenv("QDRANT_HOST")
QDRANT_PORT = os.getenv("QDRANT_PORT")

from dotenv import load_dotenv

load_dotenv()


# ------------------------ RETRIEVER ------------------------


def make_retriever(k: int = 4):
    """
    Construct a retriever. Prefers Qdrant if configured; falls back to local Chroma.
    """
    embed = OpenAIEmbeddings(model=EMBED_MODEL)
    if (QDRANT_URL and QDRANT_API_KEY) or (QDRANT_HOST and QDRANT_PORT):
        try:
            from qdrant_client import QdrantClient  # type: ignore
        except Exception as e:
            raise RuntimeError("qdrant-client is required for Qdrant backend") from e
        if QDRANT_URL:
            client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        else:
            client = QdrantClient(host=QDRANT_HOST, port=int(QDRANT_PORT or 6333), api_key=QDRANT_API_KEY)
        vs = QdrantVectorStore(
            client=client,
            collection_name=COLLECTION,
            embedding=embed,
        )
    else:
        vs = Chroma(
            collection_name=COLLECTION,
            persist_directory=CHROMA_PATH,
            embedding_function=embed,
        )
    return vs.as_retriever(search_kwargs={"k": k})


def _format_docs(docs: List):
    """Join retrieved chunks, including provenance if present."""
    lines = []
    for d in docs:
        src = (d.metadata or {}).get("source")
        title = (d.metadata or {}).get("title")
        header = f"[{title}] - {src}" if (title and src) else (src or title or "")
        lines.append((f"Source: {header}\n" if header else "") + d.page_content)
    return "\n\n---\n\n".join(lines)


# ------------------------ PROMPT ------------------------
SYSTEM_PROMPT = (
    "You are Ashwin Rachha's personal bot. Answer in FIRST PERSON as \"I\".\n"
    "Use ONLY the provided context. If the answer isn’t clearly supported, say:\n"
    "“I don’t know based on my notes.” Be concise and factual.\n"
    "When relevant, include short attributions like (source: domain or title)."
)

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "Question: {question}\n\nMy notes:\n{context}"),
    ]
)


# ------------------------ LLM ------------------------
def _load_env() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except Exception:
        # Optional dependency; ignore if not installed
        pass


def make_llm(streaming: bool = True):
    _load_env()  # ensure OPENAI_API_KEY and other env vars are loaded
    model_name = CHAT_MODEL
    try:
        return ChatOpenAI(
            model=model_name,
            temperature=0.2,
            streaming=streaming,
        )
    except Exception:
        return ChatOpenAI(
            model=FALLBACK_MODEL,
            temperature=0.2,
            streaming=streaming,
        )


# ------------------------ LCEL CHAIN ------------------------
def build_chain(k: int = 4, streaming: bool = True):
    retriever = make_retriever(k=k)
    llm = make_llm(streaming=streaming)
    parser = StrOutputParser()

    chain = (
        {
            "context": retriever | _format_docs,
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
        | parser
    )
    return chain


def stream_answer(question: str, k: int = 4) -> Iterable[str]:
    """
    Yield the answer as a sequence of string chunks.
    """
    chain = build_chain(k=k)
    yield from chain.stream(question)


def get_context_chunks(question: str, k: int = 4) -> List[dict]:
    """Return context metadata to optionally show before streaming tokens."""
    retriever = make_retriever(k=k)
    # Use LCEL-style invoke to avoid deprecation warnings
    docs = retriever.invoke(question)
    items = []
    for d in docs:
        items.append(
            {
                "text": d.page_content,
                "source": (d.metadata or {}).get("source"),
                "title": (d.metadata or {}).get("title"),
            }
        )
    return items


if __name__ == "__main__":
    # Lightweight CLI + test helpers for local validation
    import argparse
    import time

    def test_ping(k: int = 4) -> None:
        try:
            retriever = make_retriever(k=k)
            docs = retriever.get_relevant_documents("ping")
            print(f"Ping OK. Retrieved {len(docs)} doc(s) for a dummy query.")
            if docs:
                d0 = docs[0]
                meta = d0.metadata or {}
                print("Sample doc:")
                print(f"- title:  {meta.get('title')}")
                print(f"- source: {meta.get('source')}")
                preview = d0.page_content[:200]
                print((preview + ("..." if len(d0.page_content) > 200 else "")))
        except Exception as e:
            print(f"Ping failed: {e}")

    def test_context(question: str, k: int = 4) -> None:
        try:
            items = get_context_chunks(question, k=k)
            print(f"Top-{k} context items:")
            for i, it in enumerate(items, 1):
                print(f"\n[{i}] title={it.get('title')} source={it.get('source')}")
                txt = it.get("text") or ""
                print(txt[:200] + ("..." if len(txt) > 200 else ""))
        except Exception as e:
            print(f"Context error: {e}")

    def test_answer(question: str, k: int = 4, stream: bool = False) -> None:
        try:
            if stream:
                print("Answer (streaming):")
                t0 = time.perf_counter()
                for chunk in stream_answer(question, k=k):
                    print(chunk, end="", flush=True)
                dt = time.perf_counter() - t0
                print(f"\n\n---\nLatency: {dt*1000:.0f} ms")
            else:
                print("Answer:")
                t0 = time.perf_counter()
                answer = build_chain(k=k, streaming=False).invoke(question)
                dt = time.perf_counter() - t0
                print(answer)
                print(f"\n---\nLatency: {dt*1000:.0f} ms")
        except Exception as e:
            print(f"Answer error: {e}")

    parser = argparse.ArgumentParser(description="Quick test harness for RAG (Qdrant or Chroma)")
    parser.add_argument("--question", "-q", help="Question to ask")
    parser.add_argument("--k", type=int, default=4, help="Top-k to retrieve")
    parser.add_argument("--stream", action="store_true", help="Stream tokens instead of a single answer")
    parser.add_argument("--show-context", action="store_true", help="Print retrieved context before answering")
    parser.add_argument("--ping", action="store_true", help="Ping the Chroma collection (load + quick retrieval)")
    args = parser.parse_args()

    print("Config:")
    backend = 'Qdrant' if (QDRANT_URL and QDRANT_API_KEY) or (QDRANT_HOST and QDRANT_PORT) else 'Chroma'
    print(f"- BACKEND         = {backend}")
    print(f"- COLLECTION      = {COLLECTION}")
    if not (QDRANT_URL and QDRANT_API_KEY):
        print(f"- CHROMA_PATH     = {CHROMA_PATH}")
    else:
        print(f"- QDRANT_URL      = {QDRANT_URL}")
    print(f"- EMBED_MODEL     = {EMBED_MODEL}")
    print(f"- CHAT_MODEL      = {CHAT_MODEL} (fallback: {FALLBACK_MODEL})")
    print()

    if args.ping:
        test_ping(k=args.k)
        raise SystemExit(0)

    if not args.question:
        print("No --question provided. Use --ping to just test connectivity.")
        raise SystemExit(0)

    if args.show_context:
        test_context(args.question, k=args.k)
        print()

    test_answer(args.question, k=args.k, stream=args.stream)
