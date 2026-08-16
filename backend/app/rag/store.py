"""
Storage and retrieval for RAG document chunks. Search is brute-force
cosine similarity computed in Python (via numpy) over the embeddings
of chunks matching the given filters — no vector-index extension
needed (see DocumentChunk model docstring for why). Fine at personal-
project document volumes; revisit if the corpus grows very large.
"""
from dataclasses import dataclass
import numpy as np
from sqlalchemy.orm import Session

from app.models.tables import DocumentChunk, Stock
from app.rag.embeddings import embed_texts, embed_query
from app.rag.chunking import chunk_text


@dataclass
class RetrievedChunk:
    content: str
    title: str | None
    source_url: str | None
    source_type: str
    score: float  # cosine similarity, higher = more relevant


def add_document(
    db: Session,
    text: str,
    source_type: str,
    title: str | None = None,
    source_url: str | None = None,
    symbol: str | None = None,
    chunk_size_words: int = 250,
    overlap_words: int = 40,
    embed_batch_size: int = 20,
    verbose: bool = True,
) -> int:
    """
    Chunks `text`, embeds each chunk, and stores them as DocumentChunk
    rows. Returns the number of chunks created (0 if `text` was empty
    — chunk_text() already handles that case).

    Does NOT commit — caller controls the transaction, so a batch
    ingestion job can commit once at the end rather than per-document.

    Embeds in batches of `embed_batch_size` (rather than one call over
    every chunk) and prints progress between batches when verbose=True
    — a long document (e.g. a 300-page annual report) can produce
    hundreds of chunks, and without this, a slow embedding pass looks
    identical to a genuinely hung process. Set verbose=False for
    scripted/silent use.
    """
    chunks = chunk_text(text, chunk_size_words=chunk_size_words, overlap_words=overlap_words)
    if not chunks:
        return 0

    if verbose:
        print(f"    chunked into {len(chunks)} piece(s), embedding...")

    stock_id = None
    if symbol is not None:
        stock = db.query(Stock).filter_by(symbol=symbol).first()
        if stock is None:
            stock = Stock(symbol=symbol)
            db.add(stock)
            db.flush()
        stock_id = stock.id

    for batch_start in range(0, len(chunks), embed_batch_size):
        batch = chunks[batch_start:batch_start + embed_batch_size]
        batch_embeddings = embed_texts(batch)

        for chunk_content, embedding in zip(batch, batch_embeddings):
            db.add(DocumentChunk(
                source_type=source_type,
                stock_id=stock_id,
                title=title,
                source_url=source_url,
                content=chunk_content,
                embedding=embedding,
            ))

        if verbose:
            done = min(batch_start + embed_batch_size, len(chunks))
            print(f"    embedded {done}/{len(chunks)} chunks")

    return len(chunks)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr, b_arr = np.array(a), np.array(b)
    denom = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    if denom == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / denom)


def search(
    db: Session,
    query: str,
    top_k: int = 5,
    source_type: str | None = None,
    symbol: str | None = None,
) -> list[RetrievedChunk]:
    """
    Returns the top_k most semantically similar chunks to `query`,
    optionally filtered to a specific source_type and/or stock symbol.
    Returns fewer than top_k (or an empty list) if there aren't enough
    matching chunks — never pads with irrelevant results.
    """
    q = db.query(DocumentChunk)
    if source_type is not None:
        q = q.filter(DocumentChunk.source_type == source_type)
    if symbol is not None:
        stock = db.query(Stock).filter_by(symbol=symbol).first()
        if stock is None:
            return []  # no such stock, so no chunks could belong to it
        q = q.filter(DocumentChunk.stock_id == stock.id)

    candidates = q.all()
    if not candidates:
        return []

    query_embedding = embed_query(query)
    scored = [
        (c, _cosine_similarity(query_embedding, c.embedding))
        for c in candidates
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    return [
        RetrievedChunk(
            content=c.content, title=c.title, source_url=c.source_url,
            source_type=c.source_type, score=round(score, 4),
        )
        for c, score in scored[:top_k]
    ]