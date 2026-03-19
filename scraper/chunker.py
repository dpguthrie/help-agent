from __future__ import annotations
import re


def chunk_text(text: str, max_tokens: int = 500) -> list[str]:
    if not text.strip():
        return []

    max_words = int(max_tokens * 0.75)
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    chunks = []
    current_chunk: list[str] = []
    current_words = 0

    for sentence in sentences:
        words = sentence.split()
        word_count = len(words)
        # If a single sentence exceeds max_words, split it by words directly
        if word_count > max_words:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_words = 0
            for j in range(0, word_count, max_words):
                chunks.append(" ".join(words[j:j + max_words]))
            continue
        if current_words + word_count > max_words and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_words = 0
        current_chunk.append(sentence)
        current_words += word_count

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks
