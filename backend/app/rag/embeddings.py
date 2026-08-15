"""
Wraps fastembed for generating text embeddings — a lightweight,
ONNX-based library (no torch dependency, ~200MB install vs. several
GB for sentence-transformers) that runs entirely locally, no API key
or per-call cost.

IMPORTANT: the model weights (~130MB) download from huggingface.co on
first use. I could not verify this download from this sandbox —
huggingface.co isn't reachable here (confirmed: a live attempt got
"Host not in allowlist"). This WILL need a real internet connection
on your machine the first time `get_embedder()` runs; after that,
fastembed caches the model locally and doesn't re-download.
"""
from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384  # fixed by this model — every stored/query embedding must match this length

_embedder = None  # module-level cache — loaded once per process, not per call


def get_embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding(model_name=MODEL_NAME)
    return _embedder


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Returns one embedding vector (list of EMBEDDING_DIM floats) per
    input text, in the same order. Batches internally — pass a list
    even for a single text rather than calling this in a loop.
    """
    embedder = get_embedder()
    return [vec.tolist() for vec in embedder.embed(texts)]


def embed_query(text: str) -> list[float]:
    """Convenience wrapper for embedding a single query string."""
    return embed_texts([text])[0]
