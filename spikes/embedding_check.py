"""Spike D-1: are multilingual embeddings available via OpenRouter with the same API key?

Embeds four simplified German legal statements and four English lay questions and checks
whether every English question is closest to the matching German statement (cross-lingual
retrieval). Throwaway script, kept as a record of the decision.

Related: D-1, NFR-01, FR-04 AC6
"""

from __future__ import annotations

import os

import numpy as np
from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

load_dotenv()

#: Candidate model from D-1; override with EMBEDDING_MODEL=... for comparisons.
MODEL = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-large")
#: Input prefixes; e5 models need them, other models get "" (QUERY_PREFIX="" PASSAGE_PREFIX="").
QUERY_PREFIX = os.getenv("QUERY_PREFIX", "query: ")
PASSAGE_PREFIX = os.getenv("PASSAGE_PREFIX", "passage: ")

#: Simplified German statements (paraphrases for the spike, not verbatim statute text).
PASSAGES: dict[str, str] = {
    "ZPO § 692": "Gegen den Mahnbescheid kann der Antragsgegner binnen zwei Wochen "
    "ab Zustellung Widerspruch erheben.",
    "BGB § 195": "Die regelmäßige Verjährungsfrist beträgt drei Jahre.",
    "BGB § 288": "Eine Geldschuld ist während des Verzugs zu verzinsen. Der Verzugszinssatz "
    "beträgt für das Jahr fünf Prozentpunkte über dem Basiszinssatz.",
    "RDG info duties": "Inkassodienstleister müssen einer Privatperson mit der ersten "
    "Geltendmachung einer Forderung den Auftraggeber und den Forderungsgrund mitteilen.",
}

#: English lay questions, each paired with the provision it should retrieve.
QUESTIONS: dict[str, str] = {
    "I got a letter from the court. How long do I have to object?": "ZPO § 692",
    "My phone bill is from 2021. Is it too old to be collected?": "BGB § 195",
    "How much interest can they charge me for paying late?": "BGB § 288",
    "The debt collector did not say who they work for. Must they tell me?": "RDG info duties",
}


def make_embeddings() -> OpenAIEmbeddings:
    """Create the OpenRouter embedding client (same key as the chat model)."""
    return OpenAIEmbeddings(
        model=MODEL,  # AI: which embedding model turns text into vectors
        base_url="https://openrouter.ai/api/v1",  # OpenRouter instead of OpenAI
        api_key=os.environ["OPENROUTER_API_KEY"],
        check_embedding_ctx_length=False,  # send raw text, not OpenAI token IDs
    )


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity of two vectors: 1.0 = same direction, 0.0 = unrelated."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))  # AI: similarity


def run(embeddings: Embeddings) -> float:
    """Embed passages and questions, print the best match per question, return accuracy."""
    ids = list(PASSAGES)
    # AI: e5 models expect "passage: " for documents and "query: " for questions.
    doc_vectors = embeddings.embed_documents([f"{PASSAGE_PREFIX}{PASSAGES[i]}" for i in ids])
    print(f"Model: {MODEL} · dimensions: {len(doc_vectors[0])}\n")

    hits = 0
    for question, expected in QUESTIONS.items():
        q_vector = np.array(
            embeddings.embed_query(f"{QUERY_PREFIX}{question}")
        )  # AI: question vector
        scores = {i: cosine(q_vector, np.array(v)) for i, v in zip(ids, doc_vectors, strict=True)}
        best = max(scores, key=scores.__getitem__)  # AI: nearest neighbour = retrieval
        hits += best == expected
        ranking = ", ".join(f"{i}={s:.3f}" for i, s in sorted(scores.items(), key=lambda x: -x[1]))
        print(f"{'OK  ' if best == expected else 'MISS'} {question}\n     {ranking}\n")

    accuracy = hits / len(QUESTIONS)
    print(f"Cross-lingual top-1 accuracy: {hits}/{len(QUESTIONS)} = {accuracy:.0%}")
    return accuracy


if __name__ == "__main__":
    run(make_embeddings())
