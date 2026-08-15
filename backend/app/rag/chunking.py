"""
Splits long text into overlapping chunks sized for embedding.
Word-based (not character-based) so chunk boundaries don't split
mid-word, and overlapping so a fact sitting right at a chunk boundary
still appears whole in at least one chunk.
"""


def chunk_text(text: str, chunk_size_words: int = 250, overlap_words: int = 40) -> list[str]:
    """
    Returns a list of chunks, each up to `chunk_size_words` words,
    with `overlap_words` words repeated between consecutive chunks.

    Empty/whitespace-only input returns an empty list rather than a
    list containing one empty string — avoids embedding and storing
    a useless chunk.
    """
    words = text.split()
    if not words:
        return []

    if chunk_size_words <= overlap_words:
        raise ValueError("chunk_size_words must be greater than overlap_words")

    chunks = []
    start = 0
    step = chunk_size_words - overlap_words

    while start < len(words):
        chunk_words = words[start:start + chunk_size_words]
        chunks.append(" ".join(chunk_words))
        if start + chunk_size_words >= len(words):
            break
        start += step

    return chunks
