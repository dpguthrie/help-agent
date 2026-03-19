from scraper.chunker import chunk_text


def test_short_text_single_chunk():
    chunks = chunk_text("Hello world", max_tokens=500)
    assert len(chunks) == 1
    assert chunks[0] == "Hello world"


def test_long_text_multiple_chunks():
    text = " ".join(["word"] * 2000)
    chunks = chunk_text(text, max_tokens=500)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.split()) <= 600


def test_chunk_preserves_sentence_boundaries():
    text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    chunks = chunk_text(text, max_tokens=10)
    for chunk in chunks:
        assert chunk.strip().endswith(".")
